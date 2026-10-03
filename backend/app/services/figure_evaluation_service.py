"""Offline FigureSpec fixture checks, not rendered-image or aesthetic evaluation."""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.schemas.figure_spec import FigureSpec

_NUMBER_WORDS = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"trillion|half|quarter|dozen|twice|double)\b",
    re.IGNORECASE,
)
_SAFE_FIELDS = {
    "version",
    "title",
    "caption",
    "direction",
    "nodes",
    "edges",
    "groups",
    "id",
    "label",
    "role",
    "group_id",
    "source",
    "target",
    "kind",
    "sources",
    "section_index",
    "quote",
}


class _FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Section(_FixtureModel):
    index: int = Field(ge=0, le=100_000)
    title: str = ""
    content: str = Field(min_length=1, max_length=100_000)


class _RequiredEdge(_FixtureModel):
    source_label: str = Field(min_length=1, max_length=240)
    target_label: str = Field(min_length=1, max_length=240)
    label: str = Field(max_length=240)
    kind: Literal["data", "control", "skip"]

    def key(self) -> tuple[str, str, str, str]:
        return self.source_label, self.target_label, self.label, self.kind


class _Fixture(_FixtureModel):
    version: int = Field(ge=1, le=1)
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    description: str = Field(max_length=4000)
    sections: list[_Section] = Field(min_length=1, max_length=64)
    required_labels: list[str] = Field(min_length=1, max_length=100)
    required_edges: list[_RequiredEdge] = Field(max_length=200)
    allowed_numeric_text: list[str] = Field(default_factory=list, max_length=100)
    reference_spec: FigureSpec | None = None

    @model_validator(mode="after")
    def _unambiguous_requirements(self):
        indices = [section.index for section in self.sections]
        if len(set(indices)) != len(indices):
            raise ValueError("fixture section indices must be unique")
        labels = set(self.required_labels)
        if len(labels) != len(self.required_labels) or any(
            not label.strip() or len(label) > 240 for label in labels
        ):
            raise ValueError("fixture node labels must be unique, nonblank, and bounded")
        keys = [edge.key() for edge in self.required_edges]
        if len(set(keys)) != len(keys) or any(
            edge.source_label not in labels or edge.target_label not in labels
            for edge in self.required_edges
        ):
            raise ValueError("fixture edges must be unique and reference required labels")
        numeric_text = [_normalized(text) for text in self.allowed_numeric_text]
        if len(set(numeric_text)) != len(numeric_text) or any(
            not text
            or len(text) > 4000
            or not any(text in _normalized(section.content) for section in self.sections)
            for text in numeric_text
        ):
            raise ValueError("fixture numeric wording must be unique and supported by source text")
        return self


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _check(name: str, issues: list[dict], checked: int) -> dict:
    return {
        "name": name,
        "status": "failed" if issues else "passed",
        "checked": checked,
        "issues": issues,
    }


def _category(checks: list[dict]) -> dict:
    return {
        "status": "failed" if any(c["status"] == "failed" for c in checks) else "passed",
        "checks": checks,
    }


def _path(location: tuple) -> str:
    # Validation errors may include arbitrary extra-field names. Never echo
    # candidate values, quotes, or exception messages into evaluation reports.
    return ".".join(
        str(part) if type(part) is int or part in _SAFE_FIELDS else "field" for part in location
    )


