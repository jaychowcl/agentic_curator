from pathlib import Path

import pytest

from agentic_curator.curators.ontology_harmonizer import (
    Owl2json,
    Owl2jsonParseError,
)


OWL_FIXTURE = """<?xml version="1.0"?>
<rdf:RDF xmlns="http://purl.obolibrary.org/obo/test.owl#"
     xml:base="http://purl.obolibrary.org/obo/test.owl"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:obo="http://purl.obolibrary.org/obo/"
     xmlns:owl="http://www.w3.org/2002/07/owl#"
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
     xmlns:terms="http://purl.org/dc/terms/"
     xmlns:oboInOwl="http://www.geneontology.org/formats/oboInOwl#">
    <owl:Ontology rdf:about="http://purl.obolibrary.org/obo/test.owl">
        <owl:versionIRI
            rdf:resource="http://purl.obolibrary.org/obo/test/releases/2026-01-01/test.owl"/>
        <dc:title>Test Ontology</dc:title>
        <dc:description>Ontology fixture for tests.</dc:description>
        <terms:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/>
        <owl:versionInfo>2026-01-01</owl:versionInfo>
    </owl:Ontology>

    <owl:Class rdf:about="http://purl.obolibrary.org/obo/TEST_0001">
        <rdfs:subClassOf rdf:resource="http://purl.obolibrary.org/obo/TEST_0000"/>
        <rdfs:subClassOf>
            <owl:Restriction>
                <owl:onProperty rdf:resource="http://purl.obolibrary.org/obo/RO_0000052"/>
                <owl:someValuesFrom
                    rdf:resource="http://purl.obolibrary.org/obo/TEST_9999"/>
            </owl:Restriction>
        </rdfs:subClassOf>
        <obo:IAO_0000115>Example definition.</obo:IAO_0000115>
        <oboInOwl:hasDbXref>PMID:1</oboInOwl:hasDbXref>
        <oboInOwl:hasExactSynonym>exact label</oboInOwl:hasExactSynonym>
        <oboInOwl:hasRelatedSynonym>related label</oboInOwl:hasRelatedSynonym>
        <oboInOwl:inSubset rdf:resource="http://purl.obolibrary.org/obo/test#subset"/>
        <oboInOwl:id>TEST:0001</oboInOwl:id>
        <rdfs:label>example term</rdfs:label>
        <obo:TEST_annot>custom literal</obo:TEST_annot>
    </owl:Class>

    <owl:Class rdf:about="http://purl.obolibrary.org/obo/TEST_0002">
        <rdfs:label>iri fallback term</rdfs:label>
    </owl:Class>

    <owl:Class rdf:about="http://purl.obolibrary.org/obo/TEST_0002_DUPLICATE">
        <rdfs:label>iri fallback term</rdfs:label>
    </owl:Class>

    <owl:Class rdf:about="http://purl.obolibrary.org/obo/TEST_0003">
        <obo:IAO_0100001
            rdf:resource="http://purl.obolibrary.org/obo/TEST_0004"/>
        <owl:deprecated
            rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</owl:deprecated>
        <rdfs:label>obsolete term</rdfs:label>
    </owl:Class>
</rdf:RDF>
"""


def write_fixture(tmp_path: Path, content: str = OWL_FIXTURE) -> Path:
    path = tmp_path / "test.owl"
    path.write_text(content, encoding="utf-8")
    return path


def test_owl2json_extracts_ontology_metadata_and_terms(tmp_path: Path) -> None:
    result = Owl2json(write_fixture(tmp_path)).parse()

    assert result["ontology"] == {
        "id": None,
        "iri": "http://purl.obolibrary.org/obo/test.owl",
        "version_iri": "http://purl.obolibrary.org/obo/test/releases/2026-01-01/test.owl",
        "title": "Test Ontology",
        "description": "Ontology fixture for tests.",
        "version": "2026-01-01",
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }
    assert set(result["terms"]) == {"accession", "id", "iri", "label"}

    assert result["terms"]["accession"]["test:0001"] == {
        "iri": "http://purl.obolibrary.org/obo/TEST_0001",
        "accession": "TEST:0001",
        "title": "example term",
        "description": "Example definition.",
        "parents": ["TEST:0000"],
        "parent_iris": ["http://purl.obolibrary.org/obo/TEST_0000"],
        "synonyms": {
            "exact": ["exact label"],
            "related": ["related label"],
            "broad": [],
            "narrow": [],
        },
        "xrefs": ["PMID:1"],
        "subsets": ["http://purl.obolibrary.org/obo/test#subset"],
        "deprecated": False,
        "replaced_by": None,
        "properties": {
            "http://purl.obolibrary.org/obo/TEST_annot": ["custom literal"],
        },
    }
    assert (
        result["terms"]["iri"]["http://purl.obolibrary.org/obo/test_0001"]
        == result["terms"]["accession"]["test:0001"]
    )
    assert result["terms"]["label"]["example_term"] == [
        result["terms"]["accession"]["test:0001"]
    ]


def test_owl2json_indexes_use_harmonized_keys_and_preserve_metadata(
    tmp_path: Path,
) -> None:
    content = OWL_FIXTURE.replace("example term", " Example   Term, ")

    result = Owl2json(write_fixture(tmp_path, content)).parse()

    assert "example_term" in result["terms"]["label"]
    term = result["terms"]["label"]["example_term"][0]
    assert term["title"] == " Example   Term, "
    assert term["accession"] == "TEST:0001"
    assert result["terms"]["accession"]["test:0001"] == term
    assert result["terms"]["iri"]["http://purl.obolibrary.org/obo/test_0001"] == term


def test_owl2json_parse_accepts_ontology_id(tmp_path: Path) -> None:
    result = Owl2json(write_fixture(tmp_path)).parse(ontology_id="test")

    assert result["ontology"]["id"] == "test"


def test_owl2json_derives_accession_from_obo_iri(tmp_path: Path) -> None:
    result = Owl2json(write_fixture(tmp_path)).parse()

    assert result["terms"]["accession"]["test:0002"]["accession"] == "TEST:0002"


def test_owl2json_label_index_preserves_duplicate_labels(tmp_path: Path) -> None:
    result = Owl2json(write_fixture(tmp_path)).parse()

    matching_terms = result["terms"]["label"]["iri_fallback_term"]
    assert [term["accession"] for term in matching_terms] == [
        "TEST:0002",
        "TEST:0002_DUPLICATE",
    ]


def test_owl2json_extracts_deprecated_and_replaced_by(tmp_path: Path) -> None:
    result = Owl2json(write_fixture(tmp_path)).parse()

    obsolete = result["terms"]["accession"]["test:0003"]
    assert obsolete["deprecated"] is True
    assert obsolete["replaced_by"] == "TEST:0004"


def test_owl2json_rejects_html_saved_as_owl(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, "<!DOCTYPE html><html><body>not owl</body></html>")

    with pytest.raises(Owl2jsonParseError, match="does not look like RDF/XML"):
        Owl2json(path).parse()


def test_owl2json_write_json_writes_deterministic_json(tmp_path: Path) -> None:
    parser = Owl2json(write_fixture(tmp_path))
    output_path = tmp_path / "test.json"

    result_path = parser.write_json(output_path, ontology_id="test")

    assert result_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith('{\n  "ontology":')
    assert '"id": "test"' in output_path.read_text(encoding="utf-8")
    assert '"accession": "TEST:0001"' in output_path.read_text(encoding="utf-8")
