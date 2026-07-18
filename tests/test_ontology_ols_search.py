# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

import inspect
import json

import pytest

from agentic_curator.curators import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore, OlsStrategyHandler


class FakeOlsClient:
    def __init__(self, *, search_results, ontology_metadata):
        self.search_results = list(search_results)
        self.ontology_metadata = ontology_metadata
        self.search_calls = []

    def search(self, label, *, ontology_id=None, rows=25):
        self.search_calls.append(
            {"label": label, "ontology_id": ontology_id, "rows": rows}
        )
        return self.search_results.pop(0)

    def ontology(self, ontology_id):
        return self.ontology_metadata[ontology_id]


class RejectingLLM:
    def generate_response(self, *args, **kwargs):
        return json.dumps(
            {
                "decision": "false",
                "confidence": "none",
                "reason": "Sample identifiers are not harmonizable ontology labels.",
            }
        )


def test_ols_strategy_has_no_web_search_client_dependency() -> None:
    assert "search_client" not in inspect.signature(OlsStrategyHandler).parameters


def test_ols_strategy_uses_only_unrestricted_ols_after_local_miss() -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "ontology_name": "uberon",
        "short_form": "UBERON_0002048",
        "obo_id": "UBERON:0002048",
        "label": "lung",
    }
    client = FakeOlsClient(
        search_results=[[term]],
        ontology_metadata={
            "uberon": {
                "config": {
                    "id": "uberon",
                    "title": "Uber-anatomy ontology",
                    "description": "An anatomy ontology.",
                    "version": "2026-06-19",
                    "versionIri": "https://example.org/uberon.owl",
                }
            }
        },
    )
    target = {"id": "target-0", "hz_label": "lung"}

    result = OlsStrategyHandler(ols_client=client).handle(
        target,
        publication_context=None,
        ontostore=OntoStore(),
    )

    assert client.search_calls == [
        {"label": "lung", "ontology_id": None, "rows": 25}
    ]
    assert result["source"] == "ols"
    assert result["status"] == "matched"
    assert result["decision"] == "UBERON_0002048"
    assert "web_hits" not in result
    assert "web_search_error" not in result


def test_harmonizer_uses_fixed_local_rag_ols_workflow() -> None:
    assert OntologyHarmonizer().harmonize(harmonization_targets=[])["workflow"] == (
        "local_rag_ols"
    )


