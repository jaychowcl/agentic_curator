# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

import json
import logging
from importlib.resources import files
from pathlib import Path
from typing import Any

from agentic_curator.curators.json_response import parse_json_response
from agentic_curator.curators.ontology_harmonizer.harmonization_target_extractor import (
    HarmonizationTargetExtractor,
    StartPathSpec,
)
from agentic_curator.curators.ontology_harmonizer.ontology_store import OntoStore
from agentic_curator.curators.ontology_harmonizer.miniml_metadata_context import (
    build_miniml_metadata_context,
)
from agentic_curator.curators.ontology_harmonizer.request_policy import RequestPolicy, request_with_retry
from agentic_curator.curators.ontology_harmonizer.strategy_handlers import (
    OlsClient,
    OlsStrategyHandler,
)
from agentic_curator.wrappers import LLM


PROMPT_PACKAGE = "agentic_curator.curators.ontology_harmonizer"
LOGGER = logging.getLogger(__name__)


class OntologyHarmonizer:
    """Curator for harmonizing publication metadata against ontologies."""

    DEFAULT_TARGET_PATHS = HarmonizationTargetExtractor.DEFAULT_TARGET_PATHS
    LLM_CANDIDATE_LIMIT = 10
    METADATA_CONTEXT_MAX_CHARS = 500
    WORKFLOW = "local_rag_ols"

    def __init__(
        self,
        ontostore: OntoStore | None = None,
        llm: Any | None = None,
        request_policy: RequestPolicy | None = None,
    ) -> None:
        self.request_policy = request_policy or getattr(ontostore, "request_policy", None) or RequestPolicy()
        self.ontostore = OntoStore(request_policy=self.request_policy) if ontostore is None else ontostore
        self.llm = llm
        self.target_extractor = HarmonizationTargetExtractor()

    def harmonize(
        self,
        publication_context: str | None = None,
        metadata_context: str | None = None,
        harmonization_targets: dict[str, Any] | list[dict[str, Any]] | None = None,
        target: dict[str, Any] | None = None,
        ontostore: OntoStore | None = None,
        target_paths: list[StartPathSpec] | None = None,
        lookup_llm_judge: bool = True,
        search_llm_judge: bool = True,
        llm: bool = True,
    ) -> dict[str, Any]:
        LOGGER.info("Starting ontology harmonization.")
        effective_ontostore = self._effective_ontostore(ontostore)
        normalized_targets = self._normalize_targets(
            harmonization_targets=harmonization_targets,
            target=target,
        )
        LOGGER.debug(
            "Ontology harmonization using strategy %s for %d targets.",
            self.WORKFLOW,
            len(normalized_targets),
        )
        for normalized_target in normalized_targets:
            self._clear_harmonization_skip(normalized_target)
            self._harmonize_target(normalized_target, effective_ontostore)
            lookup = self.lookup_label(
                normalized_target,
                publication_context=publication_context,
                ontostore=effective_ontostore,
                lookup_llm_judge=lookup_llm_judge and llm,
                **self._metadata_context_kwargs(metadata_context),
            )
            if self._is_harmonization_skipped(normalized_target):
                continue
            if not lookup and llm:
                lookup = self.lookup_rag_label(
                    normalized_target,
                    publication_context=publication_context,
                    ontostore=effective_ontostore,
                    lookup_llm_judge=lookup_llm_judge,
                    **self._metadata_context_kwargs(metadata_context),
                )
            if self._is_harmonization_skipped(normalized_target):
                continue

            if not lookup:
                LOGGER.info(
                    "Ontology lookup missed for target %s.",
                    normalized_target.get("id"),
                )
                self._mark_ontology_miss(normalized_target)

            if not lookup:
                ols_result = self.harmonize_label(
                    normalized_target,
                    publication_context=publication_context,
                    ontostore=effective_ontostore,
                    search_llm_judge=search_llm_judge and llm,
                    **self._metadata_context_kwargs(metadata_context),
                )
                if ols_result.get("status") == "matched":
                    self._lookup_harmonized_label(
                        normalized_target,
                        ontostore=effective_ontostore,
                    )
                elif ols_result.get("status") == "skipped":
                    continue

            self._apply_selected_ontology_label(normalized_target)
            self.harmonize_field(
                normalized_target,
                publication_context=publication_context,
                ontostore=effective_ontostore,
                llm=llm,
                **self._metadata_context_kwargs(metadata_context),
            )

        matched = sum(bool(item.get("ontology_match")) for item in normalized_targets)
        skipped = sum(
            self._is_harmonization_skipped(item) for item in normalized_targets
        )
        LOGGER.info(
            "Completed ontology harmonization. targets=%s matched=%s skipped=%s unmatched=%s workflow=%s.",
            len(normalized_targets),
            matched,
            skipped,
            len(normalized_targets) - matched - skipped,
            self.WORKFLOW,
        )
        return {
            "publication_context": publication_context,
            "metadata_context": metadata_context,
            "harmonization_targets": normalized_targets,
            "workflow": self.WORKFLOW,
            "target_paths": target_paths,
        }

    def harmonize_miniml_json(
        self,
        publication_context: str | None = None,
        miniml_json: dict[str, Any] | list[Any] | None = None,
        ontostore: OntoStore | None = None,
        target_paths: list[StartPathSpec] | None = None,
        lookup_llm_judge: bool = True,
        search_llm_judge: bool = True,
        llm: bool = True,
    ) -> dict[str, Any]:
        LOGGER.info("Starting MINiML JSON ontology harmonization.")
        should_dedupe_targets = target_paths is None
        effective_target_paths = target_paths
        if effective_target_paths is None:
            effective_target_paths = (
                self.target_extractor.build_miniml_sample_target_paths(miniml_json)
            )
        LOGGER.debug("Extracting targets from %d target paths.", len(effective_target_paths))
        harmonization_targets = self.target_extractor.extract(
            miniml_json,
            start_paths=effective_target_paths,
        )
        if should_dedupe_targets:
            harmonization_targets = self.target_extractor.dedupe_targets(
                harmonization_targets
            )
        metadata_context = self._metadata_context_from_miniml(
            miniml_json,
            harmonization_targets,
        )
        result = self.harmonize(
            publication_context=publication_context,
            metadata_context=metadata_context,
            harmonization_targets=harmonization_targets,
            target=None,
            ontostore=ontostore,
            target_paths=effective_target_paths,
            lookup_llm_judge=lookup_llm_judge,
            search_llm_judge=search_llm_judge,
            llm=llm,
        )
        applied_targets = result.get("harmonization_targets", harmonization_targets)
        result["miniml_json"] = self.apply_targets(miniml_json, applied_targets)
        LOGGER.info("Completed MINiML JSON ontology harmonization.")
        return result

    def apply_targets(
        self,
        miniml_json: dict[str, Any] | list[Any] | None,
        harmonization_targets: list[dict[str, Any]],
    ) -> dict[str, Any] | list[Any] | None:
        LOGGER.debug("Applying %d harmonization targets.", len(harmonization_targets))
        if not isinstance(miniml_json, (dict, list)) or not isinstance(
            harmonization_targets,
            list,
        ):
            return miniml_json

        for target in harmonization_targets:
            if not isinstance(target, dict):
                continue
            if self._is_harmonization_skipped(target):
                continue
            for occurrence in self._target_occurrences(target):
                self._apply_target_occurrence(miniml_json, target, occurrence)

        return miniml_json

    def _normalize_targets(
        self,
        *,
        harmonization_targets: dict[str, Any] | list[dict[str, Any]] | None = None,
        target: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if target is not None and harmonization_targets is not None:
            raise ValueError("Provide either target or harmonization_targets, not both.")

        if target is not None:
            return [target]

        if harmonization_targets is None:
            return []

        if isinstance(harmonization_targets, dict):
            return [harmonization_targets]

        return harmonization_targets

    def _target_occurrences(self, target: dict[str, Any]) -> list[dict[str, Any]]:
        occurrences = target.get("occurrences")
        if isinstance(occurrences, list):
            return [
                occurrence
                for occurrence in occurrences
                if isinstance(occurrence, dict)
            ]

        if {
            "pre_hz_field_path",
            "pre_hz_label_path",
            "parent_path",
        }.issubset(target):
            return [target]

        return []

    def _apply_target_occurrence(
        self,
        miniml_json: dict[str, Any] | list[Any],
        target: dict[str, Any],
        occurrence: dict[str, Any],
    ) -> None:
        applied = self._target_applied_values(target, occurrence)
        if applied is None:
            return

        field_path = occurrence.get("pre_hz_field_path")
        label_path = occurrence.get("pre_hz_label_path")
        parent_path = occurrence.get("parent_path")
        if not all(
            isinstance(path, str)
            for path in (field_path, label_path, parent_path)
        ):
            return

        parent = self._resolve_json_pointer(miniml_json, parent_path)
        if not isinstance(parent, dict):
            return

        if field_path == label_path:
            original_field = self._field_name_from_path(field_path)
            if original_field is None or original_field not in parent:
                return
            self._apply_scalar_fields(parent, applied)
            return

        if self._is_tag_value_occurrence(parent, field_path, label_path):
            self._apply_tag_value_rows(miniml_json, parent_path, applied)
            return

        self._apply_container_value(miniml_json, field_path, applied)

    def _target_applied_values(
        self,
        target: dict[str, Any],
        occurrence: dict[str, Any],
    ) -> dict[str, Any] | None:
        hz_field = target.get("hz_field", occurrence.get("hz_field"))
        hz_label = target.get("hz_label", occurrence.get("hz_label"))
        if hz_field is None or hz_label is None:
            return None

        field_key = str(hz_field)
        applied = {
            "field_key": field_key,
            "label": hz_label,
        }
        ontology_term_id = self._target_ontology_term_id(target)
        if ontology_term_id is not None:
            applied["id"] = ontology_term_id
        ontology_id = self._target_ontology_id(target)
        if ontology_id is not None:
            applied["onto"] = ontology_id

        return applied

    @classmethod
    def _apply_scalar_fields(
        cls,
        parent: dict[str, Any],
        applied: dict[str, Any],
    ) -> None:
        for suffix in cls._scalar_suffixes():
            entries = cls._scalar_entries(applied, suffix=suffix)
            if all(parent.get(key) == value for key, value in entries.items()):
                return
            if any(key in parent for key in entries):
                continue
            parent.update(entries)
            return

    @staticmethod
    def _scalar_suffixes() -> Any:
        yield ""
        index = 1
        while True:
            yield f"_{index}"
            index += 1

    @staticmethod
    def _scalar_entries(
        applied: dict[str, Any],
        *,
        suffix: str,
    ) -> dict[str, Any]:
        field_key = applied["field_key"]
        entries = {f"hz_{field_key}{suffix}": applied["label"]}
        if "id" in applied:
            entries[f"hz_{field_key}_id{suffix}"] = applied["id"]
        if "onto" in applied:
            entries[f"hz_{field_key}_onto{suffix}"] = applied["onto"]
        return entries

    @staticmethod
    def _is_tag_value_occurrence(
        parent: dict[str, Any],
        field_path: str,
        label_path: str,
    ) -> bool:
        return (
            field_path.endswith("/tag")
            and label_path.endswith("/value")
            and "tag" in parent
            and "value" in parent
        )

    def _apply_tag_value_rows(
        self,
        miniml_json: dict[str, Any] | list[Any],
        parent_path: str,
        applied: dict[str, Any],
    ) -> None:
        list_path = self._parent_path(parent_path)
        container = self._resolve_json_pointer(miniml_json, list_path)
        if not isinstance(container, list):
            return

        for row in self._tag_value_rows(applied):
            if row not in container:
                container.append(row)

    @staticmethod
    def _tag_value_rows(applied: dict[str, Any]) -> list[dict[str, Any]]:
        field_key = applied["field_key"]
        rows = [{"tag": f"hz_{field_key}", "value": applied["label"]}]
        if "id" in applied:
            rows.append({"tag": f"hz_{field_key}_id", "value": applied["id"]})
        if "onto" in applied:
            rows.append({"tag": f"hz_{field_key}_onto", "value": applied["onto"]})
        return rows

    def _apply_container_value(
        self,
        miniml_json: dict[str, Any] | list[Any],
        field_path: str,
        applied: dict[str, Any],
    ) -> None:
        container_parent_path = self._parent_path(field_path)
        container_parent = self._resolve_json_pointer(
            miniml_json,
            container_parent_path,
        )
        if not isinstance(container_parent, dict):
            return

        key = f"hz_{applied['field_key']}"
        container = container_parent.get(key)
        if not isinstance(container, list):
            container = []
            container_parent[key] = container

        entry = self._container_value_entry(applied)
        if entry not in container:
            container.append(entry)

    @staticmethod
    def _container_value_entry(applied: dict[str, Any]) -> dict[str, Any]:
        entry = {"value": applied["label"]}
        if "id" in applied:
            entry["id"] = applied["id"]
        if "onto" in applied:
            entry["onto"] = applied["onto"]
        return entry

    @staticmethod
    def _target_ontology_term_id(target: dict[str, Any]) -> Any:
        lookup = target.get("ontology_lookup")
        if not isinstance(lookup, dict):
            return None

        term_id = lookup.get("id")
        if term_id is not None:
            return term_id
        return lookup.get("accession")

    @staticmethod
    def _target_ontology_id(target: dict[str, Any]) -> Any:
        ontology_id = target.get("ontology_id")
        if ontology_id is not None:
            return ontology_id

        lookup = target.get("ontology_lookup")
        if isinstance(lookup, dict):
            return lookup.get("ontology_id")
        return None

    @classmethod
    def _field_name_from_path(cls, path: str) -> str | None:
        if path == "":
            return None
        return cls._unescape_json_pointer_segment(path.rsplit("/", 1)[-1])

    @staticmethod
    def _parent_path(path: str) -> str:
        if "/" not in path.strip("/"):
            return ""
        return path.rsplit("/", 1)[0]

    @classmethod
    def _resolve_json_pointer(
        cls,
        value: dict[str, Any] | list[Any],
        pointer: str,
    ) -> Any:
        if pointer == "":
            return value
        if not pointer.startswith("/"):
            return None

        current: Any = value
        for raw_segment in pointer.split("/")[1:]:
            segment = cls._unescape_json_pointer_segment(raw_segment)
            if isinstance(current, dict):
                if segment not in current:
                    return None
                current = current[segment]
                continue

            if isinstance(current, list):
                if not segment.isdecimal():
                    return None
                index = int(segment)
                if index >= len(current):
                    return None
                current = current[index]
                continue

            return None

        return current

    @staticmethod
    def _unescape_json_pointer_segment(segment: str) -> str:
        return segment.replace("~1", "/").replace("~0", "~")

    def lookup_label(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        metadata_context: str | None = None,
        ontostore: OntoStore,
        lookup_llm_judge: bool = True,
    ) -> Any:
        self._harmonize_target(target, ontostore)
        label = target.get("hz_label")
        if label is None:
            LOGGER.info("Skipping ontology lookup because target has no hz_label.")
            return False

        exact_hits: list[dict[str, Any]] = []
        fts_hits: list[dict[str, Any]] = []
        ranking: list[dict[str, Any]] = []
        candidate_ontology_ids = self._candidate_ontology_ids(target, ontostore)
        LOGGER.debug(
            "Looking up label %r across ontology IDs: %s.",
            label,
            candidate_ontology_ids,
        )
        for ontology_id in candidate_ontology_ids:
            details = ontostore.lookup_with_metadata(str(label), ontology_id)
            if details["match_type"] == "exact":
                exact_hits.extend(details["hits"])
            elif details["match_type"] == "fts":
                fts_hits.extend(details["hits"])
                ranking.extend(details["ranking"])

        match_type = "exact" if exact_hits else "fts" if fts_hits else "none"
        hits = exact_hits or fts_hits

        if not hits:
            return False

        target["ontology_lookup_match_type"] = match_type
        if ranking:
            target["ontology_lookup_ranking"] = ranking
        if match_type == "fts" and not lookup_llm_judge:
            target["ontology_lookup_candidates"] = hits
            return False

        lookup = self._select_lookup_hit(
            target=target,
            publication_context=publication_context,
            metadata_context=metadata_context,
            hits=hits,
            lookup_llm_judge=lookup_llm_judge,
            source="local",
        )
        if not lookup:
            return False
        target["ontology_id"] = lookup["ontology_id"]
        target["ontology_lookup"] = lookup
        target["ontology_lookup_hits"] = hits
        target["ontology_match"] = True
        LOGGER.info(
            "Ontology lookup matched target %s with %d hits.",
            target.get("id"),
            len(hits),
        )
        return lookup

    def _select_lookup_hit(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        metadata_context: str | None = None,
        hits: list[dict[str, Any]],
        lookup_llm_judge: bool,
        source: str,
    ) -> dict[str, Any] | bool:
        if not lookup_llm_judge:
            return hits[0]

        LOGGER.info("Judging %d ontology lookup hits with LLM.", len(hits))
        judged_hits = hits[: self.LLM_CANDIDATE_LIMIT]
        judgement = self.judge_lookup(
            target,
            publication_context=publication_context,
            metadata_context=metadata_context,
            hits=judged_hits,
        )
        target["ontology_lookup_judgement"] = judgement
        target.setdefault("ontology_lookup_judgements", []).append(
            {"source": source, **judgement}
        )
        decision = str(judgement["decision"])
        if decision.lower() == "no_match":
            return False
        if decision.lower() == "false":
            self._mark_harmonization_skip(
                target,
                stage="rag_judge" if source == "rag" else "lookup_judge",
                judgement=judgement,
            )
            return False
        for hit in judged_hits:
            if str(hit.get("id")) == decision:
                return hit

        raise ValueError(
            "LLM lookup judgement decision must match a known lookup hit id."
        )

    def lookup_rag_label(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        metadata_context: str | None = None,
        ontostore: OntoStore,
        lookup_llm_judge: bool = True,
    ) -> Any:
        """Run semantic lookup across cached local ontology frameworks."""
        label = target.get("hz_label")
        if label is None:
            return False
        hits: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        frameworks = self._candidate_ontology_ids(target, ontostore)
        for ontology_id in frameworks:
            try:
                hits.extend(
                    ontostore.lookup_rag(
                        str(label), ontology_id, top_k=self.LLM_CANDIDATE_LIMIT
                    )
                )
            except Exception as exc:  # noqa: BLE001 - preserve local RAG trace.
                errors.append({"ontology_id": ontology_id, "error": str(exc)})
        hits = sorted(
            self._dedupe_semantic_hits(hits),
            key=lambda hit: float(hit.get("rag_score", 0.0)),
            reverse=True,
        )[: self.LLM_CANDIDATE_LIMIT]
        target["ontology_rag"] = {
            "status": "candidates" if hits else "error" if errors else "missed",
            "frameworks": frameworks,
            "hits": hits,
            **({"errors": errors} if errors else {}),
        }
        if not hits or not lookup_llm_judge:
            return False
        selected = self._select_lookup_hit(
            target=target,
            publication_context=publication_context,
            metadata_context=metadata_context,
            hits=hits,
            lookup_llm_judge=True,
            source="rag",
        )
        if not selected:
            target["ontology_rag"]["status"] = (
                "skipped" if self._is_harmonization_skipped(target) else "no_match"
            )
            return False
        target["ontology_id"] = selected["ontology_id"]
        target["ontology_lookup"] = selected
        target["ontology_lookup_hits"] = hits
        target["ontology_lookup_match_type"] = "rag"
        target["ontology_match"] = True
        target["ontology_rag"]["status"] = "matched"
        return selected

    @staticmethod
    def _dedupe_semantic_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            key = str(hit.get("id") or hit.get("accession") or hit.get("iri"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(hit)
        return deduped

    def judge_lookup(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        metadata_context: str | None = None,
        hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._judge_lookup_prompt(
            target=target,
            publication_context=publication_context,
            metadata_context=metadata_context,
            hits=hits,
        )
        response = self._generate_response(
            prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": self._lookup_judge_response_schema(),
            },
        )
        judgement = parse_json_response(response)
        self._validate_lookup_judge_response(judgement)
        return judgement

    def judge_search_results(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        metadata_context: str | None = None,
        stage: str,
        restricted_hits: list[dict[str, Any]],
        unrestricted_hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._judge_search_prompt(
            target=target,
            publication_context=publication_context,
            metadata_context=metadata_context,
            stage=stage,
            restricted_hits=restricted_hits,
            unrestricted_hits=unrestricted_hits,
        )
        response = self._generate_response(
            prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": self._search_judge_response_schema(),
            },
        )
        judgement = parse_json_response(response)
        self._validate_search_judge_response(judgement)
        return judgement

    def assign_onto_framework(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        metadata_context: str | None = None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
        LOGGER.info("Assigning ontology framework with LLM.")
        self._mark_ontology_miss(target)
        framework_configs = self._assignment_candidate_frameworks(target, ontostore)
        prompt = self._assign_onto_framework_prompt(
            target=target,
            publication_context=publication_context,
            metadata_context=metadata_context,
            ontology_frameworks=framework_configs,
        )
        response = self._generate_response(
            prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": self._assign_onto_framework_response_schema(),
            },
        )
        assignment = parse_json_response(response)
        self._validate_assignment_response(assignment)
        target["ontology_framework_assignment"] = assignment

        decision = str(assignment["decision"])
        if decision in framework_configs:
            target["ontology_id"] = decision

        return assignment

    def harmonize_field(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        metadata_context: str | None = None,
        ontostore: OntoStore,
        llm: bool = True,
    ) -> Any:
        self._harmonize_target(target, ontostore)
        field = target.get("hz_field")
        if field is None:
            LOGGER.info("Skipping field harmonization because target has no hz_field.")
            return False

        lookup = ontostore.lookup_fields(field)
        if lookup:
            target["hz_field"] = lookup["field"]
            target["field_lookup"] = lookup
            LOGGER.info("Field harmonization matched %s.", lookup["field"])
            return lookup

        if llm:
            LOGGER.info("Assigning field with LLM.")
            return self.assign_field(
                target,
                publication_context=publication_context,
                metadata_context=metadata_context,
                ontostore=ontostore,
            )
        return False

    def assign_field(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        metadata_context: str | None = None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
        LOGGER.info("Assigning harmonized field with LLM.")
        prompt = self._assign_field_prompt(
            target=target,
            publication_context=publication_context,
            metadata_context=metadata_context,
            fields=ontostore.fields,
        )
        response = self._generate_response(
            prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": self._assign_field_response_schema(),
            },
        )
        assignment = parse_json_response(response)
        self._validate_field_assignment_response(assignment)
        target["field_assignment"] = assignment

        decision = ontostore.harmonize_key(assignment["decision"])
        target["hz_field"] = decision
        if assignment["new_field"]:
            ontostore.add_field(decision, {
                "label": decision,
                "source": "llm",
                "confidence": assignment["confidence"],
                "reason": assignment["reason"],
                "review_status": "unreviewed",
            }, replace=True)

        return assignment

    def harmonize_label(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        metadata_context: str | None = None,
        ontostore: OntoStore,
        search_llm_judge: bool = True,
    ) -> dict[str, Any]:
        LOGGER.info("Running OLS ontology lookup.")
        handler = OlsStrategyHandler(
            ols_client=OlsClient(request_policy=self.request_policy, cache_store=ontostore),
            search_judge=(self.judge_search_results if search_llm_judge else None),
        )
        return handler.handle(
            target,
            publication_context=publication_context,
            ontostore=ontostore,
            **self._metadata_context_kwargs(metadata_context),
        )

    def _llm(self) -> Any:
        if self.llm is None:
            self.llm = LLM()

        return self.llm

    def _generate_response(self, *args: Any, **kwargs: Any) -> Any:
        response, trace = request_with_retry(
            lambda: self._llm().generate_response(*args, **kwargs),
            self.request_policy,
        )
        self.last_request_trace = trace
        return response

    def _effective_ontostore(self, ontostore: OntoStore | None = None) -> OntoStore:
        effective_ontostore = self.ontostore if ontostore is None else ontostore
        if not isinstance(effective_ontostore, OntoStore):
            raise TypeError("ontostore must be an OntoStore.")
        return effective_ontostore

    def _extract_harmonization_targets(
        self,
        metadata: str | dict[str, Any] | list[Any] | None,
        start_paths: list[StartPathSpec] | None = None,
    ) -> list[dict[str, Any]]:
        return self.target_extractor.extract(metadata, start_paths=start_paths)

    def _metadata_context_from_miniml(
        self,
        miniml_json: dict[str, Any] | list[Any] | None,
        harmonization_targets: list[dict[str, Any]],
    ) -> str | None:
        """Build compact context while preserving the compatibility method."""
        return build_miniml_metadata_context(
            miniml_json,
            harmonization_targets=harmonization_targets,
            max_chars=self.METADATA_CONTEXT_MAX_CHARS,
        )

    @staticmethod
    def _metadata_context_kwargs(metadata_context: str | None) -> dict[str, str]:
        return {} if metadata_context is None else {"metadata_context": metadata_context}

    def _candidate_ontology_ids(
        self,
        target: dict[str, Any],
        ontostore: OntoStore,
    ) -> list[str]:
        configured_ids = target.get("ontology_frameworks", target.get("ontology_ids"))
        if configured_ids is not None:
            return self._normalize_ontology_ids(configured_ids)

        return [
            ontology_id
            for ontology_id, framework in ontostore.ontology_frameworks.items()
            if self._framework_has_local_file(framework)
        ]

    def _lookup_harmonized_label(
        self,
        target: dict[str, Any],
        *,
        ontostore: OntoStore,
    ) -> Any:
        selected = target.get("ontology_lookup")
        if not isinstance(selected, dict):
            target["ontology_local_enrichment"] = {"status": "skipped", "reason": "no_selected_term"}
            return False

        ontology_id = str(selected.get("ontology_id") or target.get("ontology_id") or "")
        identifiers = self._term_identifiers(selected)
        if not ontology_id or not identifiers:
            target["ontology_local_enrichment"] = {"status": "skipped", "reason": "no_selected_identifier"}
            return False

        for identifier in identifiers:
            for candidate in ontostore.lookup_exact(identifier, ontology_id):
                if identifiers.isdisjoint(self._term_identifiers(candidate)):
                    continue
                # Local data may enrich the selected term, but the judged identity wins.
                enriched = {**candidate, **selected}
                target["ontology_lookup"] = enriched
                target["ontology_id"] = ontology_id
                target["ontology_match"] = True
                target["ontology_local_enrichment"] = {
                    "status": "matched",
                    "identifier": identifier,
                    "ontology_id": ontology_id,
                }
                return enriched

        target["ontology_local_enrichment"] = {
            "status": "missed",
            "ontology_id": ontology_id,
            "identifiers": sorted(identifiers),
        }
        return False

    @staticmethod
    def _apply_selected_ontology_label(target: dict[str, Any]) -> str | None:
        lookup = target.get("ontology_lookup")
        if not isinstance(lookup, dict):
            return None
        title = lookup.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        canonical_label = " ".join(title.split())
        target["hz_label"] = canonical_label
        occurrences = target.get("occurrences")
        if isinstance(occurrences, list):
            for occurrence in occurrences:
                if isinstance(occurrence, dict):
                    occurrence["hz_label"] = canonical_label
        return canonical_label

    @staticmethod
    def _term_identifiers(term: dict[str, Any]) -> set[str]:
        values = []
        for key in ("id", "accession", "iri"):
            value = term.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip().lower())
        return set(values)

    def _post_strategy_ontology_ids(
        self,
        target: dict[str, Any],
        ontostore: OntoStore,
    ) -> list[str]:
        ontology_ids = []
        stored_ontology_id = target.get("ontology_id")
        if (
            stored_ontology_id is not None
            and str(stored_ontology_id) in ontostore.ontology_frameworks
        ):
            ontology_ids.append(str(stored_ontology_id))

        for ontology_id in self._candidate_ontology_ids(target, ontostore):
            if ontology_id not in ontostore.ontology_frameworks:
                continue
            if ontology_id in ontology_ids:
                continue
            ontology_ids.append(ontology_id)

        return ontology_ids

    def _assignment_candidate_frameworks(
        self,
        target: dict[str, Any],
        ontostore: OntoStore,
    ) -> dict[str, Any]:
        configured_ids = target.get("ontology_frameworks", target.get("ontology_ids"))
        if configured_ids is None:
            ontology_ids = list(ontostore.ontology_frameworks)
        else:
            ontology_ids = self._normalize_ontology_ids(configured_ids)

        return {
            ontology_id: self._assignment_prompt_framework(
                ontology_id=ontology_id,
                framework=framework,
            )
            for ontology_id, framework in ontostore.ontology_frameworks.items()
            if ontology_id in ontology_ids
        }

    def _assignment_prompt_framework(
        self,
        *,
        ontology_id: str,
        framework: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": ontology_id,
            "title": framework.get("title"),
            "description": framework.get("description"),
        }

    def _normalize_ontology_ids(self, ontology_ids: Any) -> list[str]:
        if isinstance(ontology_ids, str):
            return [ontology_ids]
        if isinstance(ontology_ids, (list, tuple, set)):
            return [str(ontology_id) for ontology_id in ontology_ids]
        return []

    def _harmonize_target(
        self,
        target: dict[str, Any],
        ontostore: OntoStore,
    ) -> None:
        self._harmonize_target_fields(target, ontostore)
        occurrences = target.get("occurrences")
        if not isinstance(occurrences, list):
            return

        for occurrence in occurrences:
            if isinstance(occurrence, dict):
                self._harmonize_target_fields(occurrence, ontostore)

    def _harmonize_target_fields(
        self,
        target: dict[str, Any],
        ontostore: OntoStore,
    ) -> None:
        field = target.get("hz_field", target.get("pre_hz_field"))
        if field is not None:
            target["hz_field"] = ontostore.harmonize_key(field)

        label = target.get("hz_label", target.get("pre_hz_label"))
        if label is not None:
            target["hz_label"] = ontostore.harmonize_key(label)

    @staticmethod
    def _clear_harmonization_skip(target: dict[str, Any]) -> None:
        target.pop("harmonization_status", None)
        target.pop("harmonization_skip", None)

    @staticmethod
    def _is_harmonization_skipped(target: dict[str, Any]) -> bool:
        return target.get("harmonization_status") == "skipped"

    @classmethod
    def _mark_harmonization_skip(
        cls,
        target: dict[str, Any],
        *,
        stage: str,
        judgement: dict[str, Any],
    ) -> dict[str, Any]:
        cls._mark_ontology_miss(target)
        skip = {
            "stage": stage,
            "decision": "false",
            "confidence": str(judgement["confidence"]),
            "reason": str(judgement["reason"]),
        }
        target["harmonization_status"] = "skipped"
        target["harmonization_skip"] = skip
        return skip

    def _assign_onto_framework_prompt(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        metadata_context: str | None,
        ontology_frameworks: dict[str, Any],
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/assign_onto_framework.md"
        ).read_text(encoding="utf-8").strip()
        return self._structured_prompt(
            initial_prompt,
            ("Publication Context", publication_context),
            ("Metadata Context", metadata_context),
            ("Harmonization Target", self._semantic_target_context(target)),
            ("Ontology Framework Config", ontology_frameworks),
        )

    def _assign_field_prompt(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        metadata_context: str | None,
        fields: dict[str, Any],
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/assign_field.md"
        ).read_text(encoding="utf-8").strip()
        return self._structured_prompt(
            initial_prompt,
            ("Publication Context", publication_context),
            ("Metadata Context", metadata_context),
            (
                "Harmonization Target",
                self._field_assignment_target_context(target),
            ),
            ("Fields", self._field_prompt_context(fields)),
        )

    def _judge_lookup_prompt(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        metadata_context: str | None,
        hits: list[dict[str, Any]],
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/judge_lookup.md"
        ).read_text(encoding="utf-8").strip()
        return self._structured_prompt(
            initial_prompt,
            ("Publication Context", publication_context),
            ("Metadata Context", metadata_context),
            ("Harmonization Target", self._semantic_target_context(target)),
            ("Lookup Hits", self._candidate_prompt_context(hits)),
        )

    def _judge_search_prompt(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        metadata_context: str | None,
        stage: str,
        restricted_hits: list[dict[str, Any]],
        unrestricted_hits: list[dict[str, Any]],
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/judge_search.md"
        ).read_text(encoding="utf-8").strip()
        hits = restricted_hits if stage == "restricted" else unrestricted_hits
        sections: list[tuple[str, Any]] = [
            ("Publication Context", publication_context),
            ("Metadata Context", metadata_context),
            (
                "Harmonization Target",
                self._semantic_target_context(target, include_ontology_id=True),
            ),
            ("OLS Hits", self._candidate_prompt_context(hits)),
        ]
        return self._structured_prompt(initial_prompt, *sections)

    def _semantic_target_context(
        self,
        target: dict[str, Any],
        *,
        include_ontology_id: bool = False,
    ) -> dict[str, Any]:
        context = {
            "field": target.get("pre_hz_field", target.get("hz_field", "")),
            "label": target.get("pre_hz_label", target.get("hz_label", "")),
        }
        if include_ontology_id and target.get("ontology_id") is not None:
            context["ontology_id"] = target["ontology_id"]
        return context

    def _field_assignment_target_context(
        self,
        target: dict[str, Any],
    ) -> dict[str, Any]:
        context = self._semantic_target_context(target, include_ontology_id=True)
        if target.get("hz_label") is not None:
            context["label"] = target["hz_label"]
        if target.get("pre_hz_label") is not None:
            context["pre_hz_label"] = target["pre_hz_label"]
        return context

    def _field_prompt_context(
        self,
        fields: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        allowed = ("label", "aliases", "description")
        return {
            field_id: {
                key: metadata[key]
                for key in allowed
                if isinstance(metadata, dict) and key in metadata
            }
            for field_id, metadata in fields.items()
        }

    def _candidate_prompt_context(
        self,
        hits: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        allowed = ("id", "accession", "iri", "title", "description", "ontology_id")
        return [
            {key: hit[key] for key in allowed if key in hit}
            for hit in hits[: self.LLM_CANDIDATE_LIMIT]
            if isinstance(hit, dict)
        ]

    def _structured_prompt(
        self,
        initial_prompt: str,
        *sections: tuple[str, Any],
    ) -> str:
        prompt_parts = [initial_prompt]
        for heading, value in sections:
            if value is None or value == "" or value == [] or value == {}:
                continue
            prompt_parts.extend(["", f"{heading}:", self._prompt_text(value)])
        return "\n".join(prompt_parts)

    def _assign_onto_framework_response_schema(self) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "decision": {"type": "STRING"},
                "confidence": {"type": "STRING"},
                "reason": {"type": "STRING"},
            },
            "required": ["decision", "confidence", "reason"],
        }

    def _assign_field_response_schema(self) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "decision": {"type": "STRING"},
                "confidence": {"type": "STRING"},
                "reason": {"type": "STRING"},
                "new_field": {"type": "BOOLEAN"},
            },
            "required": ["decision", "confidence", "reason", "new_field"],
        }

    def _lookup_judge_response_schema(self) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "decision": {"type": "STRING"},
                "confidence": {"type": "STRING"},
                "reason": {"type": "STRING"},
            },
            "required": ["decision", "confidence", "reason"],
        }

    def _search_judge_response_schema(self) -> dict[str, Any]:
        return self._lookup_judge_response_schema()

    def _validate_assignment_response(self, assignment: Any) -> None:
        if not isinstance(assignment, dict):
            raise ValueError("LLM assignment response must be a JSON object.")

        required_fields = {"decision", "confidence", "reason"}
        if not required_fields.issubset(assignment):
            raise ValueError(
                "LLM assignment response must include decision, confidence, and reason."
            )

    def _validate_field_assignment_response(self, assignment: Any) -> None:
        if not isinstance(assignment, dict):
            raise ValueError("LLM field assignment response must be a JSON object.")

        required_fields = {"decision", "confidence", "reason", "new_field"}
        if not required_fields.issubset(assignment):
            raise ValueError(
                "LLM field assignment response must include decision, confidence, "
                "reason, and new_field."
            )

    def _validate_lookup_judge_response(self, judgement: Any) -> None:
        if not isinstance(judgement, dict):
            raise ValueError("LLM lookup judgement response must be a JSON object.")

        required_fields = {"decision", "confidence", "reason"}
        if not required_fields.issubset(judgement):
            raise ValueError(
                "LLM lookup judgement response must include decision, confidence, "
                "and reason."
            )

    def _validate_search_judge_response(self, judgement: Any) -> None:
        if not isinstance(judgement, dict):
            raise ValueError("Search LLM judgement response must be a JSON object.")
        if not {"decision", "confidence", "reason"}.issubset(judgement):
            raise ValueError(
                "Search LLM judgement response must include decision, confidence, "
                "and reason."
            )

    def _prompt_text(
        self,
        value: Any,
    ) -> str:
        if value is None:
            return ""

        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, sort_keys=True)

        return str(value)

    def _framework_has_local_file(self, framework: dict[str, Any]) -> bool:
        if "url" in framework:
            return False
        return self._configured_path_exists(
            framework.get("json_path")
        ) or self._configured_path_exists(framework.get("owl_path"))

    @staticmethod
    def _configured_path_exists(value: Any) -> bool:
        if isinstance(value, Path):
            return value.exists()
        if isinstance(value, str) and value:
            return Path(value).exists()
        return False

    @staticmethod
    def _mark_ontology_miss(target: dict[str, Any]) -> bool:
        target.pop("ontology_id", None)
        target.pop("ontology_lookup", None)
        target.pop("ontology_lookup_hits", None)
        target.pop("ontology_lookup_judgement", None)
        target["ontology_match"] = False
        return False
