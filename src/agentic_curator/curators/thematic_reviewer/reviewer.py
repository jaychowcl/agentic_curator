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
from typing import Any

from agentic_curator.curators.json_response import parse_json_response
from agentic_curator.wrappers import LLM


PROMPT_PACKAGE = "agentic_curator.curators.thematic_reviewer"
LOGGER = logging.getLogger(__name__)


class ThematicReviewer:
    """Assess publication relevance to a thematic curation target."""

    MAX_OUTPUT_TOKENS = 16_384

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def review_relevancy(
        self,
        publication_text: str | None = None,
        theme: str | None = None,
        metadata: str | dict[str, Any] | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        LOGGER.info("Starting thematic relevance review.")
        evidences = self.extract_evidence(
            publication_text=publication_text,
            theme=theme,
            metadata=metadata,
            title=title,
        )
        judgement = self.judge_evidence(evidences=evidences, theme=theme, title=title)
        LOGGER.info("Completed thematic relevance review.")
        return {"evidences": evidences, "judgement": judgement}

    def extract_evidence(
        self,
        publication_text: str | None = None,
        theme: str | None = None,
        metadata: str | dict[str, Any] | None = None,
        title: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        LOGGER.info("Starting evidence extraction.")
        prompt = self._evidence_prompt(
            publication_text=publication_text,
            theme=theme,
            metadata=metadata,
            title=title,
        )
        response = self._llm().generate_response(
            prompt,
            config={
                "max_output_tokens": self.MAX_OUTPUT_TOKENS,
                "response_mime_type": "application/json",
                "response_schema": self._evidence_response_schema(),
            },
        )
        result = parse_json_response(response)
        evidence_values = result.get("evidences", []) if isinstance(result, dict) else result
        evidence_count = len(evidence_values) if isinstance(evidence_values, list) else 0
        LOGGER.info("Completed evidence extraction evidence_count=%s.", evidence_count)
        return result

    def judge_evidence(
        self,
        evidences: Any,
        theme: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        LOGGER.info("Starting evidence judgement.")
        prompt = self._judge_evidence_prompt(
            evidences=evidences,
            theme=theme,
            title=title,
        )
        response = self._llm().generate_response(
            prompt,
            config={
                "max_output_tokens": self.MAX_OUTPUT_TOKENS,
                "response_mime_type": "application/json",
                "response_schema": self._judge_evidence_response_schema(),
            },
        )
        result = parse_json_response(response)
        judgement = result.get("judgement") if isinstance(result, dict) else None
        LOGGER.info("Completed evidence judgement judgement=%s.", judgement)
        return result

    def _llm(self) -> Any:
        if self.llm is None:
            LOGGER.debug("Creating default LLM facade for thematic reviewer.")
            self.llm = LLM()

        return self.llm

    def _evidence_prompt(
        self,
        publication_text: str | None = None,
        theme: str | None = None,
        metadata: str | dict[str, Any] | list[Any] | None = None,
        title: str | None = None,
    ) -> str:
        LOGGER.debug("Building evidence extraction prompt.")
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/evidence_extraction.md"
        ).read_text(encoding="utf-8").strip()
        prompt_parts = [
            initial_prompt,
            "Theme:",
            self._prompt_text(theme),
            "",
            "Title:",
            self._prompt_text(title),
            "",
            "Publication Text:",
            self._prompt_text(publication_text),
            "",
            "Metadata:",
            self._prompt_text(metadata),
        ]
        return "\n".join(prompt_parts).lstrip("\n")

    def _judge_evidence_prompt(
        self,
        evidences: Any,
        theme: str | None = None,
        title: str | None = None,
    ) -> str:
        LOGGER.debug("Building evidence judgement prompt.")
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/judge_evidence.md"
        ).read_text(encoding="utf-8").strip()
        prompt_parts = [
            initial_prompt,
            "Theme:",
            self._prompt_text(theme),
            "",
            "Title:",
            self._prompt_text(title),
            "",
            "Evidences:",
            self._prompt_text(evidences),
        ]
        return "\n".join(prompt_parts).lstrip("\n")

    def _prompt_text(
        self,
        value: str | dict[str, Any] | list[Any] | None,
    ) -> str:
        if value is None:
            return ""

        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, sort_keys=True)

        return str(value)

    def _evidence_response_schema(self) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "evidences": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "evidence": {"type": "STRING"},
                            "judgement": {"type": "STRING"},
                            "confidence": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                        },
                        "required": [
                            "evidence",
                            "judgement",
                            "confidence",
                            "reason",
                        ],
                    },
                }
            },
            "required": ["evidences"],
        }

    def _judge_evidence_response_schema(self) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "judgement": {"type": "STRING"},
                "reasoning": {"type": "STRING"},
                "confidence": {"type": "STRING"},
            },
            "required": ["judgement", "reasoning", "confidence"],
        }
