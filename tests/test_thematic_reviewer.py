# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

import importlib
import json
import pytest
from importlib.resources import files

from agentic_curator import ThematicReviewer as RootThematicReviewer
from agentic_curator.curators import ThematicReviewer


EVIDENCE_EXTRACTION_PROMPT = files("agentic_curator").joinpath(
    "curators/thematic_reviewer/prompts/evidence_extraction.md"
).read_text(encoding="utf-8").strip()
JUDGE_EVIDENCE_PROMPT = files("agentic_curator").joinpath(
    "curators/thematic_reviewer/prompts/judge_evidence.md"
).read_text(encoding="utf-8").strip()


class FakeLLM:
    def __init__(self, response=None, responses=None) -> None:
        self.calls = []
        self.response = {"response": "ok"} if response is None else response
        self.responses = list(responses or [])

    def generate_response(self, prompt, *, model=None, config=None, **extra_options):
        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "config": config,
                "extra_options": extra_options,
            }
        )
        if self.responses:
            return self.responses.pop(0)

        return self.response


def accession_assessment(
    accession: str,
    *,
    human_samples: str = "meets",
    transcriptomics_assay: str = "meets",
    established_fibrosis: str = "meets",
    accession_linkage: str = "meets",
    confidence: str = "high",
    reason: str = "The publication directly links the accession to eligible samples.",
) -> dict:
    def criterion(status: str) -> dict:
        return {"status": status, "evidence": f"Publication evidence: {status}."}

    return {
        "accession": accession,
        "human_samples": criterion(human_samples),
        "transcriptomics_assay": criterion(transcriptomics_assay),
        "established_fibrosis": criterion(established_fibrosis),
        "accession_linkage": criterion(accession_linkage),
        "confidence": confidence,
        "reason": reason,
    }


def test_thematic_reviewer_can_be_instantiated() -> None:
    assert isinstance(ThematicReviewer(), ThematicReviewer)


def test_thematic_reviewer_remains_exported_from_package_root() -> None:
    assert RootThematicReviewer is ThematicReviewer


def test_review_relevancy_directly_reviews_publication_and_accessions_once() -> None:
    gse1 = accession_assessment("GSE1")
    gse2 = accession_assessment(
        "GSE2",
        human_samples="fails",
        reason="The publication identifies this accession as mouse-only.",
    )
    decision = {"accession_assessments": [gse1, gse2]}
    fake_llm = FakeLLM(response=json.dumps(decision))

    result = ThematicReviewer(llm=fake_llm).review_relevancy(
        publication_text="GSE1 profiles human IPF. GSE2 profiles mice.",
        theme="fibrosis",
        metadata={"organism": "human", "tissue": "lung"},
        title="Fibrosis atlas publication",
        accessions=["GSE1", "GSE2", "GSE1"],
    )

    assert result == {
        "judgement": "relevant",
        "reasoning": "1 of 2 supplied accessions meets all theme criteria.",
        "confidence": "high",
        "accessions_to_remove": [
            {
                "accession": "GSE2",
                "reason": "The publication identifies this accession as mouse-only.",
                "confidence": "high",
            }
        ],
        "accession_assessments": [
            {**gse1, "decision": "qualifies"},
            {**gse2, "decision": "exclude"},
        ],
        "strategy": "direct",
    }
    assert len(fake_llm.calls) == 1
    assert "Publication Text:\nGSE1 profiles human IPF. GSE2 profiles mice." in (
        fake_llm.calls[0]["prompt"]
    )
    assert 'Accessions:\n[\n  "GSE1",\n  "GSE2"\n]' in fake_llm.calls[0]["prompt"]
    assert fake_llm.calls[0]["config"]["response_schema"] == (
        ThematicReviewer()._direct_review_response_schema()
    )


