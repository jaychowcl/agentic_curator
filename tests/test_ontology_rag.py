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
from types import SimpleNamespace

import numpy as np

from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore
from agentic_curator.cli.cli_ontology_harmonizer import _build_parser
from agentic_curator.wrappers import GeminiEmbeddingProvider


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


def test_url_backed_framework_with_local_cache_is_automatically_selected(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "cached.json"
    _write_toy_ontology(json_path)
    store = OntoStore(
        ontology_frameworks={
            "cached": {
                "url": "https://example.org/cached.owl",
                "json_path": json_path,
            },
            "remote": {"url": "https://example.org/remote.owl"},
        },
        storage_dir=tmp_path,
    )

    assert OntologyHarmonizer()._candidate_ontology_ids({}, store) == ["cached"]


def test_explicit_uncached_framework_is_not_selected_or_downloaded(
    tmp_path: Path,
) -> None:
    store = OntoStore(
        ontology_frameworks={
            "remote": {"url": "https://example.org/remote.owl"},
        },
        storage_dir=tmp_path,
    )

    assert OntologyHarmonizer()._candidate_ontology_ids(
        {"ontology_ids": ["remote"]}, store
    ) == []


def test_lookup_rag_many_embeds_query_once_and_searches_frameworks_in_order(
    tmp_path: Path,
) -> None:
    provider = FakeEmbeddingProvider()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    _write_toy_ontology(first_path)
    _write_toy_ontology(second_path)
    store = OntoStore(
        ontology_frameworks={
            "first": {"json_path": first_path, "owl_path": tmp_path / "first.owl"},
            "second": {"json_path": second_path, "owl_path": tmp_path / "second.owl"},
        },
        storage_dir=tmp_path,
        embedding_provider=provider,
    )

    result = store.lookup_rag_many(
        "breathing structure", ["first", "second"], top_k=1
    )

    assert provider.query_calls == ["breathing structure"]
    assert [hit["ontology_id"] for hit in result["hits"]] == ["first", "second"]
    assert result["errors"] == []


def test_lookup_rag_many_isolates_one_framework_index_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = FakeEmbeddingProvider()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    _write_toy_ontology(first_path)
    _write_toy_ontology(second_path)
    store = OntoStore(
        ontology_frameworks={
            "first": {"json_path": first_path, "owl_path": tmp_path / "first.owl"},
            "second": {
                "json_path": second_path,
                "owl_path": tmp_path / "second.owl",
            },
        },
        storage_dir=tmp_path,
        embedding_provider=provider,
    )
    build_rag_index = store.build_rag_index

    def build_with_one_failure(ontology_id: str) -> Path:
        if ontology_id == "second":
            raise RuntimeError("broken ontology cache")
        return build_rag_index(ontology_id)

    monkeypatch.setattr(store, "build_rag_index", build_with_one_failure)

    result = store.lookup_rag_many("breathing structure", ["first", "second"])

    assert provider.query_calls == ["breathing structure"]
    assert {hit["ontology_id"] for hit in result["hits"]} == {"first"}
    assert result["errors"] == [
        {"ontology_id": "second", "error": "broken ontology cache"}
    ]


def test_rag_judge_reserves_two_candidates_for_each_qualifying_ontology(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ontology_ids = [f"ontology_{index}" for index in range(6)]
    frameworks = {}
    hits = []
    for framework_index, ontology_id in enumerate(ontology_ids):
        owl_path = tmp_path / f"{ontology_id}.owl"
        owl_path.write_text("cached", encoding="utf-8")
        frameworks[ontology_id] = {"owl_path": owl_path}
        for hit_index in range(3):
            hits.append(
                {
                    "id": f"{ontology_id}:{hit_index}",
                    "title": f"{ontology_id} term {hit_index}",
                    "ontology_id": ontology_id,
                    "rag_score": 0.99 - (framework_index * 0.02) - (hit_index * 0.005),
                }
            )
    store = OntoStore(ontology_frameworks=frameworks, storage_dir=tmp_path)
    monkeypatch.setattr(
        store,
        "lookup_rag_many",
        lambda label, selected_ids, top_k: {"hits": hits, "errors": []},
    )

    class CapturingHarmonizer(OntologyHarmonizer):
        def __init__(self) -> None:
            super().__init__()
            self.judge_calls: list[list[dict[str, object]]] = []

        def judge_lookup(self, *args, hits, **kwargs):
            self.judge_calls.append(hits)
            return {
                "decision": hits[0]["id"],
                "confidence": "high",
                "reason": "Best balanced candidate.",
            }

    harmonizer = CapturingHarmonizer()
    target = {
        "hz_label": "target label",
        "ontology_ids": ontology_ids,
    }

    harmonizer.lookup_rag_label(
        target,
        publication_context=None,
        ontostore=store,
    )

    assert len(harmonizer.judge_calls) == 1
    judged_hits = harmonizer.judge_calls[0]
    assert len(judged_hits) == 12
    assert {
        ontology_id: sum(hit["ontology_id"] == ontology_id for hit in judged_hits)
        for ontology_id in ontology_ids
    } == {ontology_id: 2 for ontology_id in ontology_ids}
    assert target["ontology_rag"]["hits"] == judged_hits
    assert target["ontology_rag"]["similarity_thresholds"] == {
        ontology_id: 0.5 for ontology_id in ontology_ids
    }


def test_rag_balance_fills_ten_slots_after_reserving_two_per_ontology(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ontology_ids = ["dominant", "specialist"]
    frameworks = {}
    for ontology_id in ontology_ids:
        owl_path = tmp_path / f"{ontology_id}.owl"
        owl_path.write_text("cached", encoding="utf-8")
        frameworks[ontology_id] = {"owl_path": owl_path}
    hits = [
        {
            "id": f"DOM:{index}",
            "ontology_id": "dominant",
            "title": f"dominant {index}",
            "rag_score": 0.99 - (index * 0.01),
        }
        for index in range(10)
    ] + [
        {
            "id": f"SPEC:{index}",
            "ontology_id": "specialist",
            "title": f"specialist {index}",
            "rag_score": 0.60 - (index * 0.01),
        }
        for index in range(10)
    ]
    store = OntoStore(ontology_frameworks=frameworks, storage_dir=tmp_path)
    monkeypatch.setattr(
        store,
        "lookup_rag_many",
        lambda label, selected_ids, top_k: {"hits": hits, "errors": []},
    )

    class CapturingHarmonizer(OntologyHarmonizer):
        def judge_lookup(self, *args, hits, **kwargs):
            self.judged_hits = hits
            return {
                "decision": hits[0]["id"],
                "confidence": "high",
                "reason": "Best balanced candidate.",
            }

    harmonizer = CapturingHarmonizer()
    harmonizer.lookup_rag_label(
        {"hz_label": "target", "ontology_ids": ontology_ids},
        publication_context=None,
        ontostore=store,
    )

    assert len(harmonizer.judged_hits) == 10
    assert sum(hit["ontology_id"] == "specialist" for hit in harmonizer.judged_hits) == 2


def test_rag_thresholds_filter_before_reservation_and_allow_framework_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ontology_ids = ["strict", "default", "weak"]
    frameworks = {}
    for ontology_id in ontology_ids:
        owl_path = tmp_path / f"{ontology_id}.owl"
        owl_path.write_text("cached", encoding="utf-8")
        frameworks[ontology_id] = {"owl_path": owl_path}
    frameworks["strict"]["rag_similarity_threshold"] = 0.7
    hits = [
        {"id": "STRICT:1", "ontology_id": "strict", "rag_score": 0.69},
        {"id": "DEFAULT:1", "ontology_id": "default", "rag_score": 0.50},
        {"id": "WEAK:1", "ontology_id": "weak", "rag_score": 0.49},
    ]
    store = OntoStore(ontology_frameworks=frameworks, storage_dir=tmp_path)
    monkeypatch.setattr(
        store,
        "lookup_rag_many",
        lambda label, selected_ids, top_k: {"hits": hits, "errors": []},
    )

    class CapturingHarmonizer(OntologyHarmonizer):
        def judge_lookup(self, *args, hits, **kwargs):
            self.judged_hits = hits
            return {
                "decision": hits[0]["id"],
                "confidence": "high",
                "reason": "Only qualifying candidate.",
            }

    harmonizer = CapturingHarmonizer(rag_similarity_threshold=0.5)
    target = {"hz_label": "target", "ontology_ids": ontology_ids}
    harmonizer.lookup_rag_label(
        target,
        publication_context=None,
        ontostore=store,
    )

    assert [hit["id"] for hit in harmonizer.judged_hits] == ["DEFAULT:1"]
    assert target["ontology_rag"]["similarity_thresholds"] == {
        "strict": 0.7,
        "default": 0.5,
        "weak": 0.5,
    }


def test_rag_deduplicates_within_an_ontology_but_not_across_ontologies() -> None:
    harmonizer = OntologyHarmonizer()
    hits = [
        {"id": "SHARED:1", "ontology_id": "first", "rag_score": 0.9},
        {"id": "SHARED:1", "ontology_id": "first", "rag_score": 0.8},
        {"id": "SHARED:1", "ontology_id": "second", "rag_score": 0.7},
    ]

    balanced = harmonizer._balance_rag_hits(
        hits,
        ontology_ids=["first", "second"],
        thresholds={"first": 0.5, "second": 0.5},
    )

    assert [(hit["ontology_id"], hit["rag_score"]) for hit in balanced] == [
        ("first", 0.9),
        ("second", 0.7),
    ]


def test_reused_rag_index_is_viewed_from_disk_instead_of_loaded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = FakeEmbeddingProvider()
    store = _toy_store(tmp_path, provider)
    store.build_rag_index("toy")
    viewed: list[Path] = []

    class ViewingIndex:
        def __init__(self, **kwargs):
            pass

        def view(self, path):
            viewed.append(Path(path))

        def load(self, path):
            raise AssertionError("RAG queries must not load the full index")

        def __len__(self):
            return 2

        def search(self, query, count):
            return SimpleNamespace(
                keys=np.asarray([0], dtype=np.uint64),
                distances=np.asarray([0.1], dtype=np.float32),
            )

    monkeypatch.setattr("usearch.index.Index", ViewingIndex)

    assert store.lookup_rag("breathing structure", "toy", top_k=1)
    assert viewed == [store.build_rag_index("toy")]


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


def test_lookup_judge_prompt_receives_ordered_preferred_ontologies() -> None:
    prompt = OntologyHarmonizer()._judge_lookup_prompt(
        target={"pre_hz_field": "source", "pre_hz_label": "pulmonary sample"},
        publication_context=None,
        metadata_context=None,
        hits=[
            {"id": "CUSTOM:1", "title": "lung", "ontology_id": "custom"}
        ],
        preferred_ontology_ids=("custom", "uberon"),
    )

    assert "Preferred Ontologies" in prompt
    assert prompt.index('"custom"') < prompt.index('"uberon"')


def test_direct_lookup_reserves_two_candidates_per_preferred_ontology(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ontology_ids = ["general", "preferred_a", "preferred_b"]
    frameworks = {}
    for ontology_id in ontology_ids:
        owl_path = tmp_path / f"{ontology_id}.owl"
        owl_path.write_text("cached", encoding="utf-8")
        frameworks[ontology_id] = {"owl_path": owl_path}
    store = OntoStore(
        ontology_frameworks=frameworks,
        preferred_ontology_ids=["preferred_a", "preferred_b"],
        storage_dir=tmp_path,
    )
    hits_by_ontology = {
        "general": [
            {"id": f"GENERAL:{index}", "ontology_id": "general"}
            for index in range(10)
        ],
        "preferred_a": [
            {"id": f"A:{index}", "ontology_id": "preferred_a"}
            for index in range(3)
        ],
        "preferred_b": [
            {"id": f"B:{index}", "ontology_id": "preferred_b"}
            for index in range(3)
        ],
    }
    monkeypatch.setattr(
        store,
        "lookup_with_metadata",
        lambda label, ontology_id: {
            "match_type": "exact",
            "hits": hits_by_ontology[ontology_id],
            "ranking": [],
        },
    )

    class CapturingHarmonizer(OntologyHarmonizer):
        def judge_lookup(self, *args, hits, **kwargs):
            self.judged_hits = hits
            self.preferred_ontology_ids = kwargs["preferred_ontology_ids"]
            return {
                "decision": hits[0]["id"],
                "confidence": "high",
                "reason": "Preferred suitable term.",
            }

    harmonizer = CapturingHarmonizer(ontostore=store)
    harmonizer.lookup_label(
        {"hz_label": "lung", "ontology_ids": ontology_ids},
        publication_context=None,
        ontostore=store,
    )

    assert [hit["id"] for hit in harmonizer.judged_hits] == [
        "A:0",
        "B:0",
        "A:1",
        "B:1",
        "GENERAL:0",
        "GENERAL:1",
        "GENERAL:2",
        "GENERAL:3",
        "GENERAL:4",
        "GENERAL:5",
    ]
    assert harmonizer.preferred_ontology_ids == ("preferred_a", "preferred_b")


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


def test_gemini_embeddings_use_retrieval_tasks_and_batch_documents() -> None:
    requests: list[dict] = []

    class FakeModels:
        def embed_content(self, **kwargs):
            requests.append(kwargs)
            dimensions = kwargs["config"].output_dimensionality
            return SimpleNamespace(
                embeddings=[
                    SimpleNamespace(values=[0.5] * dimensions)
                    for _ in kwargs["contents"]
                ]
            )

    provider = GeminiEmbeddingProvider(
        dimensions=2,
        client=SimpleNamespace(models=FakeModels()),
    )

    documents = provider.embed_documents([f"term {index}" for index in range(251)])
    query = provider.embed_query("pulmonary structure")

    assert len(documents) == 251
    assert query == [0.5, 0.5]
    assert [len(request["contents"]) for request in requests] == [250, 1, 1]
    assert [str(request["config"].task_type) for request in requests] == [
        "RETRIEVAL_DOCUMENT",
        "RETRIEVAL_DOCUMENT",
        "RETRIEVAL_QUERY",
    ]
    assert all(request["model"] == "gemini-embedding-001" for request in requests)
