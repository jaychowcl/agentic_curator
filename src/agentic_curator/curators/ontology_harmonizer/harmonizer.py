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
from agentic_curator.curators.ontology_harmonizer.strategy_handlers import (
    RagStrategyHandler,
    WebsearchStrategyHandler,
)
from agentic_curator.wrappers import LLM


PROMPT_PACKAGE = "agentic_curator.curators.ontology_harmonizer"
LOGGER = logging.getLogger(__name__)


class OntologyHarmonizer:
    """Curator for harmonizing publication metadata against ontologies."""

    DEFAULT_TARGET_PATHS = HarmonizationTargetExtractor.DEFAULT_TARGET_PATHS
    STRATEGY_ALIASES = {
        "rag": "rag",
        "websearch": "websearch",
    }
    STRATEGY_HANDLERS = {
        "rag": RagStrategyHandler,
        "websearch": WebsearchStrategyHandler,
    }

    def __init__(
        self,
        ontostore: OntoStore | None = None,
        llm: Any | None = None,
    ) -> None:
        self.ontostore = OntoStore() if ontostore is None else ontostore
        self.llm = llm
        self.target_extractor = HarmonizationTargetExtractor()

    def harmonize(
        self,
        publication_context: str | None = None,
        harmonization_targets: dict[str, Any] | list[dict[str, Any]] | None = None,
        target: dict[str, Any] | None = None,
        strategy: str = "websearch",
        ontostore: OntoStore | None = None,
        target_paths: list[StartPathSpec] | None = None,
        lookup_llm_judge: bool = False,
        lookup_llm_threshold: int = 2,
        llm: bool = True,
    ) -> dict[str, Any]:
        LOGGER.info("Starting ontology harmonization.")
        effective_ontostore = self._effective_ontostore(ontostore)
        normalized_strategy = self._normalize_strategy(strategy)
        normalized_targets = self._normalize_targets(
            harmonization_targets=harmonization_targets,
            target=target,
        )
        LOGGER.debug(
            "Ontology harmonization using strategy %s for %d targets.",
            normalized_strategy,
            len(normalized_targets),
        )
        for normalized_target in normalized_targets:
            self._harmonize_target(normalized_target, effective_ontostore)
            lookup = self.lookup_label(
                normalized_target,
                publication_context=publication_context,
                ontostore=effective_ontostore,
                strategy=normalized_strategy,
                lookup_llm_judge=lookup_llm_judge,
                lookup_llm_threshold=lookup_llm_threshold,
            )
            if not lookup:
                LOGGER.info(
                    "Ontology lookup missed for target %s.",
                    normalized_target.get("id"),
                )
                self._mark_ontology_miss(normalized_target)
                if llm:
                    LOGGER.info(
                        "Assigning ontology framework for target %s.",
                        normalized_target.get("id"),
                    )
                    self.assign_onto_framework(
                        normalized_target,
                        publication_context=publication_context,
                        ontostore=effective_ontostore,
                    )

            self.harmonize_field(
                normalized_target,
                publication_context=publication_context,
                ontostore=effective_ontostore,
                llm=llm,
            )

            if not lookup:
                if normalized_strategy in self.STRATEGY_HANDLERS:
                    LOGGER.info(
                        "Routing target %s to %s strategy handler.",
                        normalized_target.get("id"),
                        normalized_strategy,
                    )
                    self.harmonize_label(
                        normalized_target,
                        publication_context=publication_context,
                        ontostore=effective_ontostore,
                        strategy=normalized_strategy,
                    )
                    self._lookup_harmonized_label(
                        normalized_target,
                        ontostore=effective_ontostore,
                    )

        LOGGER.info("Completed ontology harmonization.")
        return {
            "publication_context": publication_context,
            "harmonization_targets": normalized_targets,
            "strategy": normalized_strategy,
            "target_paths": target_paths,
        }

    def harmonize_miniml_json(
        self,
        publication_context: str | None = None,
        miniml_json: dict[str, Any] | list[Any] | None = None,
        ontostore: OntoStore | None = None,
        target_paths: list[StartPathSpec] | None = None,
        strategy: str = "websearch",
        lookup_llm_judge: bool = False,
        lookup_llm_threshold: int = 2,
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
        result = self.harmonize(
            publication_context=publication_context,
            harmonization_targets=harmonization_targets,
            target=None,
            strategy=strategy,
            ontostore=ontostore,
            target_paths=effective_target_paths,
            lookup_llm_judge=lookup_llm_judge,
            lookup_llm_threshold=lookup_llm_threshold,
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
        alternative = self._target_alternative(target, occurrence)
        if alternative is None:
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
            field_name = self._field_name_from_path(field_path)
            if field_name is None or field_name not in parent:
                return
            alternatives_key = f"{field_name}_hz_alternatives"
            alternatives = self._alternatives_list(parent, alternatives_key)
            self._append_alternative(alternatives, alternative)
            return

        alternatives = self._alternatives_list(parent, "hz_alternatives")
        if self._append_alternative(alternatives, alternative):
            parent.setdefault("hz_field", alternative["hz_field"])
            parent.setdefault("hz_label", alternative["hz_label"])

    def _target_alternative(
        self,
        target: dict[str, Any],
        occurrence: dict[str, Any],
    ) -> dict[str, Any] | None:
        hz_field = target.get("hz_field", occurrence.get("hz_field"))
        hz_label = target.get("hz_label", occurrence.get("hz_label"))
        target_id = target.get("id")
        if hz_field is None or hz_label is None or target_id is None:
            return None

        return {
            "hz_field": hz_field,
            "hz_label": hz_label,
            "target_id": target_id,
        }

    def _alternatives_list(
        self,
        parent: dict[str, Any],
        key: str,
    ) -> list[dict[str, Any]]:
        alternatives = parent.get(key)
        if isinstance(alternatives, list):
            return alternatives

        alternatives = []
        parent[key] = alternatives
        return alternatives

    @staticmethod
    def _append_alternative(
        alternatives: list[dict[str, Any]],
        alternative: dict[str, Any],
    ) -> bool:
        if alternative in alternatives:
            return False
        alternatives.append(alternative)
        return True

    @classmethod
    def _field_name_from_path(cls, path: str) -> str | None:
        if path == "":
            return None
        return cls._unescape_json_pointer_segment(path.rsplit("/", 1)[-1])

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

    def _normalize_strategy(self, strategy: str) -> str:
        normalized = self.STRATEGY_ALIASES.get(strategy)
        if normalized is None:
            supported = ", ".join(sorted(self.STRATEGY_ALIASES))
            raise ValueError(
                f"Unknown harmonization strategy {strategy!r}. "
                f"Supported strategies: {supported}."
            )
        return normalized

    def lookup_label(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
        strategy: str,
        lookup_llm_judge: bool = False,
        lookup_llm_threshold: int = 2,
    ) -> Any:
        del strategy

        self._harmonize_target(target, ontostore)
        label = target.get("hz_label")
        if label is None:
            LOGGER.info("Skipping ontology lookup because target has no hz_label.")
            return False

        hits: list[dict[str, Any]] = []
        candidate_ontology_ids = self._candidate_ontology_ids(target, ontostore)
        LOGGER.debug(
            "Looking up label %r across ontology IDs: %s.",
            label,
            candidate_ontology_ids,
        )
        for ontology_id in candidate_ontology_ids:
            hits.extend(ontostore.lookup(str(label), ontology_id))

        if not hits:
            return False

        lookup = self._select_lookup_hit(
            target=target,
            publication_context=publication_context,
            hits=hits,
            lookup_llm_judge=lookup_llm_judge,
            lookup_llm_threshold=lookup_llm_threshold,
        )
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
        hits: list[dict[str, Any]],
        lookup_llm_judge: bool,
        lookup_llm_threshold: int,
    ) -> dict[str, Any]:
        if not lookup_llm_judge or len(hits) < lookup_llm_threshold:
            return hits[0]

        LOGGER.info("Judging %d ontology lookup hits with LLM.", len(hits))
        judgement = self.judge_lookup(
            target,
            publication_context=publication_context,
            hits=hits,
        )
        target["ontology_lookup_judgement"] = judgement
        decision = str(judgement["decision"])
        for hit in hits:
            if str(hit.get("id")) == decision:
                return hit

        raise ValueError(
            "LLM lookup judgement decision must match a known lookup hit id."
        )

    def judge_lookup(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._judge_lookup_prompt(
            target=target,
            publication_context=publication_context,
            hits=hits,
        )
        response = self._llm().generate_response(
            prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": self._lookup_judge_response_schema(),
            },
        )
        judgement = parse_json_response(response)
        self._validate_lookup_judge_response(judgement)
        return judgement

    def assign_onto_framework(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
        LOGGER.info("Assigning ontology framework with LLM.")
        self._mark_ontology_miss(target)
        framework_configs = self._assignment_candidate_frameworks(target, ontostore)
        prompt = self._assign_onto_framework_prompt(
            target=target,
            publication_context=publication_context,
            ontology_frameworks=framework_configs,
        )
        response = self._llm().generate_response(
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
                ontostore=ontostore,
            )
        return False

    def assign_field(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
        LOGGER.info("Assigning harmonized field with LLM.")
        prompt = self._assign_field_prompt(
            target=target,
            publication_context=publication_context,
            fields=ontostore.fields,
        )
        response = self._llm().generate_response(
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
            ontostore.fields[decision] = {
                "label": decision,
                "source": "llm",
                "confidence": assignment["confidence"],
                "reason": assignment["reason"],
            }

        return assignment

    def harmonize_label(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
        strategy: str,
    ) -> dict[str, Any]:
        handler_class = self.STRATEGY_HANDLERS.get(strategy)
        if handler_class is None:
            supported = ", ".join(sorted(self.STRATEGY_HANDLERS))
            raise ValueError(
                f"Unknown harmonization strategy {strategy!r}. "
                f"Supported strategies: {supported}."
            )

        LOGGER.info("Running ontology harmonization strategy %s.", strategy)
        return handler_class().handle(
            target,
            publication_context=publication_context,
            ontostore=ontostore,
        )

    def _llm(self) -> Any:
        if self.llm is None:
            self.llm = LLM()

        return self.llm

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
        label = target.get("hz_label")
        if label is None:
            LOGGER.info(
                "Skipping post-strategy ontology lookup because target has no hz_label."
            )
            return False

        for ontology_id in self._post_strategy_ontology_ids(target, ontostore):
            hits = ontostore.lookup(str(label), ontology_id)
            if hits:
                break
        else:
            hits = []

        if not hits:
            LOGGER.info("Post-strategy ontology lookup returned no hits.")
            return False

        lookup = hits[0]
        target["ontology_id"] = lookup["ontology_id"]
        target["ontology_lookup"] = lookup
        target["ontology_lookup_hits"] = hits
        target["ontology_match"] = True
        LOGGER.info(
            "Post-strategy ontology lookup matched target %s with %d hits.",
            target.get("id"),
            len(hits),
        )
        return lookup

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
            "version": framework.get("version"),
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

    def _assign_onto_framework_prompt(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        ontology_frameworks: dict[str, Any],
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/assign_onto_framework.md"
        ).read_text(encoding="utf-8").strip()
        prompt_parts = [
            initial_prompt,
            "Publication Context:",
            self._prompt_text(publication_context),
            "",
            "Harmonization Target:",
            self._prompt_text(target),
            "",
            "Ontology Framework Config:",
            self._prompt_text(ontology_frameworks),
        ]
        return "\n".join(prompt_parts).lstrip("\n")

    def _assign_field_prompt(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        fields: dict[str, Any],
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/assign_field.md"
        ).read_text(encoding="utf-8").strip()
        prompt_parts = [
            initial_prompt,
            "Publication Context:",
            self._prompt_text(publication_context),
            "",
            "Harmonization Target:",
            self._prompt_text(target),
            "",
            "Fields:",
            self._prompt_text(fields),
        ]
        return "\n".join(prompt_parts).lstrip("\n")

    def _judge_lookup_prompt(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        hits: list[dict[str, Any]],
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/judge_lookup.md"
        ).read_text(encoding="utf-8").strip()
        prompt_parts = [
            initial_prompt,
            "Publication Context:",
            self._prompt_text(publication_context),
            "",
            "Harmonization Target:",
            self._prompt_text(target),
            "",
            "Lookup Hits:",
            self._prompt_text(hits),
        ]
        return "\n".join(prompt_parts).lstrip("\n")

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