def test_review_relevancy_returns_evidence_decision_for_legacy_strategy() -> None:
    evidences = {
        "evidences": [
            {
                "evidence": "fibrotic tissue",
                "judgement": "relevant",
                "confidence": "high",
                "reason": "Directly names fibrotic tissue.",
            }
        ]
    }
    judgement = {
        "judgement": "relevant",
        "reasoning": "The evidence directly supports the theme.",
        "confidence": "high",
        "accessions_to_remove": [],
    }
    result = ThematicReviewer(
        llm=FakeLLM(responses=[json.dumps(evidences), json.dumps(judgement)])
    ).review_relevancy(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata={"organism": "human", "tissue": "lung"},
        title="Fibrosis atlas publication",
        accessions=["GSE1"],
        strategy="evidence_then_judgement",
    )

    assert result == {
        **judgement,
        "strategy": "evidence_then_judgement",
        "evidences": evidences,
    }
    assert len(result["evidences"]["evidences"]) == 1


def test_review_relevancy_passes_inputs_to_extract_evidence() -> None:
    class RecordingReviewer(ThematicReviewer):
        calls: list[dict] = []
        judge_calls: list[dict] = []

        def extract_evidence(
            self,
            publication_text=None,
            theme=None,
            metadata=None,
            title=None,
            accessions=None,
        ):
            self.__class__.calls.append(
                {
                    "publication_text": publication_text,
                    "theme": theme,
                    "metadata": metadata,
                    "title": title,
                    "accessions": accessions,
                }
            )
            return {"evidence": "matched"}

        def judge_evidence(self, evidences, theme=None, title=None, accessions=None):
            self.__class__.judge_calls.append(
                {
                    "evidences": evidences,
                    "theme": theme,
                    "title": title,
                    "accessions": accessions,
                }
            )
            return {
                "judgement": "relevant",
                "reasoning": "matched",
                "confidence": "high",
                "accessions_to_remove": [],
            }

    metadata = {"organism": "human", "tissue": "lung"}
    RecordingReviewer.calls = []
    RecordingReviewer.judge_calls = []

    result = RecordingReviewer().review_relevancy(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata=metadata,
        title="Fibrosis atlas publication",
        accessions=["GSE1"],
        strategy="evidence_then_judgement",
    )

    assert result == {
        "judgement": "relevant",
        "reasoning": "matched",
        "confidence": "high",
        "accessions_to_remove": [],
        "strategy": "evidence_then_judgement",
        "evidences": {"evidence": "matched"},
    }
    assert RecordingReviewer.calls == [
        {
            "publication_text": "Full publication text",
            "theme": "fibrosis",
            "metadata": metadata,
            "title": "Fibrosis atlas publication",
            "accessions": ["GSE1"],
        }
    ]
    assert RecordingReviewer.judge_calls == [
        {
            "evidences": {"evidence": "matched"},
            "theme": "fibrosis",
            "title": "Fibrosis atlas publication",
            "accessions": ["GSE1"],
        }
    ]


def test_review_relevancy_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="Unsupported thematic review strategy"):
        ThematicReviewer(llm=FakeLLM()).review_relevancy(
            publication_text="text",
            theme="fibrosis",
            strategy="unknown",
        )


def test_direct_review_drops_unknown_and_duplicate_accession_assessments(
    caplog,
) -> None:
    gse2 = accession_assessment("GSE2", human_samples="fails", reason="mouse")
    decision = {"accession_assessments": [
        gse2,
        accession_assessment("GSE2", human_samples="fails", reason="duplicate"),
        accession_assessment("GSE999", reason="invented"),
    ]}

    result = ThematicReviewer(
        llm=FakeLLM(response=json.dumps(decision))
    ).review_relevancy(
        publication_text="text",
        theme="fibrosis",
        accessions=["GSE1", "GSE2"],
    )

    assert result["accessions_to_remove"] == [
        {"accession": "GSE2", "reason": "mouse", "confidence": "high"}
    ]
    assert result["accession_assessments"][0]["accession"] == "GSE1"
    assert result["accession_assessments"][0]["decision"] == "uncertain"
    assert "unknown accession assessment" in caplog.text


