from __future__ import annotations

import json
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


class OntologyHarmonizer:
    """Curator for harmonizing publication metadata against ontologies."""

    DEFAULT_TARGET_PATHS = HarmonizationTargetExtractor.DEFAULT_TARGET_PATHS
    STRATEGY_ALIASES = {
        "identity": "identity",
        "noop": "identity",
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
        strategy: str = "identity",
        ontostore: OntoStore | None = None,
        target_paths: list[StartPathSpec] | None = None,
    ) -> dict[str, Any]:
        effective_ontostore = self._effective_ontostore(ontostore)
        normalized_strategy = self._normalize_strategy(strategy)
        normalized_targets = self._normalize_targets(
            harmonization_targets=harmonization_targets,
            target=target,
        )
        for normalized_target in normalized_targets:
            self._harmonize_target(normalized_target, effective_ontostore)
            lookup = self.lookup_label(
                normalized_target,
                publication_context=publication_context,
                ontostore=effective_ontostore,
                strategy=normalized_strategy,
            )
            if not lookup:
                self.assign_onto_framework(
                    normalized_target,
                    publication_context=publication_context,
                    ontostore=effective_ontostore,
                )
                self.harmonize_label(
                    normalized_target,
                    publication_context=publication_context,
                    ontostore=effective_ontostore,
                )
                if normalized_strategy in self.STRATEGY_HANDLERS:
                    self.harmonize_with_strategy(
                        normalized_target,
                        publication_context=publication_context,
                        ontostore=effective_ontostore,
                        strategy=normalized_strategy,
                    )

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
        strategy: str = "identity",
    ) -> dict[str, Any]:
        should_dedupe_targets = target_paths is None
        effective_target_paths = target_paths
        if effective_target_paths is None:
            effective_target_paths = (
                self.target_extractor.build_miniml_sample_target_paths(miniml_json)
            )
        harmonization_targets = self.target_extractor.extract(
            miniml_json,
            start_paths=effective_target_paths,
        )
        if should_dedupe_targets:
            harmonization_targets = self.target_extractor.dedupe_targets(
                harmonization_targets
            )
        return self.harmonize(
            publication_context=publication_context,
            harmonization_targets=harmonization_targets,
            target=None,
            strategy=strategy,
            ontostore=ontostore,
            target_paths=effective_target_paths,
        )

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
    ) -> Any:
        del publication_context, strategy

        self._harmonize_target(target, ontostore)
        label = target.get("hz_label")
        if label is None:
            return False

        for ontology_id in self._candidate_ontology_ids(target, ontostore):
            lookup = ontostore.lookup(str(label), ontology_id)
            if lookup:
                target["ontology_id"] = ontology_id
                target["ontology_lookup"] = lookup
                target["ontology_match"] = True
                return lookup

        return False

    def assign_onto_framework(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
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

    def harmonize_label(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> Any:
        self._harmonize_target(target, ontostore)
        field = target.get("hz_field")
        if field is None:
            return False

        lookup = ontostore.lookup_fields(field)
        if lookup:
            target["hz_field"] = lookup["field"]
            target["field_lookup"] = lookup
            return lookup

        return self.assign_field(
            target,
            publication_context=publication_context,
            ontostore=ontostore,
        )

    def assign_field(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
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

    def harmonize_with_strategy(
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
        target["ontology_match"] = False
        return False
