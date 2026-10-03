"""Deterministic, extractive document context selection without model calls."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

_TRUNCATED = "[TRUNCATED CONTEXT: source text is omitted; do not infer missing facts.]\n"
_GAP = "\n[... source text omitted ...]\n"
_UNIT_CHARS = 1200
_MAX_SELECTION_PASSES = 64
_KEY_CONTENT = re.compile(
    r"\b(methods?|methodology|algorithm|architecture|propos\w*|framework|loss|objective|"
    r"results?|ablation|baseline|accuracy|precision|recall|f1|auc|outperform\w*|"
    r"evaluation|experiments?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    priority: int
    atomic: bool = False


def _merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _render(content: str, ranges: list[tuple[int, int]]) -> str:
    parts = []
    previous = 0
    for start, end in ranges:
        if start > previous:
            parts.append(_GAP)
        parts.append(content[start:end])
        previous = end
    if previous < len(content):
        parts.append(_GAP)
    return "".join(parts)


def _text_candidates(content: str, start: int, end: int) -> list[_Candidate]:
    candidates = []
    for match in re.finditer(r".+?(?:\n\s*\n|\Z)", content[start:end], re.DOTALL):
        left, right = start + match.start(), start + match.end()
        while left < right:
            stop = min(left + _UNIT_CHARS, right)
            if stop < right:
                boundary = content.rfind(" ", left + _UNIT_CHARS // 2, stop)
                if boundary != -1:
                    stop = boundary + 1
            score = min(8, len(_KEY_CONTENT.findall(content[left:stop])))
            if (
                candidates
                and candidates[-1].priority == score
                and stop - candidates[-1].start <= _UNIT_CHARS
            ):
                candidates[-1] = _Candidate(candidates[-1].start, stop, score)
            else:
                candidates.append(_Candidate(left, stop, score))
            left = stop
    return candidates


def _candidates(section: dict) -> list[_Candidate]:
    content = section["content"]
    tables = []
    for block in section.get("blocks", []):
        start, end = block.get("start"), block.get("end")
        if (
            block.get("type") == "table"
            and type(start) is int
            and type(end) is int
            and 0 <= start < end <= len(content)
        ):
            tables.append((start, end, block.get("row_spans", [])))

    # Legacy TXT/Markdown sections have no structured blocks. Recognize table
    # runs, but never assume their first row is a header or synthesize cells.
    if not tables:
        rows = list(re.finditer(r"(?m)^(?:[^\n]*\t[^\n]*|\|[^\n]*\|[ \t]*)(?:\n|\Z)", content))
        for row in rows:
            span = {"start": row.start(), "end": row.end()}
            if tables and tables[-1][1] == row.start():
                start, _, row_spans = tables[-1]
                row_spans.append(span)
                tables[-1] = (start, row.end(), row_spans)
            else:
                tables.append((row.start(), row.end(), [span]))

    candidates = []
    cursor = 0
    for start, end, rows in sorted(tables):
        if start < cursor:
            continue
        candidates.extend(_text_candidates(content, cursor, start))
        candidates.append(_Candidate(start, end, 20, atomic=True))
        valid_rows = []
        for row in rows:
            left, right = row.get("start"), row.get("end")
            if type(left) is int and type(right) is int and start <= left < right <= end:
                valid_rows.append((left, right))
        groups: list[tuple[int, int]] = []
        for left, right in valid_rows:
            if groups and right - groups[-1][0] <= _UNIT_CHARS:
                groups[-1] = (groups[-1][0], right)
            else:
                groups.append((left, right))
        candidates.extend(_Candidate(a, b, 12, atomic=True) for a, b in groups)
        # Keep a bounded, evenly spaced row fallback for budgets smaller than
        # a group, without quadratic selection over thousands of tiny rows.
        count = min(32, len(valid_rows))
        for i in range(count):
            a, b = valid_rows[i * (len(valid_rows) - 1) // max(1, count - 1)]
            candidates.append(_Candidate(a, b, 11, atomic=True))
        cursor = end
    candidates.extend(_text_candidates(content, cursor, len(content)))
    return candidates


def _allocate(demands: list[int], weights: list[int], budget: int) -> list[int]:
    """Capped weighted allocation, with deterministic largest-remainder ties."""
    allocations = [0] * len(demands)
    remaining = min(budget, sum(demands))
    while remaining:
        active = [i for i, demand in enumerate(demands) if allocations[i] < demand]
        total_weight = sum(weights[i] for i in active)
        shares = {i: divmod(remaining * weights[i], total_weight) for i in active}
        granted = 0
        for i in active:
            amount = min(demands[i] - allocations[i], shares[i][0])
            allocations[i] += amount
            granted += amount
        remaining -= granted
        if not granted:
            for i in sorted(active, key=lambda i: (-shares[i][1], i))[:remaining]:
                allocations[i] += 1
                remaining -= 1
    return allocations


def _pick(content: str, candidates: list[_Candidate], budget: int) -> list[tuple[int, int]]:
    if len(content) <= budget:
        return [(0, len(content))] if content else []
    ranges: list[tuple[int, int]] = []
    pending = list(candidates)

    def rank(candidate: _Candidate):
        center = (candidate.start + candidate.end) // 2
        distance = min((abs(center - (a + b) // 2) for a, b in ranges), default=0)
        return candidate.priority, distance, -candidate.start

    # Reserve a little space for relevant prose when a long table shares its
    # section. Otherwise row priority could consume the entire section budget.
    if any(c.atomic for c in candidates):
        prose = [c for c in candidates if not c.atomic and c.priority]
        if prose:
            ranges = _pick(content, prose, budget // 3)

    for _ in range(_MAX_SELECTION_PASSES):
        pending = [c for c in pending if not any(a <= c.start and c.end <= b for a, b in ranges)]
        chosen = None
        for candidate in sorted(pending, key=rank, reverse=True):
            trial = _merge([*ranges, (candidate.start, candidate.end)])
            if len(_render(content, trial)) <= budget:
                chosen = candidate
                ranges = trial
                break
        if chosen is None:
            break

    # When whole passages cannot fit, use separated source windows. Atomic
    # table rows are never clipped into misleading partial numeric records.
    pending = [c for c in pending if not c.atomic]
    for remaining_windows in (2, 1):
        uncovered = []
        for candidate in pending:
            cursor = candidate.start
            for left, right in ranges:
                if right <= cursor or left >= candidate.end:
                    continue
                if cursor < left:
                    uncovered.append(_Candidate(cursor, left, candidate.priority))
                cursor = max(cursor, right)
            if cursor < candidate.end:
                uncovered.append(_Candidate(cursor, candidate.end, candidate.priority))
        if not uncovered:
            break
        candidate = max(uncovered, key=rank)
        spare = budget - len(_render(content, ranges)) - 2 * len(_GAP)
        length = min(candidate.end - candidate.start, spare // remaining_windows)
        if length <= 0:
            continue
        keyword = _KEY_CONTENT.search(content, candidate.start, candidate.end)
        if keyword:
            start = max(candidate.start, min(keyword.start() - length // 3, candidate.end - length))
        elif ranges and min(abs(candidate.end - (a + b) // 2) for a, b in ranges) > min(
            abs(candidate.start - (a + b) // 2) for a, b in ranges
        ):
            start = candidate.end - length
        else:
            start = candidate.start
        stop = start + length
        if start > candidate.start:
            boundary = content.find(" ", start, start + length // 3)
            if boundary != -1:
                start = boundary + 1
        if stop < candidate.end:
            boundary = content.rfind(" ", start + (stop - start) // 2, stop)
            if boundary != -1:
                stop = boundary
        trial = _merge([*ranges, (start, stop)])
        if len(_render(content, trial)) <= budget:
            ranges = trial
    return ranges


class ContextService:
    """Select verbatim evidence under a hard character (not token) budget.

    ``select(sections, section_indices=None, *, max_chars=32000)`` returns
    ``text``, excerpt ``sections``, ``source_refs``, ``coverage`` and ``truncated``.
    Use ``text`` directly in the prompt: it includes section IDs and omission
    markers within the budget. Persist ``coverage`` for generation provenance.

    Indices are zero-based original document indices, using ``index`` (or legacy
    ``section_index``) when supplied and list positions otherwise. Pass the full
    list with ``section_indices`` to select legacy sections without renumbering.
    ``None`` selects all; an empty list selects none. Missing/duplicate source
    indices and invalid budgets raise ValueError, never silently select others.
    Offsets are Python string offsets into the unmodified section content.
    Coverage counts body characters; title truncation is reported separately.
    Selection is heuristic, not a claim of complete semantic coverage. Source
    references are scoped to the input document, not globally unique IDs.
    """

    def select(
        self,
        sections: Sequence[dict],
        section_indices: Sequence[int] | None = None,
        *,
        max_chars: int = 32000,
    ) -> dict:
        if type(max_chars) is not int or max_chars < 0:
            raise ValueError("max_chars must be a non-negative integer")
        sources = []
        seen = set()
        for position, section in enumerate(sections):
            index = section.get("index", section.get("section_index", position))
            if type(index) is not int or index < 0 or index in seen:
                raise ValueError("Source section indices must be unique non-negative integers")
            if "section_index" in section and (
                type(section["section_index"]) is not int or section["section_index"] != index
            ):
                raise ValueError("Conflicting source section indices")
            seen.add(index)
            content = section.get("content", section.get("text", ""))
            title = section.get("title", f"Section {index}")
            if not isinstance(content, str) or not isinstance(title, str):
                raise ValueError("Section title and content must be strings")
            sources.append({**section, "index": index, "title": title, "content": content})

        if section_indices is not None and any(
            type(i) is not int or i < 0 for i in section_indices
        ):
            raise ValueError("Requested section indices must be non-negative integers")
        requested = seen if section_indices is None else set(section_indices)
        if requested - seen:
            raise ValueError("Requested section indices do not exist in the source document")
        selected = [s for s in sources if s["index"] in requested]
        headers = []
        for section in selected:
            title = section["title"]
            if len(title) > 160:
                title = title[:160] + " [title truncated]"
            headers.append(f"\n## Section {section['index']}: {title}\n")
        demands = [len(h) + len(s["content"]) + 1 for h, s in zip(headers, selected)]
        full = sum(demands) <= max_chars
        prefix = "" if full else _TRUNCATED
        if len(prefix) > max_chars:
            prefix = "[TRUNCATED]" if max_chars >= len("[TRUNCATED]") else ""
        available = max_chars - len(prefix)
        candidates = (
            [_candidates(s) for s in selected] if not full and available else [[] for _ in selected]
        )
        weights = [
            3 if any(c.atomic for c in units) else 2 if _KEY_CONTENT.search(s["title"]) else 1
            for s, units in zip(selected, candidates)
        ]
        allocations = _allocate(demands, weights, available)

        def extract():
            outputs = []
            for section, header, units, allocation in zip(
                selected, headers, candidates, allocations
            ):
                budget = allocation - len(header) - 1
                ranges = _pick(section["content"], units, budget) if budget >= 0 else []
                included = budget >= 0 and (bool(ranges) or not section["content"])
                body = _render(section["content"], ranges) if included else ""
                rendered = header + body + "\n" if included else ""
                outputs.append((ranges, rendered, body))
            return outputs

        outputs = extract()
        # Give unused capacity (e.g. a table row that did not fit) back to other
        # selected sections. A fixed pass count bounds work and is reproducible.
        for _ in range(2):
            used = [len(rendered) for _, rendered, _ in outputs]
            surplus = available - sum(used)
            if not surplus:
                break
            extra = _allocate([d - u for d, u in zip(demands, used)], weights, surplus)
            revised = [u + e for u, e in zip(used, extra)]
            if revised == allocations:
                break
            allocations = revised
            outputs = extract()

        excerpts = []
        source_refs = []
        coverage_sections = []
        for section, allocation, (ranges, rendered, body) in zip(selected, allocations, outputs):
            index = section["index"]
            included_chars = sum(end - start for start, end in ranges)
            status = (
                "omitted"
                if not rendered
                else "full"
                if included_chars == len(section["content"])
                else "partial"
            )
            refs = [
                {
                    "section_index": index,
                    "source_ref": f"section:{index}:chars:{start}-{end}",
                    "char_start": start,
                    "char_end": end,
                    "quote": section["content"][start:end],
                }
                for start, end in ranges
            ]
            if rendered:
                excerpts.append(
                    {
                        "index": index,
                        "title": section["title"],
                        "content": body,
                        "source_ref": f"section:{index}",
                        "source": section.get("source", {}),
                        "page_start": section.get("page_start"),
                        "page_end": section.get("page_end"),
                        "truncated": status != "full" or len(section["title"]) > 160,
                        "excerpts": refs,
                        "title_truncated": len(section["title"]) > 160,
                    }
                )
                source_refs.extend(refs)
            coverage_sections.append(
                {
                    "section_index": index,
                    "source_ref": f"section:{index}",
                    "status": status,
                    "original_chars": len(section["content"]),
                    "included_chars": included_chars,
                    "omitted_chars": len(section["content"]) - included_chars,
                    "allocated_chars": allocation,
                    "title_truncated": len(section["title"]) > 160,
                    "ranges": [{"start": start, "end": end} for start, end in ranges],
                }
            )

        truncated = any(s["status"] != "full" or s["title_truncated"] for s in coverage_sections)
        text = prefix + "".join(rendered for _, rendered, _ in outputs)
        original_chars = sum(s["original_chars"] for s in coverage_sections)
        included_chars = sum(s["included_chars"] for s in coverage_sections)
        return {
            "text": text,
            "sections": excerpts,
            "source_refs": source_refs,
            "truncated": truncated,
            "coverage": {
                "selection_method": "deterministic_extractive_v1",
                "budget_unit": "characters",
                "max_chars": max_chars,
                "used_chars": len(text),
                "truncated": truncated,
                "selected_section_indices": [s["index"] for s in selected],
                "included_section_indices": [s["index"] for s in excerpts],
                "omitted_section_indices": [
                    s["section_index"] for s in coverage_sections if s["status"] == "omitted"
                ],
                "unselected_section_indices": [
                    s["index"] for s in sources if s["index"] not in requested
                ],
                "original_chars": original_chars,
                "included_chars": included_chars,
                "omitted_chars": original_chars - included_chars,
                "coverage_ratio": included_chars / original_chars if original_chars else 1.0,
                "sections": coverage_sections,
            },
        }