@pytest.mark.parametrize(
    ("assessments", "judgement", "confidence"),
    [
        ([accession_assessment("GSE1")], "relevant", "high"),
        (
            [accession_assessment("GSE1", established_fibrosis="fails", confidence="medium")],
            "not_relevant",
            "medium",
        ),
        (
            [accession_assessment("GSE1", accession_linkage="uncertain", confidence="low")],
            "unsure",
            "low",
        ),
    ],
)
def test_direct_review_derives_publication_judgement_from_accession_criteria(
    assessments, judgement, confidence
) -> None:
    result = ThematicReviewer(
        llm=FakeLLM(response=json.dumps({"accession_assessments": assessments}))
    ).review_relevancy(
        publication_text="publication",
        theme="fibrosis",
        accessions=["GSE1"],
    )

    assert result["judgement"] == judgement
    assert result["confidence"] == confidence


def test_direct_review_schema_constrains_criteria_and_confidence() -> None:
    schema = ThematicReviewer()._direct_review_response_schema()
    assert schema["required"] == ["accession_assessments"]
    item = schema["properties"]["accession_assessments"]["items"]
    assert item["required"] == [
        "accession",
        "human_samples",
        "transcriptomics_assay",
        "established_fibrosis",
        "accession_linkage",
        "confidence",
        "reason",
    ]
    assert item["properties"]["confidence"]["enum"] == ["low", "medium", "high"]
    assert item["properties"]["human_samples"]["properties"]["status"]["enum"] == [
        "meets",
        "fails",
        "uncertain",
    ]


def test_direct_prompt_forbids_external_accession_knowledge_and_cohort_transfer() -> None:
    reviewer = ThematicReviewer()
    prompt = reviewer._direct_review_prompt(
        publication_text="A paper.",
        theme="fibrosis",
        metadata=[{"accession": "GSE1", "context": "Study: Compact context"}],
        accessions=["GSE1"],
    )

    assert "Never use remembered or external knowledge" in prompt
    assert "Never transfer evidence between cohorts" in prompt
    assert '"accession": "GSE1"' in prompt
    assert "Study: Compact context" in prompt


def test_judge_evidence_accepts_expected_inputs_and_returns_json() -> None:
    response = {
        "judgement": "relevant",
        "reasoning": "Evidence supports the theme.",
        "confidence": "high",
        "accessions_to_remove": [],
    }
    result = ThematicReviewer(llm=FakeLLM(response=json.dumps(response))).judge_evidence(
        evidences="matched evidence",
        theme="fibrosis",
        title="Fibrosis atlas publication",
    )

    assert result == response


def test_judge_evidence_generates_json_response_from_prompt() -> None:
    response = {
        "judgement": "relevant",
        "reasoning": "Evidence supports the theme.",
        "confidence": "high",
        "accessions_to_remove": [],
    }
    fake_llm = FakeLLM(response=json.dumps(response))
    reviewer = ThematicReviewer(llm=fake_llm)
    evidences = [
        {
            "evidence": "fibrotic tissue",
            "judgement": "relevant",
            "confidence": "direct",
            "reason": "Directly names fibrotic tissue.",
        }
    ]

    assert reviewer.judge_evidence(
        evidences=evidences,
        theme="fibrosis",
        title="Fibrosis atlas publication",
    ) == response
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0]["model"] is None
    assert fake_llm.calls[0]["config"] == {
        "max_output_tokens": 16384,
        "response_mime_type": "application/json",
        "response_schema": reviewer._judge_evidence_response_schema(),
    }
    assert fake_llm.calls[0]["extra_options"] == {}
    assert fake_llm.calls[0]["prompt"].startswith(JUDGE_EVIDENCE_PROMPT)
    assert "Theme:\nfibrosis" in fake_llm.calls[0]["prompt"]
    assert "Title:\nFibrosis atlas publication" in fake_llm.calls[0]["prompt"]
    assert "Evidences:\n[" in fake_llm.calls[0]["prompt"]
    assert '"evidence": "fibrotic tissue"' in fake_llm.calls[0]["prompt"]


