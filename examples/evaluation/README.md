# Offline FigureSpec Evaluation

These fixed fixtures are original educational content authored for this repository.
They are not copied papers, public model benchmarks, or evidence of measured model
quality. The score-table fixture contains explicitly fictional teaching values.
No fixture or test calls a model, the OpenAI Evals API, or any hosted service.

## API

```python
import json
from pathlib import Path

from app.services.figure_evaluation_service import FigureEvaluationService

# Run from backend/, using the backend virtual environment.
fixture = json.loads(Path("../examples/evaluation/illustrative-scores.json").read_text())
candidate = fixture["reference_spec"]  # Replace with a candidate FigureSpec dict.
report = FigureEvaluationService().evaluate(candidate, fixture)
assert report["passed"]
```

Exact signature:
`FigureEvaluationService.evaluate(spec: FigureSpec | dict, fixture: dict) -> dict`.
The report is JSON-serializable and has `version`, `fixture_id`, `passed`,
`structural`, `grounding`, and `aesthetic` fields. Each evaluated category has
`status` (`passed` or `failed`) and `checks`; each check has `name`, `status`,
`checked`, and `issues`. Issues contain stable `code` and `path` strings rather
than raw source text or candidate values. Invalid candidates return failed schema
reports with grounding `not_evaluated`. Invalid fixture definitions raise
`ValueError`. Inputs are not mutated.

Each fixture contains `version: 1`, `id`, `description`, `sections` (explicit
original `index`, `title`, and `content`), `required_labels`, and `required_edges`.
An edge requirement contains `source_label`, `target_label`, `label`, and `kind`.
`allowed_numeric_text` lists exact approved visible numeric wording, with only
whitespace normalization. Its default empty list forbids numeric outcomes.
Approved wording must also occur in a fixture source section.
`reference_spec` is an optional hand-authored known-good example for regression
tests, not a model output. Section IDs need not be contiguous or list positions.

## What Is Checked

- **Structure:** FigureSpec schema validity, exact node-label multiplicities,
  and exact directed edge tuples including labels and data/control/skip kinds.
  Missing, additional, duplicate, reversed, and relabeled edges fail. Node IDs
  can change without changing the graph's meaning. Label case and spacing are
  intentionally exact; synonyms do not silently pass.
- **Source references:** Every node and edge must cite a nonblank quote from
  the stated original section. Only whitespace is normalized for quote matching.
  A real quote from the wrong section fails. Quote existence alone is not proof
  that the cited passage entails the node or edge's meaning.
- **Numeric grounding:** Numeric-bearing visible fields must match the fixture's
  explicit approved wording and preserve complete, contiguous,
  whitespace-normalized source wording, not just reuse a bag of numbers.
  Node/edge labels must occur in their own valid cited quotes. Titles,
  captions, and group labels have no citation field in FigureSpec v1, so they
  are checked against fixture sections. Digits (including Unicode numeric
  characters) and common English number words trigger this conservative check.
  Numeric IDs, schema versions, and section indices are not displayed outcomes.
  Derived numbers, numeric paraphrases, and unsupported measurements fail;
  even a mathematically plausible calculation needs explicit source wording.
- **Aesthetics:** Always `not_evaluated`. No typography, overlap, color, image
  fidelity, or visual appeal score is inferred from a semantic FigureSpec.
  Renderer checks and human visual review remain separate requirements.

`passed` means only that these fixed structural and lexical grounding checks
passed. It does not certify all factual claims, semantic entailment, aesthetic
quality, or general performance. The numeric check is deliberately conservative,
not an unrestricted natural-language claim verifier.

## Fixtures and Tests

| Fixture | Purpose |
| --- | --- |
| `retrieval-routing` | Linear information flow with no reported numeric outcomes |
| `branch-and-merge` | Data, control, skip edges, grouping, and sparse section IDs |
| `illustrative-scores` | Fictional table values with explicit model attribution |

From `backend/`, run:

```sh
.venv/bin/pytest tests/test_figure_evaluation.py -q
```

Tests evaluate every known-good fixture, then mutate labels, endpoints, edge
kinds, citations, and numeric claims to assert precise failure categories.
The CI workflow runs the full offline backend suite, Ruff checks for all backend
`app` and `tests` code, and the frontend lockfile install, production build, and required test
script. It uses no repository secrets or hosted evaluation credentials.
