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
DIRECT_REVIEW = "direct"
EVIDENCE_THEN_JUDGEMENT = "evidence_then_judgement"
REVIEW_STRATEGIES = {DIRECT_REVIEW, EVIDENCE_THEN_JUDGEMENT}


class ThematicReviewer:
    """Assess publication relevance to a thematic curation target."""

    MAX_OUTPUT_TOKENS = 16_384
    DIRECT_REVIEW_REVISION = 2
    ACCESSION_CRITERIA = (
        "human_samples",
        "transcriptomics_assay",
        "established_fibrosis",
        "accession_linkage",
    )
    CRITERION_STATUSES = ("meets", "fails", "uncertain")
    CONFIDENCE_LEVELS = ("low", "medium", "high")

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def review_relevancy(
        self,
        publication_text: str | None = None,
        theme: str | None = None,
        metadata: str | dict[str, Any] | None = None,
        title: str | None = None,
        accessions: list[str] | None = None,
        strategy: str = DIRECT_REVIEW,
    ) -> dict[str, Any]:
        if strategy not in REVIEW_STRATEGIES:
            raise ValueError(
                f"Unsupported thematic review strategy {strategy!r}; "
                f"expected one of {sorted(REVIEW_STRATEGIES)}."
            )
        accessions = self._normalized_accessions(accessions)
        LOGGER.info("Starting thematic relevance review strategy=%s.", strategy)
        if strategy == DIRECT_REVIEW:
            result = self._direct_review(
                publication_text=publication_text,
                theme=theme,
                metadata=metadata,
                title=title,
                accessions=accessions,
            )
            LOGGER.info(
                "Completed thematic relevance review strategy=%s judgement=%s accession_rejections=%s.",
                strategy,
                result.get("judgement"),
                len(result.get("accessions_to_remove", [])),
            )
            return {**result, "strategy": strategy}

        evidences = self.extract_evidence(
            publication_text=publication_text,
            theme=theme,
            metadata=metadata,
            title=title,
            accessions=accessions,
        )
        judgement = self.judge_evidence(
            evidences=evidences,
            theme=theme,
            title=title,
            accessions=accessions,
        )
        LOGGER.info(
            "Completed thematic relevance review strategy=%s judgement=%s accession_rejections=%s.",
            strategy,
            judgement.get("judgement"),
            len(judgement.get("accessions_to_remove", [])),
        )
        return {**judgement, "strategy": strategy, "evidences": evidences}

    def _direct_review(
        self,
        publication_text: str | None = None,
        theme: str | None = None,
        metadata: str | dict[str, Any] | None = None,
        title: str | None = None,
        accessions: list[str] | None = None,
    ) -> dict[str, Any]:
        LOGGER.debug("Building direct thematic review prompt.")
        prompt = self._direct_review_prompt(
            publication_text=publication_text,
            theme=theme,
            metadata=metadata,
            title=title,
            accessions=accessions,
        )
        response = self._llm().generate_response(
            prompt,
            config={
                "max_output_tokens": self.MAX_OUTPUT_TOKENS,
                "response_mime_type": "application/json",
                "response_schema": self._direct_review_response_schema(),
            },
        )
        return self._normalized_direct_review_result(
            parse_json_response(response),
            accessions=accessions,
        )

    def extract_evidence(
        self,
        publication_text: str | None = None,
        theme: str | None = None,
        metadata: str | dict[str, Any] | None = None,
        title: str | None = None,
        accessions: list[str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        LOGGER.info("Starting evidence extraction.")
        prompt = self._evidence_prompt(
            publication_text=publication_text,
            theme=theme,
            metadata=metadata,
            title=title,
            accessions=accessions,
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
        accessions: list[str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        LOGGER.info("Starting evidence judgement.")
        prompt = self._judge_evidence_prompt(
            evidences=evidences,
            theme=theme,
            title=title,
            accessions=accessions,
        )
        response = self._llm().generate_response(
            prompt,
            config={
                "max_output_tokens": self.MAX_OUTPUT_TOKENS,
                "response_mime_type": "application/json",
                "response_schema": self._judge_evidence_response_schema(),
            },
        )
        result = self._normalized_review_result(
            parse_json_response(response),
            accessions=self._normalized_accessions(accessions),
        )
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
        accessions: list[str] | None = None,
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
            "",
            "Accessions:",
            self._prompt_text(self._normalized_accessions(accessions)),
        ]
        return "\n".join(prompt_parts).lstrip("\n")

    def _judge_evidence_prompt(
        self,
        evidences: Any,
        theme: str | None = None,
        title: str | None = None,
        accessions: list[str] | None = None,
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
            "",
            "Accessions:",
            self._prompt_text(self._normalized_accessions(accessions)),
        ]
        return "\n".join(prompt_parts).lstrip("\n")

    def _direct_review_prompt(
        self,
        publication_text: str | None = None,
        theme: str | None = None,
        metadata: str | dict[str, Any] | list[Any] | None = None,
        title: str | None = None,
        accessions: list[str] | None = None,
    ) -> str:
        initial_prompt = files(PROMPT_PACKAGE).joinpath(
            "prompts/direct_review.md"
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
            "",
            "Accessions:",
            self._prompt_text(self._normalized_accessions(accessions)),
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
        return self._review_response_schema()

    def _direct_review_response_schema(self) -> dict[str, Any]:
        criterion_schema = {
            "type": "OBJECT",
            "properties": {
                "status": {
                    "type": "STRING",
                    "enum": list(self.CRITERION_STATUSES),
                },
                "evidence": {"type": "STRING"},
            },
            "required": ["status", "evidence"],
        }
        assessment_properties = {
            "accession": {"type": "STRING"},
            **{
                criterion: criterion_schema
                for criterion in self.ACCESSION_CRITERIA
            },
            "confidence": {
                "type": "STRING",
                "enum": list(self.CONFIDENCE_LEVELS),
            },
            "reason": {"type": "STRING"},
        }
        return {
            "type": "OBJECT",
            "properties": {
                "accession_assessments": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": assessment_properties,
                        "required": [
                            "accession",
                            *self.ACCESSION_CRITERIA,
                            "confidence",
                            "reason",
                        ],
                    },
                }
            },
            "required": ["accession_assessments"],
        }

    def _review_response_schema(self) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "judgement": {"type": "STRING"},
                "reasoning": {"type": "STRING"},
                "confidence": {"type": "STRING"},
                "accessions_to_remove": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "accession": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                            "confidence": {"type": "STRING"},
                        },
                        "required": ["accession", "reason", "confidence"],
                    },
                },
            },
            "required": [
                "judgement",
                "reasoning",
                "confidence",
                "accessions_to_remove",
            ],
        }

    @staticmethod
    def _normalized_accessions(accessions: list[str] | None) -> list[str]:
        normalized = []
        seen = set()
        for value in accessions or []:
            accession = str(value).strip()
            if not accession or accession in seen:
                continue
            seen.add(accession)
            normalized.append(accession)
        return normalized

    def _normalized_review_result(
        self,
        result: Any,
        *,
        accessions: list[str] | None,
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise ValueError("Thematic review response must be a JSON object.")
        supplied = set(self._normalized_accessions(accessions))
        removals = []
        seen = set()
        raw_removals = result.get("accessions_to_remove", [])
        if not isinstance(raw_removals, list):
            raw_removals = []
        for value in raw_removals:
            if not isinstance(value, dict):
                continue
            accession = str(value.get("accession", "")).strip()
            if accession not in supplied:
                LOGGER.warning(
                    "Ignoring unknown accession rejection accession=%r.", accession
                )
                continue
            if accession in seen:
                continue
            seen.add(accession)
            removals.append(
                {
                    "accession": accession,
                    "reason": str(value.get("reason", "")),
                    "confidence": str(value.get("confidence", "")),
                }
            )
        return {
            "judgement": str(result.get("judgement", "")),
            "reasoning": str(result.get("reasoning", "")),
            "confidence": str(result.get("confidence", "")),
            "accessions_to_remove": removals,
        }

    def _normalized_direct_review_result(
        self,
        result: Any,
        *,
        accessions: list[str] | None,
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise ValueError("Thematic review response must be a JSON object.")

        supplied = self._normalized_accessions(accessions)
        supplied_set = set(supplied)
        by_accession: dict[str, dict[str, Any]] = {}
        raw_assessments = result.get("accession_assessments", [])
        if not isinstance(raw_assessments, list):
            raw_assessments = []

        for value in raw_assessments:
            if not isinstance(value, dict):
                continue
            accession = str(value.get("accession", "")).strip()
            if accession not in supplied_set:
                LOGGER.warning(
                    "Ignoring unknown accession assessment accession=%r.", accession
                )
                continue
            if accession in by_accession:
                LOGGER.warning(
                    "Ignoring duplicate accession assessment accession=%r.", accession
                )
                continue
            by_accession[accession] = self._normalized_accession_assessment(
                value,
                accession=accession,
            )

        assessments = []
        for accession in supplied:
            assessment = by_accession.get(accession)
            if assessment is None:
                assessment = self._missing_accession_assessment(accession)
            assessments.append(assessment)

        qualifying = [
            value for value in assessments if value["decision"] == "qualifies"
        ]
        excluded = [
            value for value in assessments if value["decision"] == "exclude"
        ]
        uncertain = [
            value for value in assessments if value["decision"] == "uncertain"
        ]

        if qualifying:
            judgement = "relevant"
            confidence = self._aggregate_confidence(qualifying, strongest=True)
            reasoning = (
                f"{len(qualifying)} of {len(assessments)} supplied accessions "
                "meets all theme criteria."
            )
        elif assessments and len(excluded) == len(assessments):
            judgement = "not_relevant"
            confidence = self._aggregate_confidence(excluded, strongest=False)
            reasoning = (
                f"All {len(assessments)} supplied accessions explicitly fail "
                "at least one theme criterion."
            )
        else:
            judgement = "unsure"
            confidence = self._aggregate_confidence(uncertain, strongest=False)
            reasoning = (
                "No supplied accession meets all theme criteria; "
                f"{len(uncertain)} uncertain and {len(excluded)} excluded."
            )

        return {
            "judgement": judgement,
            "reasoning": reasoning,
            "confidence": confidence,
            "accessions_to_remove": [
                {
                    "accession": value["accession"],
                    "reason": value["reason"],
                    "confidence": value["confidence"],
                }
                for value in excluded
            ],
            "accession_assessments": assessments,
            "review_revision": self.DIRECT_REVIEW_REVISION,
        }

    def _normalized_accession_assessment(
        self,
        value: dict[str, Any],
        *,
        accession: str,
    ) -> dict[str, Any]:
        assessment = {"accession": accession}
        statuses = []
        for criterion in self.ACCESSION_CRITERIA:
            normalized = self._normalized_criterion(value.get(criterion))
            assessment[criterion] = normalized
            statuses.append(normalized["status"])

        confidence = str(value.get("confidence", "")).strip().lower()
        if confidence not in self.CONFIDENCE_LEVELS:
            confidence = "low"

        if "fails" in statuses and confidence in {"medium", "high"}:
            decision = "exclude"
        elif statuses and all(status == "meets" for status in statuses):
            decision = "qualifies"
        else:
            decision = "uncertain"

        reason = str(value.get("reason", "")).strip()
        if not reason:
            reason = "The criterion assessments determine this accession decision."
        return {
            **assessment,
            "confidence": confidence,
            "reason": reason,
            "decision": decision,
        }

    def _normalized_criterion(self, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {"status": "uncertain", "evidence": ""}
        status = str(value.get("status", "")).strip().lower()
        evidence = str(value.get("evidence", "")).strip()
        if status not in self.CRITERION_STATUSES or (
            status != "uncertain" and not evidence
        ):
            status = "uncertain"
        return {"status": status, "evidence": evidence}

    def _missing_accession_assessment(self, accession: str) -> dict[str, Any]:
        return {
            "accession": accession,
            **{
                criterion: {"status": "uncertain", "evidence": ""}
                for criterion in self.ACCESSION_CRITERIA
            },
            "confidence": "low",
            "reason": (
                "The model did not return an assessment for this supplied accession."
            ),
            "decision": "uncertain",
        }

    def _aggregate_confidence(
        self,
        assessments: list[dict[str, Any]],
        *,
        strongest: bool,
    ) -> str:
        if not assessments:
            return "low"
        ranks = {value: index for index, value in enumerate(self.CONFIDENCE_LEVELS)}
        selected = (max if strongest else min)(
            assessments,
            key=lambda value: ranks.get(value.get("confidence", "low"), 0),
        )
        return str(selected.get("confidence", "low"))