def test_judge_evidence_response_schema_requires_judgement_fields() -> None:
    schema = ThematicReviewer()._judge_evidence_response_schema()

    assert schema == ThematicReviewer()._review_response_schema()
    assert schema["required"] == [
        "judgement",
        "reasoning",
        "confidence",
        "accessions_to_remove",
    ]


def test_judge_evidence_raises_value_error_for_invalid_json_response() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        ThematicReviewer(llm=FakeLLM(response="not json")).judge_evidence(
            evidences="matched evidence",
            theme="fibrosis",
            title="Fibrosis atlas publication",
        )


def test_extract_evidence_accepts_expected_inputs_and_returns_json() -> None:
    response = {
        "evidences": [
            {
                "evidence": "fibrotic tissue",
                "judgement": "relevant",
                "confidence": "high",
                "reason": "Directly names fibrotic tissue.",
            }
        ]
    }
    result = ThematicReviewer(llm=FakeLLM(response=json.dumps(response))).extract_evidence(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata={"organism": "human", "tissue": "lung"},
        title="Fibrosis atlas publication",
    )

    assert result == response


def test_extract_evidence_generates_json_response_from_prompt() -> None:
    response = {
        "evidences": [
            {
                "evidence": "fibrotic tissue",
                "judgement": "relevant",
                "confidence": "high",
                "reason": "Directly names fibrotic tissue.",
            }
        ]
    }
    fake_llm = FakeLLM(response=json.dumps(response))
    reviewer = ThematicReviewer(llm=fake_llm)

    assert reviewer.extract_evidence(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata={"organism": "human", "tissue": "lung"},
        title="Fibrosis atlas publication",
    ) == response
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0]["model"] is None
    assert fake_llm.calls[0]["config"] == {
        "max_output_tokens": 16384,
        "response_mime_type": "application/json",
        "response_schema": reviewer._evidence_response_schema(),
    }
    assert fake_llm.calls[0]["extra_options"] == {}
    assert fake_llm.calls[0]["prompt"].startswith(EVIDENCE_EXTRACTION_PROMPT)
    assert "Theme:\nfibrosis" in fake_llm.calls[0]["prompt"]
    assert "Title:\nFibrosis atlas publication" in fake_llm.calls[0]["prompt"]
    assert "Publication Text:\nFull publication text" in fake_llm.calls[0]["prompt"]
    assert '"organism": "human"' in fake_llm.calls[0]["prompt"]


def test_extract_evidence_raises_value_error_for_invalid_json_response() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        ThematicReviewer(llm=FakeLLM(response="not json")).extract_evidence(
            publication_text="Full publication text",
            theme="fibrosis",
            metadata={"organism": "human"},
            title="Fibrosis atlas publication",
        )


def test_evidence_response_schema_requires_evidence_fields() -> None:
    schema = ThematicReviewer()._evidence_response_schema()

    assert schema["type"] == "OBJECT"
    assert schema["required"] == ["evidences"]
    evidences = schema["properties"]["evidences"]
    assert evidences["type"] == "ARRAY"
    item = evidences["items"]
    assert item["type"] == "OBJECT"
    assert item["required"] == [
        "evidence",
        "judgement",
        "confidence",
        "reason",
    ]
    assert item["properties"] == {
        "evidence": {"type": "STRING"},
        "judgement": {"type": "STRING"},
        "confidence": {"type": "STRING"},
        "reason": {"type": "STRING"},
    }


