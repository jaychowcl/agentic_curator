# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

import json

import pytest

from agentic_curator import QueryGenerator as RootQueryGenerator
from agentic_curator.curators import QueryGenerator


class FakeLLM:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []

    def generate_response(self, prompt, *, model=None, config=None, **extra_options):
        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "config": config,
                "extra_options": extra_options,
            }
        )
        return self.response


def response(*details, summary="Broad disease and mechanism terminology.") -> str:
    return json.dumps({"details": list(details), "strategy_summary": summary})


def test_query_generator_is_exported_from_public_packages() -> None:
    assert RootQueryGenerator is QueryGenerator


def test_generate_queries_returns_dataset_filtered_epmc_queries() -> None:
    llm = FakeLLM(
        response(
            {
                "query": 'TITLE_ABS:(fibrosis OR fibrotic)',
                "purpose": "Capture direct fibrosis terminology.",
            },
            {
                "query": 'TITLE_ABS:("extracellular matrix" AND remodel*)',
                "purpose": "Capture core fibrotic mechanisms.",
            },
        )
    )

    result = QueryGenerator(llm=llm).generate_queries(
        "Include publications about fibrosis and fibrotic biology.",
        max_queries=3,
    )

    expected_queries = [
        '(TITLE_ABS:(fibrosis OR fibrotic)) AND (HAS_DATA:y OR HAS_LABSLINKS:y)',
        '(TITLE_ABS:("extracellular matrix" AND remodel*)) AND '
        '(HAS_DATA:y OR HAS_LABSLINKS:y)',
    ]
    assert result == {
        "queries": expected_queries,
        "details": [
            {
                "query": expected_queries[0],
                "purpose": "Capture direct fibrosis terminology.",
            },
            {
                "query": expected_queries[1],
                "purpose": "Capture core fibrotic mechanisms.",
            },
        ],
        "strategy_summary": "Broad disease and mechanism terminology.",
    }
    assert len(llm.calls) == 1
    assert "Include publications about fibrosis" in llm.calls[0]["prompt"]
    assert "Maximum Queries:\n3" in llm.calls[0]["prompt"]
    assert llm.calls[0]["config"] == {
        "response_mime_type": "application/json",
        "response_schema": QueryGenerator()._response_schema(max_queries=3),
    }


@pytest.mark.parametrize("theme", [None, "", "  \n "])
def test_generate_queries_rejects_empty_theme(theme) -> None:
    llm = FakeLLM(response())

    with pytest.raises(ValueError, match="theme"):
        QueryGenerator(llm=llm).generate_queries(theme)

    assert llm.calls == []


@pytest.mark.parametrize("max_queries", [0, 4, True, 1.5, "3"])
def test_generate_queries_rejects_invalid_max_queries(max_queries) -> None:
    with pytest.raises(ValueError, match="max_queries"):
        QueryGenerator(llm=FakeLLM(response())).generate_queries(
            "fibrosis",
            max_queries=max_queries,
        )


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"details": [], "strategy_summary": "summary"}, "at least one"),
        (
            {
                "details": [
                    {"query": "fibrosis", "purpose": "one"},
                    {"query": " fibrosis ", "purpose": "two"},
                ],
                "strategy_summary": "summary",
            },
            "unique",
        ),
        (
            {
                "details": [{"query": "HAS_DATA:y", "purpose": "bad"}],
                "strategy_summary": "summary",
            },
            "dataset filters",
        ),
        (
            {
                "details": [{"query": "fibrosis", "purpose": ""}],
                "strategy_summary": "summary",
            },
            "purpose",
        ),
        (
            {
                "details": [{"query": "fibrosis", "purpose": "valid"}],
                "strategy_summary": "",
            },
            "strategy_summary",
        ),
    ],
)
def test_generate_queries_rejects_invalid_structured_responses(payload, message) -> None:
    with pytest.raises(ValueError, match=message):
        QueryGenerator(llm=FakeLLM(payload)).generate_queries("fibrosis")


def test_generate_queries_rejects_more_than_requested() -> None:
    details = [
        {"query": f"term-{index}", "purpose": f"purpose-{index}"}
        for index in range(3)
    ]

    with pytest.raises(ValueError, match="max_queries"):
        QueryGenerator(llm=FakeLLM(response(*details))).generate_queries(
            "fibrosis",
            max_queries=2,
        )


def test_generate_queries_rejects_non_json_response() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        QueryGenerator(llm=FakeLLM("not json")).generate_queries("fibrosis")


def test_query_generator_lazily_creates_default_llm(monkeypatch) -> None:
    created = []

    class DefaultLLM(FakeLLM):
        def __init__(self):
            created.append(True)
            super().__init__(
                response(
                    {"query": "fibrosis", "purpose": "Direct terminology."}
                )
            )

    monkeypatch.setattr(
        "agentic_curator.curators.query_generator.generator.LLM",
        DefaultLLM,
    )
    generator = QueryGenerator()
    assert created == []

    generator.generate_queries("fibrosis")

    assert created == [True]