class FigureEvaluationService:
    """Evaluate a candidate against one fixed, original educational fixture.

    ``evaluate(spec: FigureSpec | dict, fixture: dict) -> dict`` is pure,
    deterministic and JSON-serializable. No provider, storage, rendering, or
    network calls are made. Invalid candidates return a failed report; invalid
    fixture definitions raise ValueError with no raw validation details.

    Structural checks use exact node-label multiplicities and directed edge
    tuples (source label, target label, edge label, kind). IDs may be renamed.
    Every node/edge needs a quote from the stated original section index.

    Numeric-bearing fields must match fixture ``allowed_numeric_text`` wording;
    the default empty list forbids all numeric outcomes. Labels additionally
    require that complete normalized wording inside a valid attached quote.
    Numeric title/caption/group text must occur inside a fixture section, since
    those FigureSpec fields have no source references.
    This intentionally rejects unquoted paraphrases or derived numeric values;
    it is a lexical grounding check, not proof of semantic entailment. Numbers
    in IDs, schema versions, and source indices are not displayed outcomes.

    ``passed`` covers structural and grounding checks only. Aesthetics always
    remain ``not_evaluated``: no image, geometry, typography, or color is scored.
    """

    def evaluate(self, spec: FigureSpec | dict, fixture: dict) -> dict:
        try:
            expected = _Fixture.model_validate(fixture)
        except ValidationError:
            raise ValueError("Invalid evaluation fixture definition.") from None

        report = {
            "version": 1,
            "fixture_id": expected.id,
            "passed": False,
            "structural": {"status": "not_evaluated", "checks": []},
            "grounding": {"status": "not_evaluated", "checks": []},
            "aesthetic": {
                "status": "not_evaluated",
                "reason": "No rendered image or layout was inspected; visual review is required.",
                "checks": [],
            },
        }
        try:
            candidate = FigureSpec.model_validate(spec)
        except ValidationError as exc:
            issues = [
                {"code": "invalid_spec", "path": _path(error["loc"])}
                for error in exc.errors(
                    include_input=False,
                    include_context=False,
                    include_url=False,
                )
            ]
            report["structural"] = _category([_check("schema", issues, 1)])
            return report

        expected_labels = Counter(expected.required_labels)
        labels = Counter(node.label for node in candidate.nodes)
        label_issues = []
        for position, label in enumerate(expected.required_labels):
            if labels[label] < expected_labels[label]:
                label_issues.append(
                    {
                        "code": "missing_required_label",
                        "path": f"required_labels.{position}",
                    }
                )
        remaining_labels = expected_labels.copy()
        for index, node in enumerate(candidate.nodes):
            if remaining_labels[node.label] > 0:
                remaining_labels[node.label] -= 1
            else:
                label_issues.append({"code": "unexpected_label", "path": f"nodes.{index}.label"})

        node_labels = {node.id: node.label for node in candidate.nodes}
        expected_edges = Counter(edge.key() for edge in expected.required_edges)
        actual_keys = [
            (node_labels[edge.source], node_labels[edge.target], edge.label, edge.kind)
            for edge in candidate.edges
        ]
        actual_edges = Counter(actual_keys)
        edge_issues = []
        for index, edge in enumerate(expected.required_edges):
            if actual_edges[edge.key()] < expected_edges[edge.key()]:
                edge_issues.append(
                    {"code": "missing_required_edge", "path": f"required_edges.{index}"}
                )
        remaining_edges = expected_edges.copy()
        for index, key in enumerate(actual_keys):
            if remaining_edges[key] > 0:
                remaining_edges[key] -= 1
            else:
                edge_issues.append({"code": "unexpected_edge", "path": f"edges.{index}"})
        report["structural"] = _category(
            [
                _check("schema", [], 1),
                _check("exact_labels", label_issues, len(candidate.nodes)),
                _check("exact_edges", edge_issues, len(candidate.edges)),
            ]
        )

        section_texts = {
            section.index: _normalized(section.content) for section in expected.sections
        }
        source_issues = []
        source_count = 0
        numeric_fields = [
            ("title", candidate.title, list(section_texts.values())),
            ("caption", candidate.caption, list(section_texts.values())),
        ]
        for collection_name in ("nodes", "edges"):
            for index, item in enumerate(getattr(candidate, collection_name)):
                path = f"{collection_name}.{index}"
                quotes = []
                if not item.sources:
                    source_issues.append({"code": "missing_source", "path": f"{path}.sources"})
                for ref_index, reference in enumerate(item.sources):
                    source_count += 1
                    ref_path = f"{path}.sources.{ref_index}"
                    if reference.section_index not in section_texts:
                        source_issues.append(
                            {
                                "code": "unknown_section_index",
                                "path": f"{ref_path}.section_index",
                            }
                        )
                    elif _normalized(reference.quote) not in section_texts[reference.section_index]:
                        source_issues.append(
                            {"code": "quote_not_in_section", "path": f"{ref_path}.quote"}
                        )
                    else:
                        quotes.append(_normalized(reference.quote))
                numeric_fields.append((f"{path}.label", item.label, quotes))
        numeric_fields.extend(
            (f"groups.{i}.label", group.label, list(section_texts.values()))
            for i, group in enumerate(candidate.groups)
        )
        numeric_issues = []
        numeric_count = 0
        approved_numeric_text = {_normalized(text) for text in expected.allowed_numeric_text}
        for path, text, evidence in numeric_fields:
            if not any(char.isnumeric() for char in text) and not _NUMBER_WORDS.search(text):
                continue
            numeric_count += 1
            normalized = _normalized(text)
            if normalized not in approved_numeric_text or not any(
                normalized in quote for quote in evidence
            ):
                numeric_issues.append({"code": "unsupported_numeric_text", "path": path})
        report["grounding"] = _category(
            [
                _check("source_references", source_issues, source_count),
                _check("numeric_outcomes", numeric_issues, numeric_count),
            ]
        )
        report["passed"] = all(
            report[category]["status"] == "passed" for category in ("structural", "grounding")
        )
        return report
