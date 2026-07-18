import inspect

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
    assert result["strategy"] == "ols"
    assert result["status"] == "matched"
    assert result["decision"] == "UBERON_0002048"
    assert "web_hits" not in result
    assert "web_search_error" not in result


def test_harmonizer_defaults_to_ols_and_rejects_removed_websearch_name() -> None:
    assert OntologyHarmonizer().harmonize(harmonization_targets=[])["strategy"] == "ols"
    with pytest.raises(ValueError, match="strategy"):
        OntologyHarmonizer().harmonize(
            harmonization_targets=[],
            strategy="websearch",
        )
