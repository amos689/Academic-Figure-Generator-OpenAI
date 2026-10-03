from __future__ import annotations

import copy
import json
import socket
import traceback
from pathlib import Path

import pytest

from app.core.exceptions import FileValidationException
from app.schemas.figure_spec import FigureSpec
from app.services.document_service import DocumentService
from app.services.figure_evaluation_service import FigureEvaluationService

_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "evaluation"
_FIXTURE_NAMES = ["branch-and-merge", "illustrative-scores", "retrieval-routing"]


def _fixture(name="retrieval-routing"):
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _evaluate(spec, fixture=None):
    return FigureEvaluationService().evaluate(spec, fixture or _fixture())


def _check(report, name):
    return next(
        check
        for category in ("structural", "grounding")
        for check in report[category]["checks"]
        if check["name"] == name
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline figure evaluation attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def test_fixed_fixture_inventory_is_explicit():
    assert sorted(path.stem for path in _FIXTURES.glob("*.json")) == _FIXTURE_NAMES


@pytest.mark.parametrize("name", _FIXTURE_NAMES)
def test_original_known_good_fixtures_pass_without_aesthetic_claims(name):
    fixture = _fixture(name)
    before = copy.deepcopy(fixture)
    candidate = fixture["reference_spec"]
    result = _evaluate(candidate, fixture)

    assert result["passed"]
    assert result["fixture_id"] == name
    assert result["structural"]["status"] == "passed"
    assert result["grounding"]["status"] == "passed"
    assert result["aesthetic"]["status"] == "not_evaluated"
    assert result["aesthetic"]["checks"] == []
    assert "score" not in result["aesthetic"]
    assert result == _evaluate(candidate, fixture)
    assert result == _evaluate(FigureSpec.model_validate(candidate), fixture)
    assert fixture == before
    json.dumps(result, sort_keys=True, allow_nan=False)


def test_ids_can_change_without_changing_structural_meaning():
    fixture = _fixture()
    spec = copy.deepcopy(fixture["reference_spec"])
    ids = {node["id"]: f"renamed-node-{i}" for i, node in enumerate(spec["nodes"])}
    for node in spec["nodes"]:
        node["id"] = ids[node["id"]]
    for index, edge in enumerate(spec["edges"]):
        edge.update(
            id=f"renamed-edge-{index}", source=ids[edge["source"]], target=ids[edge["target"]]
        )
    result = _evaluate(spec, fixture)
    assert result["passed"]
    assert _check(result, "numeric_outcomes")["checked"] == 0


@pytest.mark.parametrize("replacement", ["query", " Query", "Questions"])
def test_required_labels_are_exact_not_synonyms_or_case_folded(replacement):
    spec = _fixture()["reference_spec"]
    spec["nodes"][0]["label"] = replacement
    result = _evaluate(spec)
    assert not result["passed"]
    assert {issue["code"] for issue in _check(result, "exact_labels")["issues"]} == {
        "missing_required_label",
        "unexpected_label",
    }


def test_missing_and_extra_node_labels_are_reported():
    spec = _fixture()["reference_spec"]
    spec["nodes"].pop()
    spec["edges"].pop()
    result = _evaluate(spec)
    assert _check(result, "exact_labels")["status"] == "failed"
    assert _check(result, "exact_edges")["status"] == "failed"

    spec = _fixture()["reference_spec"]
    extra = copy.deepcopy(spec["nodes"][0])
    extra["id"] = "extra-query"
    spec["nodes"].append(extra)
    result = _evaluate(spec)
    assert not result["passed"]
    assert _check(result, "exact_labels")["issues"] == [
        {"code": "unexpected_label", "path": "nodes.5.label"},
    ]


@pytest.mark.parametrize("mutation", ["missing", "extra", "reverse", "label", "kind"])
def test_edges_match_exact_directed_labeled_typed_requirements(mutation):
    spec = _fixture()["reference_spec"]
    if mutation == "missing":
        spec["edges"].pop()
    elif mutation == "extra":
        extra = copy.deepcopy(spec["edges"][0])
        extra["id"] = "duplicate-semantic-edge"
        spec["edges"].append(extra)
    elif mutation == "reverse":
        edge = spec["edges"][0]
        edge["source"], edge["target"] = edge["target"], edge["source"]
    elif mutation == "label":
        spec["edges"][0]["label"] = "Query"
    else:
        spec["edges"][0]["kind"] = "control"
    result = _evaluate(spec)
    assert _check(result, "schema")["status"] == "passed"
    assert _check(result, "exact_labels")["status"] == "passed"
    assert _check(result, "exact_edges")["status"] == "failed"
    assert not result["passed"]


@pytest.mark.parametrize("position", [3, 4])
def test_skip_and_control_edges_are_not_interchangeable_with_data_edges(position):
    fixture = _fixture("branch-and-merge")
    spec = copy.deepcopy(fixture["reference_spec"])
    spec["edges"][position]["kind"] = "data"
    assert _check(_evaluate(spec, fixture), "exact_edges")["status"] == "failed"


@pytest.mark.parametrize(
    "mutation", ["duplicate_id", "dangling_edge", "unknown_group", "markup", "version"]
)
def test_invalid_specs_fail_structure_without_fake_grounding_or_visual_scores(mutation):
    spec = _fixture()["reference_spec"]
    if mutation == "duplicate_id":
        spec["edges"][0]["id"] = spec["nodes"][0]["id"]
    elif mutation == "dangling_edge":
        spec["edges"][0]["target"] = "missing-node"
    elif mutation == "unknown_group":
        spec["nodes"][0]["group_id"] = "missing-group"
    elif mutation == "markup":
        spec["nodes"][0]["label"] = "<script>alert('private-fixture')</script>"
    else:
        spec["version"] = True
    result = _evaluate(spec)
    assert not result["passed"]
    assert _check(result, "schema")["status"] == "failed"
    assert result["grounding"] == {"status": "not_evaluated", "checks": []}
    assert result["aesthetic"]["status"] == "not_evaluated"


def test_report_never_echoes_raw_validation_messages_quotes_or_candidate_values():
    spec = _fixture()["reference_spec"]
    spec["caption"] = "Bearer private-fixture-token"
    spec["nodes"][0]["label"] = "<script>private-fixture-body</script>"
    spec["private-fixture-field"] = "private-fixture-value"
    result = _evaluate(spec)
    assert "private-fixture" not in json.dumps(result)
    assert "Bearer" not in json.dumps(result)
    assert not result["passed"]


@pytest.mark.parametrize("collection", ["nodes", "edges"])
@pytest.mark.parametrize(
    ("index", "quote", "code"),
    [
        (99, "Query feeds Retrieve through the query edge.", "unknown_section_index"),
        (0, "The document contains this fabricated quotation.", "quote_not_in_section"),
        (1, "Query feeds Retrieve through the query edge.", "quote_not_in_section"),
    ],
)
def test_invalid_source_indices_quotes_and_wrong_section_quotes_fail(
    collection, index, quote, code
):
    spec = _fixture()["reference_spec"]
    spec[collection][0]["sources"] = [{"section_index": index, "quote": quote}]
    result = _evaluate(spec)
    assert result["structural"]["status"] == "passed"
    assert _check(result, "source_references")["issues"][0]["code"] == code
    assert not result["passed"]


def test_sparse_original_section_indices_are_not_list_positions():
    fixture = _fixture("branch-and-merge")
    assert _evaluate(fixture["reference_spec"], fixture)["passed"]
    fixture["reference_spec"]["nodes"][0]["sources"][0]["section_index"] = 0
    result = _evaluate(fixture["reference_spec"], fixture)
    assert _check(result, "source_references")["issues"][0]["code"] == "unknown_section_index"


def test_quote_whitespace_is_normalized_but_words_are_not_invented():
    spec = _fixture()["reference_spec"]
    quote = spec["nodes"][0]["sources"][0]["quote"]
    spec["nodes"][0]["sources"][0]["quote"] = "\n  ".join(quote.split())
    assert _evaluate(spec)["passed"]


@pytest.mark.parametrize("collection", ["nodes", "edges"])
def test_each_node_and_edge_needs_at_least_one_valid_source(collection):
    spec = _fixture()["reference_spec"]
    spec[collection][0]["sources"] = []
    result = _evaluate(spec)
    assert _check(result, "source_references")["issues"] == [
        {"code": "missing_source", "path": f"{collection}.0.sources"},
    ]
    assert not result["passed"]


def test_valid_quote_does_not_hide_an_additional_invalid_quote():
    spec = _fixture()["reference_spec"]
    spec["nodes"][0]["sources"].append({"section_index": 1, "quote": "Made up quote."})
    result = _evaluate(spec)
    assert _check(result, "source_references")["status"] == "failed"


@pytest.mark.parametrize(
    "caption",
    [
        "Accuracy reaches 99.9%.",
        "The result is ninety-nine percent accuracy.",
        "Latency improves by half.",
        "The result is \uff19\uff19 percent accuracy.",
        "The result is \u2167 percent accuracy.",
    ],
)
def test_methods_only_fixture_does_not_allow_invented_numeric_outcomes(caption):
    spec = _fixture()["reference_spec"]
    spec["caption"] = caption
    result = _evaluate(spec)
    assert result["structural"]["status"] == "passed"
    assert _check(result, "source_references")["status"] == "passed"
    assert _check(result, "numeric_outcomes")["issues"] == [
        {"code": "unsupported_numeric_text", "path": "caption"},
    ]
    assert not result["passed"]


@pytest.mark.parametrize(
    "caption",
    [
        "Baseline accuracy: 82%. Method accuracy: 70%.",
        "Method latency: 82%.",
        "Method gain: 12 percentage points.",
        "Baseline accuracy: 70.0%. Method accuracy: 82%.",
        "Baseline accuracy: 7",
        "Method accuracy: 8",
        "70%",
    ],
)
def test_numeric_grounding_requires_attribution_not_number_membership(caption):
    fixture = _fixture("illustrative-scores")
    spec = copy.deepcopy(fixture["reference_spec"])
    spec["caption"] = caption
    result = _evaluate(spec, fixture)
    assert _check(result, "numeric_outcomes")["status"] == "failed"
    assert result["structural"]["status"] == "passed"
    assert not result["passed"]


def test_numeric_labels_need_their_own_supporting_quote():
    fixture = _fixture("illustrative-scores")
    spec = copy.deepcopy(fixture["reference_spec"])
    spec["nodes"][3]["sources"] = copy.deepcopy(spec["nodes"][4]["sources"])
    result = _evaluate(spec, fixture)
    assert _check(result, "source_references")["status"] == "passed"
    assert _check(result, "numeric_outcomes")["issues"] == [
        {"code": "unsupported_numeric_text", "path": "nodes.3.label"},
    ]
    assert not result["passed"]


@pytest.mark.parametrize("field", ["title", "nodes", "edges", "groups"])
def test_numeric_guard_checks_all_visible_label_locations(field):
    spec = _fixture()["reference_spec"]
    text = "Invented score: 99%"
    if field == "title":
        spec["title"] = text
    elif field == "groups":
        spec["groups"].append({"id": "scores", "label": text})
    else:
        spec[field][0]["label"] = text
    result = _evaluate(spec)
    assert _check(result, "numeric_outcomes")["status"] == "failed"
    assert not result["passed"]


def test_reference_numeric_text_remains_supported_with_pdf_style_line_wrapping():
    fixture = _fixture("illustrative-scores")
    spec = copy.deepcopy(fixture["reference_spec"])
    spec["caption"] = "Baseline accuracy:\n70%. Method accuracy: 82%."
    result = _evaluate(spec, fixture)
    assert result["passed"]
    assert _check(result, "numeric_outcomes")["checked"] == 3


@pytest.mark.parametrize("mutation", ["sections", "labels", "edges", "missing", "version"])
def test_invalid_or_ambiguous_fixtures_raise_a_private_configuration_error(mutation):
    fixture = _fixture()
    spec = copy.deepcopy(fixture["reference_spec"])
    if mutation == "sections":
        fixture["sections"][1]["index"] = fixture["sections"][0]["index"]
    elif mutation == "labels":
        fixture["required_labels"].append(fixture["required_labels"][0])
    elif mutation == "edges":
        fixture["required_edges"][0]["target_label"] = "private-fixture-label"
    elif mutation == "missing":
        fixture.pop("sections")
    else:
        fixture["version"] = True
    with pytest.raises(ValueError, match="Invalid evaluation fixture definition") as error:
        _evaluate(spec, fixture)
    assert "private-fixture" not in "".join(traceback.format_exception(error.value))


def test_reference_spec_is_optional_for_evaluating_external_candidates():
    fixture = _fixture()
    candidate = fixture.pop("reference_spec")
    assert _evaluate(candidate, fixture)["passed"]


def test_numeric_outcomes_are_forbidden_without_explicit_fixture_approval():
    fixture = _fixture("illustrative-scores")
    fixture.pop("allowed_numeric_text")
    result = _evaluate(fixture["reference_spec"], fixture)
    assert _check(result, "numeric_outcomes")["status"] == "failed"
    assert _check(result, "source_references")["status"] == "passed"


def test_fixture_cannot_whitelist_numeric_wording_absent_from_its_sources():
    fixture = _fixture("illustrative-scores")
    fixture["allowed_numeric_text"].append("Accuracy: 99.9%")
    with pytest.raises(ValueError, match="Invalid evaluation fixture definition"):
        _evaluate(fixture["reference_spec"], fixture)


def test_document_parser_hides_raw_exception_text_in_response_and_logs(monkeypatch, caplog):
    service = DocumentService()

    def failing_parser(_content):
        raise RuntimeError(
            "Bearer private-fixture-token: private-fixture-document /private-fixture/path"
        )

    monkeypatch.setattr(service, "parse_pdf", failing_parser)
    with pytest.raises(FileValidationException, match="Check the file and try again") as error:
        service.parse(b"mock PDF", "pdf")
    assert "private-fixture" not in str(error.value)
    assert "private-fixture" not in "".join(traceback.format_exception(error.value))
    assert "private-fixture" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
