# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

import logging
from importlib.resources import files
from typing import Any

from agentic_curator.curators.json_response import parse_json_response
from agentic_curator.wrappers import LLM


PROMPT_PACKAGE = "agentic_curator.curators.query_generator"
DATASET_FILTER = "(HAS_DATA:y OR HAS_LABSLINKS:y)"
LOGGER = logging.getLogger(__name__)


class QueryGenerator:
    """Generate bounded Europe PMC queries for a thematic atlas workflow."""

    MIN_QUERIES = 1
    MAX_QUERIES = 3

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def generate_queries(
        self,
        theme: str | None,
        max_queries: int = MAX_QUERIES,
    ) -> dict[str, Any]:
        normalized_theme = self._validate_theme(theme)
        self._validate_max_queries(max_queries)
        LOGGER.info("Generating up to %d Europe PMC queries.", max_queries)
        response = self._llm().generate_response(
            self._prompt(normalized_theme, max_queries=max_queries),
            config={
                "response_mime_type": "application/json",
                "response_schema": self._response_schema(max_queries=max_queries),
            },
        )
        result = parse_json_response(response)
        validated = self._validated_response(result, max_queries=max_queries)
        LOGGER.info(
            "Generated Europe PMC query stats queries=%d query_characters=%s.",
            len(validated["queries"]),
            [len(query) for query in validated["queries"]],
        )
        return validated

    def _llm(self) -> Any:
        if self.llm is None:
            LOGGER.debug("Creating default LLM facade for query generator.")
            self.llm = LLM()
        return self.llm

    def _prompt(self, theme: str, *, max_queries: int) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/generate_queries.md"
        ).read_text(encoding="utf-8").strip()
        return "\n".join(
            [
                initial_prompt,
                "",
                "Theme:",
                theme,
                "",
                "Maximum Queries:",
                str(max_queries),
            ]
        )

    def _validated_response(
        self,
        response: Any,
        *,
        max_queries: int,
    ) -> dict[str, Any]:
        if not isinstance(response, dict):
            raise ValueError("Query generator response must be a JSON object.")
        details = response.get("details")
        if not isinstance(details, list) or not details:
            raise ValueError("Query generator must return at least one query detail.")
        if len(details) > max_queries:
            raise ValueError("Query generator returned more than max_queries queries.")

        summary = self._non_empty_string(
            response.get("strategy_summary"),
            name="strategy_summary",
        )
        normalized_details: list[dict[str, str]] = []
        seen: set[str] = set()
        for detail in details:
            if not isinstance(detail, dict):
                raise ValueError("Each query detail must be a JSON object.")
            topical_query = self._non_empty_string(detail.get("query"), name="query")
            purpose = self._non_empty_string(detail.get("purpose"), name="purpose")
            normalized_key = " ".join(topical_query.split()).casefold()
            if normalized_key in seen:
                raise ValueError("Query generator queries must be unique.")
            seen.add(normalized_key)
            if "has_data:" in normalized_key or "has_labslinks:" in normalized_key:
                raise ValueError(
                    "Topical queries must not include dataset filters; they are added "
                    "programmatically."
                )
            query = f"({topical_query}) AND {DATASET_FILTER}"
            normalized_details.append({"query": query, "purpose": purpose})

        return {
            "queries": [detail["query"] for detail in normalized_details],
            "details": normalized_details,
            "strategy_summary": summary,
        }

    @staticmethod
    def _validate_theme(theme: str | None) -> str:
        if not isinstance(theme, str) or not theme.strip():
            raise ValueError("theme must be a non-empty string.")
        return theme.strip()

    @classmethod
    def _validate_max_queries(cls, max_queries: Any) -> None:
        if (
            isinstance(max_queries, bool)
            or not isinstance(max_queries, int)
            or not cls.MIN_QUERIES <= max_queries <= cls.MAX_QUERIES
        ):
            raise ValueError("max_queries must be an integer from 1 to 3.")

    @staticmethod
    def _non_empty_string(value: Any, *, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")
        return value.strip()

    def _response_schema(self, *, max_queries: int) -> dict[str, Any]:
        self._validate_max_queries(max_queries)
        return {
            "type": "OBJECT",
            "properties": {
                "details": {
                    "type": "ARRAY",
                    "minItems": 1,
                    "maxItems": max_queries,
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {"type": "STRING"},
                            "purpose": {"type": "STRING"},
                        },
                        "required": ["query", "purpose"],
                    },
                },
                "strategy_summary": {"type": "STRING"},
            },
            "required": ["details", "strategy_summary"],
        }
