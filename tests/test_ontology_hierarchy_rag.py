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
import math
import sqlite3
from pathlib import Path

import pytest

from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore


class HierarchyEmbeddingProvider:
    model = "hierarchy-embedding"
    dimensions = 2

    SCORES = {
        "lung": 1.0,
        "left lung": 0.95,
        "thoracic structure": 0.90,
        "right lung": 0.85,
        "organ": 0.80,
        "entity": 0.70,
        "orphan": 0.20,
    }

    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [self._document_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [1.0, 0.0]

    def _document_vector(self, text: str) -> list[float]:
        title = next(
            line.removeprefix("Term: ").lower()
            for line in text.splitlines()
            if line.startswith("Term: ")
        )
        score = self.SCORES[title]
        return [score, math.sqrt(max(0.0, 1.0 - score**2))]


def _term(identifier: str, title: str, *parents: str) -> dict[str, object]:
    compact = identifier.replace(":", "_")
    return {
        "id": compact,
        "accession": identifier,
        "iri": f"https://example.org/{compact}",
        "title": title,
        "description": f"Definition of {title}.",
        "parents": list(parents),
        "parent_iris": [
            f"https://example.org/{parent.replace(':', '_')}" for parent in parents
        ],
        "synonyms": {},
    }


def _write_hierarchy_json(path: Path) -> None:
    terms = [
        _term("TEST:0", "entity"),
        _term("TEST:1", "organ", "TEST:0"),
        _term("TEST:2", "thoracic structure", "TEST:0"),
        _term("TEST:3", "lung", "TEST:1", "TEST:2"),
        _term("TEST:4", "left lung", "TEST:3"),
        _term("TEST:5", "right lung", "TEST:3"),
        _term("TEST:6", "orphan", "EXTERNAL:1"),
    ]
    payload = {
        "ontology": {"id": "test"},
        "terms": {
            "label": {str(term["title"]).lower(): term for term in terms},
            "id": {str(term["id"]).lower(): term for term in terms},
            "accession": {
                str(term["accession"]).lower(): term for term in terms
            },
            "iri": {str(term["iri"]).lower(): term for term in terms},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _hierarchy_store(
    tmp_path: Path,
    provider: HierarchyEmbeddingProvider | None = None,
) -> OntoStore:
    json_path = tmp_path / "test.json"
    _write_hierarchy_json(json_path)
    return OntoStore(
        ontology_frameworks={
            "test": {
                "json_path": json_path,
                "owl_path": tmp_path / "test.owl",
            }
        },
        storage_dir=tmp_path,
        embedding_provider=provider or HierarchyEmbeddingProvider(),
    )


def test_hierarchy_is_disabled_by_default_and_does_not_backfill_edges(
    tmp_path: Path,
) -> None:
    provider = HierarchyEmbeddingProvider()
    store = _hierarchy_store(tmp_path, provider)

    result = store.lookup_rag_many("lung", ["test"], top_k=1)

    assert set(result) == {"hits", "errors"}
    assert provider.query_calls == ["lung"]
    with sqlite3.connect(store.sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM term_hierarchy").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM hierarchy_frameworks").fetchone()[0] == 0


def test_hierarchy_lookup_reuses_query_and_returns_best_relative_at_each_depth(
    tmp_path: Path,
) -> None:
    provider = HierarchyEmbeddingProvider()
    store = _hierarchy_store(tmp_path, provider)

    result = store.lookup_rag_many(
        "lung",
        ["test"],
        top_k=1,
        parent_depth=2,
        child_depth=1,
    )

    assert provider.query_calls == ["lung"]
    assert [hit["id"] for hit in result["hits"]] == ["TEST_3"]
    hierarchy = result["hierarchy_hits"]
    assert [
        (hit["id"], hit["rag_relation"], hit["rag_depth"], hit["rag_seed_id"])
        for hit in hierarchy
    ] == [
        ("TEST_2", "parent", 1, "TEST_3"),
        ("TEST_0", "parent", 2, "TEST_3"),
        ("TEST_4", "child", 1, "TEST_3"),
    ]
    assert hierarchy[0]["rag_score"] == pytest.approx(0.9, abs=1e-5)
    with sqlite3.connect(store.sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM term_hierarchy").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM hierarchy_frameworks").fetchone()[0] == 1


def test_hierarchy_index_is_lazily_backfilled_and_framework_removal_cascades(
    tmp_path: Path,
) -> None:
    store = _hierarchy_store(tmp_path)
    store.index_framework("test")

    store._ensure_hierarchy_index("test")

    with sqlite3.connect(store.sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM term_hierarchy").fetchone()[0] == 6
    assert store.remove_indexed_framework("test") is True
    with sqlite3.connect(store.sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM term_hierarchy").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM hierarchy_frameworks").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"parent_depth": -1}, "parent_depth"),
        ({"child_depth": True}, "child_depth"),
    ],
)
def test_lookup_rag_many_validates_hierarchy_depths(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    store = _hierarchy_store(tmp_path)

    with pytest.raises(ValueError, match=message):
        store.lookup_rag_many("lung", ["test"], **kwargs)


def test_harmonizer_hierarchy_is_opt_in_and_uses_only_two_anchor_seeds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _hierarchy_store(tmp_path)
    calls: list[dict[str, object]] = []
    direct_hits = [
        {
            "id": f"SEED:{index}",
            "ontology_id": "test",
            "title": f"seed {index}",
            "rag_score": 0.9 - (index * 0.05),
        }
        for index in range(3)
    ]
    hierarchy_hits = [
        {
            "id": "PARENT:1",
            "ontology_id": "test",
            "title": "parent one",
            "rag_score": 0.45,
            "rag_relation": "parent",
            "rag_depth": 1,
            "rag_seed_id": "SEED:0",
        },
        {
            "id": "PARENT:2",
            "ontology_id": "test",
            "title": "parent two",
            "rag_score": 0.41,
            "rag_relation": "parent",
            "rag_depth": 2,
            "rag_seed_id": "SEED:1",
        },
        {
            "id": "CHILD:1",
            "ontology_id": "test",
            "title": "weak child",
            "rag_score": 0.39,
            "rag_relation": "child",
            "rag_depth": 1,
            "rag_seed_id": "SEED:0",
        },
        {
            "id": "IGNORED:1",
            "ontology_id": "test",
            "title": "third seed parent",
            "rag_score": 0.8,
            "rag_relation": "parent",
            "rag_depth": 1,
            "rag_seed_id": "SEED:2",
        },
    ]

    def lookup_many(label, ontology_ids, top_k=10, **kwargs):
        calls.append(kwargs)
        result = {"hits": direct_hits, "errors": []}
        if kwargs:
            result["hierarchy_hits"] = hierarchy_hits
        return result

    monkeypatch.setattr(store, "lookup_rag_many", lookup_many)

    class CapturingHarmonizer(OntologyHarmonizer):
        def judge_lookup(self, *args, hits, **kwargs):
            self.judged_hits = hits
            return {
                "decision": (
                    "PARENT:1"
                    if any(hit["id"] == "PARENT:1" for hit in hits)
                    else "SEED:0"
                ),
                "confidence": "high",
                "reason": "The parent is appropriate.",
            }

    disabled = CapturingHarmonizer()
    disabled.lookup_rag_label(
        {"hz_label": "lung", "ontology_ids": ["test"]},
        publication_context=None,
        ontostore=store,
    )
    assert calls[0] == {}
    assert [hit["id"] for hit in disabled.judged_hits] == [
        "SEED:0",
        "SEED:1",
        "SEED:2",
    ]

    enabled = CapturingHarmonizer(rag_hierarchy=True)
    target = {"hz_label": "lung", "ontology_ids": ["test"]}
    selected = enabled.lookup_rag_label(
        target,
        publication_context=None,
        ontostore=store,
    )

    assert calls[1] == {"parent_depth": 2, "child_depth": 1}
    assert selected["id"] == "PARENT:1"
    assert [hit["id"] for hit in enabled.judged_hits] == [
        "SEED:0",
        "SEED:1",
        "SEED:2",
        "PARENT:1",
        "PARENT:2",
    ]
    assert target["ontology_rag"]["hierarchy"] == {
        "enabled": True,
        "parent_depth": 2,
        "child_depth": 1,
        "threshold_offset": 0.1,
        "hits": [enabled.judged_hits[3], enabled.judged_hits[4]],
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rag_parent_depth": -1}, "rag_parent_depth"),
        ({"rag_child_depth": 1.5}, "rag_child_depth"),
        ({"rag_hierarchy_threshold_offset": float("nan")}, "threshold_offset"),
        ({"rag_hierarchy_threshold_offset": 2.1}, "threshold_offset"),
    ],
)
def test_harmonizer_validates_hierarchy_configuration(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        OntologyHarmonizer(**kwargs)


def test_hierarchy_candidate_context_includes_relation_provenance() -> None:
    context = OntologyHarmonizer()._candidate_prompt_context(
        [
            {
                "id": "TEST:1",
                "ontology_id": "test",
                "title": "organ",
                "rag_score": 0.75,
                "rag_relation": "parent",
                "rag_depth": 1,
                "rag_seed_id": "TEST:2",
            }
        ]
    )

    assert context == [
        {
            "id": "TEST:1",
            "title": "organ",
            "ontology_id": "test",
            "rag_score": 0.75,
            "rag_relation": "parent",
            "rag_depth": 1,
            "rag_seed_id": "TEST:2",
        }
    ]
