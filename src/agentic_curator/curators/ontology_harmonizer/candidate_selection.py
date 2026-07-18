# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from typing import Any, Sequence


def preferred_judge_candidates(
    hits: list[dict[str, Any]],
    *,
    preferred_ontology_ids: Sequence[str] = (),
    limit: int,
    reserved_per_ontology: int = 2,
) -> list[dict[str, Any]]:
    """Select a fixed-size judge pool with ordered preferred reservations."""
    if limit < 1:
        return []
    if not preferred_ontology_ids:
        return hits[:limit]

    selected: list[dict[str, Any]] = []
    selected_indexes: set[int] = set()
    for reservation_index in range(reserved_per_ontology):
        for ontology_id in preferred_ontology_ids:
            matches = [
                (index, hit)
                for index, hit in enumerate(hits)
                if str(hit.get("ontology_id", "")) == ontology_id
            ]
            if reservation_index >= len(matches):
                continue
            index, hit = matches[reservation_index]
            if index not in selected_indexes:
                selected.append(hit)
                selected_indexes.add(index)
            if len(selected) == limit:
                return selected

    for index, hit in enumerate(hits):
        if index in selected_indexes:
            continue
        selected.append(hit)
        if len(selected) == limit:
            break
    return selected