def test_extract_evidence_builds_evidence_prompt_before_generation() -> None:
    class RecordingReviewer(ThematicReviewer):
        calls: list[dict] = []

        def _evidence_prompt(
            self,
            publication_text=None,
            theme=None,
            metadata=None,
            title=None,
            accessions=None,
        ):
            self.__class__.calls.append(
                {
                    "publication_text": publication_text,
                    "theme": theme,
                    "metadata": metadata,
                    "title": title,
                    "accessions": accessions,
                }
            )
            return "prompt"

    metadata = {"organism": "human", "tissue": "lung"}
    RecordingReviewer.calls = []
    fake_llm = FakeLLM()

    assert RecordingReviewer(llm=fake_llm).extract_evidence(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata=metadata,
        title="Fibrosis atlas publication",
    ) == {"response": "ok"}
    assert RecordingReviewer.calls == [
        {
            "publication_text": "Full publication text",
            "theme": "fibrosis",
            "metadata": metadata,
            "title": "Fibrosis atlas publication",
            "accessions": None,
        }
    ]


def test_judge_evidence_builds_judge_prompt_before_generation() -> None:
    class RecordingReviewer(ThematicReviewer):
        calls: list[dict] = []

        def _judge_evidence_prompt(
            self,
            evidences=None,
            theme=None,
            title=None,
            accessions=None,
        ):
            self.__class__.calls.append(
                {
                    "evidences": evidences,
                    "theme": theme,
                    "title": title,
                    "accessions": accessions,
                }
            )
            return "prompt"

    RecordingReviewer.calls = []
    fake_llm = FakeLLM()
    evidences = {"evidence": "matched"}

    assert RecordingReviewer(llm=fake_llm).judge_evidence(
        evidences=evidences,
        theme="fibrosis",
        title="Fibrosis atlas publication",
    ) == {
        "judgement": "",
        "reasoning": "",
        "confidence": "",
        "accessions_to_remove": [],
    }
    assert RecordingReviewer.calls == [
        {
            "evidences": evidences,
            "theme": "fibrosis",
            "title": "Fibrosis atlas publication",
            "accessions": None,
        }
    ]


def test_evidence_prompt_uses_labeled_blocks_with_string_metadata() -> None:
    prompt = ThematicReviewer()._evidence_prompt(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata="metadata text",
        title="Fibrosis atlas publication",
    )

    assert prompt.startswith(EVIDENCE_EXTRACTION_PROMPT)
    assert prompt == (
        f"{EVIDENCE_EXTRACTION_PROMPT}\n"
        "Theme:\n"
        "fibrosis\n"
        "\n"
        "Title:\n"
        "Fibrosis atlas publication\n"
        "\n"
        "Publication Text:\n"
        "Full publication text\n"
        "\n"
        "Metadata:\n"
        "metadata text\n"
        "\n"
        "Accessions:\n"
        "[]"
    )


def test_evidence_prompt_formats_dict_metadata_as_sorted_json() -> None:
    assert ThematicReviewer()._evidence_prompt(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata={"tissue": "lung", "organism": "human"},
        title="Fibrosis atlas publication",
    ) == (
        f"{EVIDENCE_EXTRACTION_PROMPT}\n"
        "Theme:\n"
        "fibrosis\n"
        "\n"
        "Title:\n"
        "Fibrosis atlas publication\n"
        "\n"
        "Publication Text:\n"
        "Full publication text\n"
        "\n"
        "Metadata:\n"
        "{\n"
        '  "organism": "human",\n'
        '  "tissue": "lung"\n'
        "}\n"
        "\n"
        "Accessions:\n"
        "[]"
    )


def test_thematic_reviewer_package_exports_reviewer_without_dev_atlas_side_effect() -> None:
    module = importlib.import_module("agentic_curator.curators.thematic_reviewer")

    assert module.ThematicReviewer is ThematicReviewer
    assert not hasattr(module, "atlas_data")
    assert not hasattr(module, "thematic_reviewer")


def test_old_flat_thematic_reviewer_module_was_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agentic_curator.thematic_reviewer")
