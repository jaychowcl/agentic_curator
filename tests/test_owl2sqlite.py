# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from pathlib import Path
import sqlite3

from agentic_curator.curators.ontology_harmonizer import OntoStore


OWL = """<?xml version="1.0"?>
<rdf:RDF
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:obo="http://purl.obolibrary.org/obo/"
 xmlns:oboInOwl="http://www.geneontology.org/formats/oboInOwl#">
 <owl:Ontology rdf:about="https://example.org/test"/>
 <owl:Class rdf:about="https://example.org/TEST_1">
   <rdfs:label>Lung</rdfs:label>
   <obo:IAO_0000115>Respiratory organ.</obo:IAO_0000115>
   <oboInOwl:id>TEST:1</oboInOwl:id>
   <oboInOwl:hasExactSynonym>pulmonary organ</oboInOwl:hasExactSynonym>
   <oboInOwl:hasDbXref>UMLS:C0024109</oboInOwl:hasDbXref>
   <rdfs:subClassOf rdf:resource="https://example.org/TEST_0"/>
   <oboInOwl:inSubset rdf:resource="https://example.org/subset"/>
   <obo:custom>custom value</obo:custom>
 </owl:Class>
 <rdf:Description rdf:about="https://example.org/TEST_2">
   <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#Class"/>
   <rdfs:label>Fibrotic lung</rdfs:label>
   <owl:deprecated>true</owl:deprecated>
   <obo:IAO_0100001 rdf:resource="https://example.org/TEST_1"/>
 </rdf:Description>
</rdf:RDF>
"""


def store_with_owl(tmp_path: Path) -> OntoStore:
    owl_path = tmp_path / "test.owl"
    owl_path.write_text(OWL, encoding="utf-8")
    return OntoStore(
        ontology_frameworks={"test": {"path": owl_path}},
        storage_dir=tmp_path,
    )


def test_direct_owl_index_matches_expected_term_semantics(tmp_path: Path) -> None:
    store = store_with_owl(tmp_path)

    store.index_owl_framework("test")

    lung = store.lookup("pulmonary organ", "test")[0]
    assert lung["accession"] == "TEST:1"
    assert lung["title"] == "Lung"
    assert lung["description"] == "Respiratory organ."
    assert lung["parents"] == ["TEST:0"]
    assert lung["xrefs"] == ["UMLS:C0024109"]
    assert lung["subsets"] == ["https://example.org/subset"]
    assert lung["properties"] == {
        "http://purl.obolibrary.org/obo/custom": ["custom value"]
    }
    deprecated = store.lookup("Fibrotic lung", "test")[0]
    assert deprecated["deprecated"] is True
    assert deprecated["replaced_by"] == "TEST:1"


def test_direct_index_creates_no_json_and_cleans_staging(tmp_path: Path) -> None:
    store = store_with_owl(tmp_path)

    store.index_owl_framework("test")

    assert not Path(store.ontology_frameworks["test"]["json_path"]).exists()
    assert not list((tmp_path / "sqlite" / "staging").glob("*"))
    with sqlite3.connect(store.sqlite_path) as connection:
        source_kind = connection.execute(
            "SELECT source_kind FROM frameworks WHERE ontology_id = 'test'"
        ).fetchone()[0]
    assert source_kind == "owl"


def test_cache_all_selectively_forces_one_framework(tmp_path: Path, monkeypatch) -> None:
    store = OntoStore(ontology_frameworks={}, storage_dir=tmp_path)
    store.ontology_frameworks = {
        name: {
            "owl_path": tmp_path / f"{name}.owl",
            "json_path": tmp_path / f"{name}.json",
            "url": f"https://example/{name}.owl",
        }
        for name in ("alpha", "beta")
    }
    calls = []

    def index_owl(name, force=False, batch_size=1000):
        calls.append((name, force))
        path = tmp_path / f"{name}.owl"
        path.write_text("owl", encoding="utf-8")
        return store.sqlite_path

    monkeypatch.setattr(store, "index_owl_framework", index_owl)

    result = store.cache_all(force_frameworks=["beta"])

    assert calls == [("alpha", False), ("beta", True)]
    assert result["successful"] == ["alpha", "beta"]


def test_failed_stream_refresh_preserves_previous_index(tmp_path: Path, monkeypatch) -> None:
    store = store_with_owl(tmp_path)
    store.index_owl_framework("test")

    def fail_after_one():
        yield {
            "iri": "https://example.org/BROKEN",
            "accession": "BROKEN:1",
            "title": "Broken",
        }
        raise RuntimeError("parse failed")

    monkeypatch.setattr(
        "agentic_curator.curators.ontology_harmonizer.ontology_store."
        "Owl2SqliteTerms.iter_terms",
        lambda self: fail_after_one(),
    )

    try:
        store.index_owl_framework("test", force=True)
    except RuntimeError as error:
        assert str(error) == "parse failed"
    else:
        raise AssertionError("refresh should fail")

    assert store.lookup("Lung", "test")[0]["accession"] == "TEST:1"
    assert store.lookup("Broken", "test") == []
