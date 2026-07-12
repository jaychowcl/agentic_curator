# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from typing import Any

from agentic_curator.curators.ontology_harmonizer.harmonization_target_extractor import (
    HarmonizationTargetExtractor,
)


DEFAULT_MAX_CHARS = 500


def build_miniml_metadata_context(
    miniml_json: dict[str, Any] | list[Any] | None,
    *,
    harmonization_targets: list[dict[str, Any]] | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str | None:
    """Build compact, deterministic LLM context from useful MINiML metadata."""
    if max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if not isinstance(miniml_json, (dict, list)) and harmonization_targets is None:
        return None

    if harmonization_targets is None:
        extractor = HarmonizationTargetExtractor()
        target_paths = extractor.build_miniml_sample_target_paths(miniml_json)
        harmonization_targets = extractor.dedupe_targets(
            extractor.extract(miniml_json, start_paths=target_paths)
        )

    packages = [miniml_json] if isinstance(miniml_json, dict) else miniml_json
    title: str | None = None
    for package in packages if isinstance(packages, list) else []:
        if not isinstance(package, dict):
            continue
        series = package.get("series")
        if isinstance(series, dict) and series.get("title") is not None:
            candidate = _compact_value(series["title"])
            if candidate:
                title = candidate
                break

    entries: list[str] = []
    seen: set[tuple[str, str]] = set()
    for target in harmonization_targets:
        if not isinstance(target, dict):
            continue
        field_value = target.get("pre_hz_field")
        label_value = target.get("pre_hz_label")
        if field_value is None or label_value is None:
            continue
        field = _compact_value(field_value)
        label = _compact_value(label_value)
        if not field or not label or (field, label) in seen:
            continue
        seen.add((field, label))
        entries.append(f"{field}={label}")

    context = f"Study: {title}" if title else ""
    if len(context) > max_chars:
        return context[: max_chars - 1].rstrip() + "…"

    appended_entries = 0
    for entry in entries:
        separator = " | " if context and appended_entries == 0 else "; " if context else ""
        candidate = f"{context}{separator}{entry}"
        if len(candidate) <= max_chars:
            context = candidate
            appended_entries += 1
            continue
        if len(entry) <= max_chars:
            break
        available = max_chars - len(context) - len(separator)
        if available > 1:
            context = f"{context}{separator}{entry[: available - 1].rstrip()}…"
        break

    return context or None


def _compact_value(value: Any) -> str:
    return " ".join(str(value).split())
