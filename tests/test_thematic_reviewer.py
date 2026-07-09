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


def test_thematic_reviewer_can_be_instantiated() -> None:
    assert isinstance(ThematicReviewer(), ThematicReviewer)


def test_thematic_reviewer_remains_exported_from_package_root() -> None:
    assert RootThematicReviewer is ThematicReviewer


def test_review_relevancy_returns_evidence_decision() -> None:
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
    }
    result = ThematicReviewer(
        llm=FakeLLM(responses=[json.dumps(evidences), json.dumps(judgement)])
    ).review_relevancy(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata={"organism": "human", "tissue": "lung"},
        title="Fibrosis atlas publication",
    )

    assert result == {
        "evidences": evidences,
        "judgement": judgement,
    }


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
        ):
            self.__class__.calls.append(
                {
                    "publication_text": publication_text,
                    "theme": theme,
                    "metadata": metadata,
                    "title": title,
                }
            )
            return {"evidence": "matched"}

        def judge_evidence(self, evidences, theme=None, title=None):
            self.__class__.judge_calls.append(
                {
                    "evidences": evidences,
                    "theme": theme,
                    "title": title,
                }
            )
            return {"judgement": "relevant"}

    metadata = {"organism": "human", "tissue": "lung"}
    RecordingReviewer.calls = []
    RecordingReviewer.judge_calls = []

    result = RecordingReviewer().review_relevancy(
        publication_text="Full publication text",
        theme="fibrosis",
        metadata=metadata,
        title="Fibrosis atlas publication",
    )

    assert result == {
        "evidences": {"evidence": "matched"},
        "judgement": {"judgement": "relevant"},
    }
    assert RecordingReviewer.calls == [
        {
            "publication_text": "Full publication text",
            "theme": "fibrosis",
            "metadata": metadata,
            "title": "Fibrosis atlas publication",
        }
    ]
    assert RecordingReviewer.judge_calls == [
        {
            "evidences": {"evidence": "matched"},
            "theme": "fibrosis",
            "title": "Fibrosis atlas publication",
        }
    ]


def test_judge_evidence_accepts_expected_inputs_and_returns_json() -> None:
    response = {
        "judgement": "relevant",
        "reasoning": "Evidence supports the theme.",
        "confidence": "high",
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

    assert schema == {
        "type": "OBJECT",
        "properties": {
            "judgement": {"type": "STRING"},
            "reasoning": {"type": "STRING"},
            "confidence": {"type": "STRING"},
        },
        "required": ["judgement", "reasoning", "confidence"],
    }


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
        ):
            self.__class__.calls.append(
                {
                    "publication_text": publication_text,
                    "theme": theme,
                    "metadata": metadata,
                    "title": title,
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
        ):
            self.__class__.calls.append(
                {
                    "evidences": evidences,
                    "theme": theme,
                    "title": title,
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
    ) == {"response": "ok"}
    assert RecordingReviewer.calls == [
        {
            "evidences": evidences,
            "theme": "fibrosis",
            "title": "Fibrosis atlas publication",
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
        "metadata text"
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
        "}"
    )


def test_thematic_reviewer_package_exports_reviewer_without_dev_atlas_side_effect() -> None:
    module = importlib.import_module("agentic_curator.curators.thematic_reviewer")

    assert module.ThematicReviewer is ThematicReviewer
    assert not hasattr(module, "atlas_data")
    assert not hasattr(module, "thematic_reviewer")


def test_old_flat_thematic_reviewer_module_was_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agentic_curator.thematic_reviewer")
