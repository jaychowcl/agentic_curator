from __future__ import annotations

from typing import Any


class OntologyHarmonizer:
    """Placeholder curator for harmonizing terms against ontology targets."""

    def harmonize(
        self,
        terms: list[str] | None = None,
        ontology: str | None = None,
        context: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "placeholder",
            "terms": terms or [],
            "ontology": ontology,
            "context": context,
            "matches": [],
        }
