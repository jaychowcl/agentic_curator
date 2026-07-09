from __future__ import annotations

from typing import Any

from agentic_curator.curators.ontology_harmonizer.harmonization_target_extractor import (
    HarmonizationTargetExtractor,
    StartPathSpec,
)
from agentic_curator.curators.ontology_harmonizer.ontology_store import OntoStore


class OntologyHarmonizer:
    """Curator for harmonizing publication metadata against ontologies."""

    DEFAULT_TARGET_PATHS = HarmonizationTargetExtractor.DEFAULT_TARGET_PATHS
    STRATEGY_ALIASES = {
        "identity": "identity",
        "noop": "identity",
    }

    def __init__(self, ontostore: OntoStore | None = None) -> None:
        self.ontostore = OntoStore() if ontostore is None else ontostore
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
            self.assign_onto_framework(
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

    def assign_onto_framework(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
        strategy: str,
    ) -> None:
        pass

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
