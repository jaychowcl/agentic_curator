from __future__ import annotations

from typing import Any

from agentic_curator.curators.ontology_harmonizer.ontology_store import OntoStore


class PlaceholderStrategyHandler:
    """Base placeholder handler for ontology harmonization strategies."""

    strategy = ""
    reason = ""

    def handle(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, str]:
        del publication_context, ontostore

        result = {
            "strategy": self.strategy,
            "status": "placeholder",
            "reason": self.reason,
        }
        target["ontology_strategy_result"] = result
        return result


class DirectStrategyHandler(PlaceholderStrategyHandler):
    strategy = "direct"
    reason = "Direct ontology harmonization is not implemented yet."


class WebsearchStrategyHandler(PlaceholderStrategyHandler):
    strategy = "websearch"
    reason = "Websearch ontology harmonization is not implemented yet."


class RagStrategyHandler(PlaceholderStrategyHandler):
    strategy = "rag"
    reason = "RAG ontology harmonization is not implemented yet."
