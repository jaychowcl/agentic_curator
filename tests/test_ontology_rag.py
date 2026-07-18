# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

import inspect
import json
from pathlib import Path

from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore
from agentic_curator.cli.cli_ontology_harmonizer import _build_parser


class FakeEmbeddingProvider:
    model = "fake-embedding"
    dimensions = 2

    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        lowered = text.lower()
        return [1.0, 0.0] if "lung" in lowered or "breathing" in lowered else [0.0, 1.0]


def _write_toy_ontology(path: Path) -> None:
    lung = {
        "id": "UBERON_0002048",
        "accession": "UBERON:0002048",
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "title": "lung",
        "description": "Respiratory organ used for breathing.",
        "synonyms": {"exact": ["pulmonary organ"]},
    }
    heart = {
        "id": "UBERON_0000948",
        "accession": "UBERON:0000948",
        "iri": "http://purl.obolibrary.org/obo/UBERON_0000948",
        "title": "heart",
        "description": "Muscular blood-pumping organ.",
        "synonyms": {"exact": ["cardiac organ"]},
    }
    payload = {
        "ontology": {"id": "toy"},
        "terms": {
            "label": {"lung": [lung], "heart": [heart]},
            "id": {lung["id"].lower(): lung, heart["id"].lower(): heart},
            "accession": {
                lung["accession"].lower(): lung,
                heart["accession"].lower(): heart,
            },
            "iri": {lung["iri"].lower(): lung, heart["iri"].lower(): heart},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _toy_store(tmp_path: Path, provider: FakeEmbeddingProvider) -> OntoStore:
    json_path = tmp_path / "toy.json"
    if not json_path.exists():
        _write_toy_ontology(json_path)
    return OntoStore(
        ontology_frameworks={
            "toy": {
                "owl_path": tmp_path / "toy.owl",
                "json_path": json_path,
                "title": "Toy anatomy",
            }
        },
        storage_dir=tmp_path,
        embedding_provider=provider,
    )


def test_lookup_rag_builds_reuses_and_returns_semantic_top_k(tmp_path: Path) -> None:
    first_provider = FakeEmbeddingProvider()
    first_store = _toy_store(tmp_path, first_provider)

    hits = first_store.lookup_rag("breathing structure", "toy", top_k=1)

    assert [hit["id"] for hit in hits] == ["UBERON_0002048"]
    assert hits[0]["ontology_id"] == "toy"
    assert isinstance(hits[0]["rag_score"], float)
    assert len(first_provider.document_calls) == 1
    assert len(first_provider.document_calls[0]) == 2
    assert any(
        "Term: lung" in chunk and "Synonyms: pulmonary organ" in chunk
        for chunk in first_provider.document_calls[0]
    )
    assert first_provider.query_calls == ["breathing structure"]

    second_provider = FakeEmbeddingProvider()
    second_store = _toy_store(tmp_path, second_provider)
    reused = second_store.lookup_rag("breathing structure", "toy", top_k=1)

    assert [hit["id"] for hit in reused] == ["UBERON_0002048"]
    assert second_provider.document_calls == []
    assert second_provider.query_calls == ["breathing structure"]


def test_lookup_rag_does_not_download_uncached_framework(tmp_path: Path) -> None:
    provider = FakeEmbeddingProvider()
    store = OntoStore(
        ontology_frameworks={
            "remote": {
                "url": "https://example.org/remote.owl",
                "title": "Remote ontology",
            }
        },
        storage_dir=tmp_path,
        embedding_provider=provider,
    )

    assert store.lookup_rag("lung", "remote") == []
    assert provider.document_calls == []
    assert provider.query_calls == []


def test_fixed_workflow_removes_strategy_public_api_and_cli() -> None:
    assert "strategy" not in inspect.signature(OntologyHarmonizer.harmonize).parameters
    assert "strategy" not in inspect.signature(
        OntologyHarmonizer.harmonize_miniml_json
    ).parameters
    assert "strategy" not in inspect.signature(
        OntologyHarmonizer.harmonize_label
    ).parameters

    parser = _build_parser()
    parsed = parser.parse_args(
        ["harmonize", "--target", '{"pre_hz_label": "lung"}', "--no-llm"]
    )
    assert not hasattr(parsed, "strategy")


def test_lookup_judge_contract_accepts_no_match() -> None:
    prompt = OntologyHarmonizer()._judge_lookup_prompt(
        target={"pre_hz_field": "source", "pre_hz_label": "pulmonary sample"},
        publication_context=None,
        metadata_context=None,
        hits=[{"id": "UBERON_0002048", "title": "lung"}],
    )

    assert '"no_match"' in prompt
    assert '"false"' in prompt


def test_lookup_judge_no_match_falls_through_without_skipping_target() -> None:
    class NoMatchHarmonizer(OntologyHarmonizer):
        def judge_lookup(self, *args, **kwargs):
            return {
                "decision": "no_match",
                "confidence": "high",
                "reason": "Candidates are semantically unrelated.",
            }

    target = {"id": "target-0", "hz_label": "lung"}
    selected = NoMatchHarmonizer()._select_lookup_hit(
        target=target,
        publication_context=None,
        hits=[{"id": "UBERON_0000948", "title": "heart"}],
        lookup_llm_judge=True,
        source="rag",
    )

    assert selected is False
    assert "harmonization_skip" not in target
    assert target["ontology_lookup_judgements"][0]["source"] == "rag"


def test_fixed_workflow_calls_local_then_rag_then_ols() -> None:
    calls: list[str] = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def lookup_label(self, *args, **kwargs):
            calls.append("local")
            return False

        def lookup_rag_label(self, *args, **kwargs):
            calls.append("rag")
            return False

        def harmonize_label(self, target, **kwargs):
            calls.append("ols")
            result = {"source": "ols", "status": "not_harmonized"}
            target["ontology_ols_result"] = result
            return result

        def harmonize_field(self, *args, **kwargs):
            calls.append("field")
            return False

    result = RecordingHarmonizer(llm=object()).harmonize(
        target={"id": "target-0", "pre_hz_label": "pulmonary structure"}
    )

    assert calls == ["local", "rag", "ols", "field"]
    assert result["workflow"] == "local_rag_ols"
