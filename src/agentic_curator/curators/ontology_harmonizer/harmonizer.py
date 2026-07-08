from __future__ import annotations

from typing import Any

from agentic_curator.curators.ontology_harmonizer.harmonization_target_extractor import (
    HarmonizationTargetExtractor,
    StartPathSpec,
)
from agentic_curator.curators.ontology_harmonizer.ontology_store import OntoStore


OntologyFrameworks = dict[str, Any] | OntoStore


class OntologyHarmonizer:
    """Curator for harmonizing publication metadata against ontologies."""

    DEFAULT_TARGET_PATHS = HarmonizationTargetExtractor.DEFAULT_TARGET_PATHS

    def __init__(self, ontology_frameworks: OntologyFrameworks | None = None) -> None:
        self.ontology_frameworks = (
            OntoStore() if ontology_frameworks is None else ontology_frameworks
        )
        self.target_extractor = HarmonizationTargetExtractor()

    def harmonize(
        self,
        publication_context: str | None = None,
        harmonization_targets: list[dict[str, Any]] | None = None,
        ontostore: OntoStore | None = None,
        target_paths: list[StartPathSpec] | None = None,
    ) -> dict[str, Any]:
        effective_ontostore = self._effective_ontostore(ontostore)
        _ = effective_ontostore

        return {
            "publication_context": publication_context,
            "harmonization_targets": (
                [] if harmonization_targets is None else harmonization_targets
            ),
            "target_paths": target_paths,
        }

    def harmonize_miniml_json(
        self,
        publication_context: str | None = None,
        miniml_json: dict[str, Any] | list[Any] | None = None,
        ontostore: OntoStore | None = None,
        target_paths: list[StartPathSpec] | None = None,
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
            ontostore=ontostore,
            target_paths=effective_target_paths,
        )

    def _effective_ontostore(self, ontostore: OntoStore | None = None) -> OntoStore:
        effective_ontostore = (
            self.ontology_frameworks if ontostore is None else ontostore
        )
        if not isinstance(effective_ontostore, OntoStore):
            raise TypeError("ontostore must be an OntoStore.")
        return effective_ontostore

    def _extract_harmonization_targets(
        self,
        metadata: str | dict[str, Any] | list[Any] | None,
        start_paths: list[StartPathSpec] | None = None,
    ) -> list[dict[str, Any]]:
        return self.target_extractor.extract(metadata, start_paths=start_paths)
