from __future__ import annotations

from typing import Any


class OntologyHarmonizer:
    """Placeholder curator for harmonizing publication text against ontologies."""

    def harmonize(
        self,
        publication_text: str | None = None,
        metadata: str | dict[str, Any] | None = None,
        title: str | None = None,
        ontology_frameworks: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "placeholder",
            "publication_text": publication_text,
            "metadata": metadata,
            "title": title,
            "ontology_frameworks": ontology_frameworks or {},
            "matches": [],
        }