def test_lookup_judge_false_terminally_skips_search_and_field(
    monkeypatch, tmp_path
) -> None:
    json_path = tmp_path / "test.json"
    json_path.write_text("{}", encoding="utf-8")
    store = OntoStore(
        ontology_frameworks={
            "test": {"path": tmp_path / "test.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )
    monkeypatch.setattr(
        store,
        "lookup_with_metadata",
        lambda label, ontology_id: {
            "match_type": "exact",
            "hits": [
                {
                    "id": "TEST:1",
                    "title": "sample one",
                    "ontology_id": ontology_id,
                }
            ],
            "ranking": [],
        },
    )

    class NoProceedingStepsHarmonizer(OntologyHarmonizer):
        def harmonize_label(self, *args, **kwargs):
            raise AssertionError("lookup rejection must not call OLS search")

        def harmonize_field(self, *args, **kwargs):
            raise AssertionError("lookup rejection must not harmonize the field")

    target = {
        "id": "sample-id-target",
        "pre_hz_field": "sample id",
        "pre_hz_label": "sample one",
        "ontology_ids": ["test"],
    }
    result = NoProceedingStepsHarmonizer(
        ontostore=store,
        llm=RejectingLLM(),
    ).harmonize(target=target)

    assert result["harmonization_targets"] == [target]
    assert target["harmonization_status"] == "skipped"
    assert target["harmonization_skip"] == {
        "stage": "lookup_judge",
        "decision": "false",
        "confidence": "none",
        "reason": "Sample identifiers are not harmonizable ontology labels.",
    }
    assert target["ontology_match"] is False


@pytest.mark.parametrize(
    "target",
    [
        {"hz_label": "sample one", "ontology_id": "test"},
        {"hz_label": "sample one"},
    ],
)
def test_ols_judge_false_is_terminal_skip(
    target,
) -> None:
    client = FakeOlsClient(
        search_results=[
            [
                {
                    "iri": "https://example.org/1",
                    "ontology_name": "test",
                    "short_form": "TEST_1",
                    "label": "sample one",
                }
            ]
        ],
        ontology_metadata={},
    )

    result = OlsStrategyHandler(
        ols_client=client,
        search_judge=lambda **kwargs: {
            "decision": "false",
            "confidence": "none",
            "reason": "Identifier target should be skipped.",
        },
    ).handle(target, publication_context=None, ontostore=OntoStore())

    assert result["status"] == "skipped"
    assert result["decision"] == "false"
    assert result["search_llm_judgements"][-1]["stage"] == "unrestricted"
    assert client.search_calls == [
        {"label": "sample one", "ontology_id": None, "rows": 25}
    ]


def test_ols_judge_reserves_preferred_candidates_within_fixed_limit() -> None:
    terms = [
        {
            "iri": f"https://example.org/general/{index}",
            "ontology_name": "general",
            "short_form": f"GENERAL_{index}",
            "label": f"general {index}",
        }
        for index in range(10)
    ] + [
        {
            "iri": f"https://example.org/preferred/{index}",
            "ontology_name": "preferred",
            "short_form": f"PREFERRED_{index}",
            "label": f"preferred {index}",
        }
        for index in range(3)
    ]
    client = FakeOlsClient(search_results=[terms], ontology_metadata={})
    calls = []
    store = OntoStore(
        ontology_frameworks={
            "preferred": {"url": "https://example.org/preferred.owl"},
        },
        preferred_ontology_ids=["preferred"],
    )

    result = OlsStrategyHandler(
        ols_client=client,
        search_judge=lambda **kwargs: calls.append(kwargs)
        or {
            "decision": "false",
            "confidence": "none",
            "reason": "test",
        },
    ).handle(
        {"hz_label": "sample one"},
        publication_context=None,
        ontostore=store,
    )

    assert result["status"] == "skipped"
    assert [hit["id"] for hit in calls[0]["unrestricted_hits"]] == [
        "PREFERRED_0",
        "PREFERRED_1",
        "GENERAL_0",
        "GENERAL_1",
        "GENERAL_2",
        "GENERAL_3",
        "GENERAL_4",
        "GENERAL_5",
        "GENERAL_6",
        "GENERAL_7",
    ]
    assert calls[0]["preferred_ontology_ids"] == ("preferred",)


def test_apply_targets_ignores_terminally_skipped_target() -> None:
    miniml = {"sample": {"characteristics": "sample one"}}
    target = {
        "hz_field": "sample id",
        "hz_label": "sample one",
        "harmonization_status": "skipped",
        "pre_hz_field_path": "/sample/characteristics",
        "pre_hz_label_path": "/sample/characteristics",
        "parent_path": "/sample",
    }

    result = OntologyHarmonizer().apply_targets(miniml, [target])

    assert result == {"sample": {"characteristics": "sample one"}}


def test_ols_skip_bypasses_field_and_later_target_continues() -> None:
    field_calls = []

    class MixedOutcomeHarmonizer(OntologyHarmonizer):
        def lookup_label(self, target, **kwargs):
            if target["id"] == "skip-me":
                return False
            target["ontology_match"] = True
            target["ontology_lookup"] = {
                "id": "UBERON:0002048",
                "title": "lung",
                "ontology_id": "uberon",
            }
            return target["ontology_lookup"]

        def harmonize_label(self, target, **kwargs):
            return OlsStrategyHandler(
                ols_client=FakeOlsClient(
                    search_results=[
                        [
                            {
                                "iri": "https://example.org/1",
                                "ontology_name": "test",
                                "short_form": "TEST_1",
                                "label": "sample one",
                            }
                        ]
                    ],
                    ontology_metadata={},
                ),
                search_judge=lambda **judge_kwargs: {
                    "decision": "false",
                    "confidence": "none",
                    "reason": "Identifier target should be skipped.",
                },
            ).handle(
                target,
                publication_context=kwargs["publication_context"],
                ontostore=kwargs["ontostore"],
            )

        def harmonize_field(self, target, **kwargs):
            field_calls.append(target["id"])
            return False

    targets = [
        {"id": "skip-me", "pre_hz_field": "sample id", "pre_hz_label": "sample one"},
        {"id": "continue", "pre_hz_field": "tissue", "pre_hz_label": "lung"},
    ]

    result = MixedOutcomeHarmonizer().harmonize(harmonization_targets=targets)

    assert result["harmonization_targets"][0]["harmonization_status"] == "skipped"
    assert result["harmonization_targets"][1]["ontology_match"] is True
    assert field_calls == ["continue"]


def test_lookup_llm_threshold_is_removed_from_public_methods() -> None:
    for method in (
        OntologyHarmonizer.harmonize,
        OntologyHarmonizer.harmonize_miniml_json,
        OntologyHarmonizer.lookup_label,
    ):
        assert "lookup_llm_threshold" not in inspect.signature(method).parameters
