import inspect
from pathlib import Path

import pytest

from agentic_curator import OntologyHarmonizer as RootOntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import ontology_store
from agentic_curator.curators import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import (
    HarmonizationTargetExtractor,
    OntoStore,
    OntologyHarmonizer as SubpackageOntologyHarmonizer,
    Owl2jsonParseError,
)


DEFAULT_ONTOLOGY_FRAMEWORKS = {
    "efo": {
        "title": "Experimental Factor Ontology",
        "url": "http://www.ebi.ac.uk/efo/efo.owl",
        "version": None,
        "description": "The Experimental Factor Ontology (EFO) provides a systematic description of many experimental variables available in EBI databases, and for projects such as the NHGRI-EBI GWAS catalog. It combines parts of several biological ontologies, such as UBERON anatomy, ChEBI chemical compounds, Cell Ontology and the Monarch Disease Ontology (MONDO). The scope of EFO is to support the annotation, analysis and visualization of data handled by many groups at the EBI and as the core ontology for Open Targets.",
    },
    "mondo": {
        "title": "Mondo Disease Ontology",
        "url": "http://purl.obolibrary.org/obo/mondo/releases/2026-06-02/mondo-international.owl",
        "version": "2026-06-02",
        "description": "A semi-automatically constructed ontology that merges in multiple disease resources to yield a coherent merged ontology.",
    },
    "uberon": {
        "title": "Uber-anatomy ontology",
        "url": "http://purl.obolibrary.org/obo/uberon.owl",
        "version": None,
        "description": "Uberon is an integrated cross-species anatomy ontology representing a variety of entities classified according to traditional anatomical criteria such as structure, function and developmental lineage. The ontology includes comprehensive relationships to taxon-specific anatomical ontologies, allowing integration of functional, phenotype and expression data.",
    },
    "hp": {
        "title": "Human Phenotype Ontology",
        "url": "http://purl.obolibrary.org/obo/hp/releases/2026-06-23/hp-international.owl",
        "version": "2026-06-23",
        "description": "The Human Phenotype Ontology (HPO) provides a standardized vocabulary of phenotypic abnormalities and clinical features encountered in human disease.",
    },
    "cl": {
        "title": "Cell Ontology",
        "url": "http://purl.obolibrary.org/obo/cl/releases/2026-06-08/cl.owl",
        "version": "2026-06-08",
        "description": "An ontology of cell types.",
    },
    "chebi": {
        "title": "Chemical Entities of Biological Interest",
        "url": "http://purl.obolibrary.org/obo/chebi/252/chebi.owl",
        "version": "252",
        "description": "A structured classification of molecular entities of biological interest focusing on 'small' chemical compounds.",
    },
    "pato": {
        "title": "PATO - the Phenotype And Trait Ontology",
        "url": "http://purl.obolibrary.org/obo/pato/releases/2025-05-14/pato.owl",
        "version": "2025-05-14",
        "description": "An ontology of phenotypic qualities (properties, attributes or characteristics).",
    },
    "obi": {
        "title": "Ontology for Biomedical Investigations",
        "url": "http://purl.obolibrary.org/obo/obi/2026-05-08/obi.owl",
        "version": "2026-05-08",
        "description": "An ontology for representing biomedical investigations, including study designs, the collection and preparation of the targets of investigation, assays, instrumentation and reagents used, as well as the data generated and the types of analysis performed on the data to reach conclusions, and their documentation.",
    },
    "snomed": {
        "title": "SNOMED CT (International Edition)",
        "url": "http://snomed.info/sct/900000000000207008/version/20251017",
        "version": "20251017",
        "description": "SNOMED CT or SNOMED Clinical Terms is a systematically organized computer processable collection of medical terms providing codes, terms, synonyms and definitions used in clinical documentation and reporting.",
    },
    "ncit": {
        "title": "NCI Thesaurus OBO Edition",
        "url": "http://purl.obolibrary.org/obo/ncit/releases/2026-03-19/ncit.owl",
        "version": "26.02d",
        "description": "NCI Thesaurus (NCIt)is a reference terminology that includes broad coverage of the cancer domain, including cancer related diseases, findings and abnormalities. The NCIt OBO Edition aims to increase integration of the NCIt with OBO Library ontologies. NCIt OBO Edition releases should be considered experimental.",
    },
    "ncbitaxon": {
        "title": "NCBI organismal classification",
        "url": "http://purl.obolibrary.org/obo/ncbitaxon/2026-05-13/ncbitaxon.owl",
        "version": "2026-05-13",
        "description": "An ontology representation of the NCBI organismal taxonomy",
    },
}


class FakeResponse:
    def __init__(self, content: bytes = b"ontology", error: Exception | None = None):
        self.content = content
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error


def ontology_bytes(*, title: str = "Cell Ontology", label: str = "cell") -> bytes:
    return f"""<?xml version="1.0"?>
<rdf:RDF xmlns="http://purl.obolibrary.org/obo/cl.owl#"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:obo="http://purl.obolibrary.org/obo/"
     xmlns:owl="http://www.w3.org/2002/07/owl#"
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
     xmlns:oboInOwl="http://www.geneontology.org/formats/oboInOwl#">
    <owl:Ontology rdf:about="http://purl.obolibrary.org/obo/cl.owl">
        <dc:title>{title}</dc:title>
    </owl:Ontology>
    <owl:Class rdf:about="http://purl.obolibrary.org/obo/CL_0000000">
        <oboInOwl:id>CL:0000000</oboInOwl:id>
        <rdfs:label>{label}</rdfs:label>
    </owl:Class>
</rdf:RDF>
""".encode("utf-8")


def test_ontology_harmonizer_can_be_imported_from_subpackage() -> None:
    assert SubpackageOntologyHarmonizer is OntologyHarmonizer


def test_ontology_harmonizer_is_exported_from_package_root() -> None:
    assert RootOntologyHarmonizer is OntologyHarmonizer


def test_ontostore_can_be_imported_from_subpackage() -> None:
    assert OntoStore.__name__ == "OntoStore"


def test_harmonization_target_extractor_can_be_imported_from_subpackage() -> None:
    assert HarmonizationTargetExtractor.__name__ == "HarmonizationTargetExtractor"


def test_ontostore_initializes_with_default_frameworks(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    assert store.ontology_frameworks == DEFAULT_ONTOLOGY_FRAMEWORKS
    assert store.storage_dir == tmp_path
    assert store.downloaded_paths == {}


def test_default_frameworks_include_titles() -> None:
    for framework in OntoStore.DEFAULT_ONTOLOGY_FRAMEWORKS.values():
        assert isinstance(framework["title"], str)
        assert framework["title"]


def test_default_frameworks_include_descriptions() -> None:
    for framework in OntoStore.DEFAULT_ONTOLOGY_FRAMEWORKS.values():
        assert isinstance(framework["description"], str)
        assert framework["description"]


def test_ontostore_constructor_frameworks_extend_defaults(tmp_path: Path) -> None:
    ontology_frameworks = {"CL": {"url": "https://example.org/cl.owl"}}

    store = OntoStore(
        ontology_frameworks=ontology_frameworks,
        storage_dir=tmp_path,
    )

    assert store.ontology_frameworks == {
        **DEFAULT_ONTOLOGY_FRAMEWORKS,
        "CL": {"url": "https://example.org/cl.owl"},
    }


def test_constructor_framework_can_override_default(tmp_path: Path) -> None:
    store = OntoStore(
        ontology_frameworks={
            "efo": {
                "url": "https://example.org/custom-efo.owl",
                "version": "custom",
            }
        },
        storage_dir=tmp_path,
    )

    assert store.ontology_frameworks["efo"] == {
        "url": "https://example.org/custom-efo.owl",
        "version": "custom",
    }


def test_add_url_adds_single_framework_url(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    store.add_url("CL", "https://example.org/cl.owl", version="v1")

    assert store.ontology_frameworks["CL"] == {
        "url": "https://example.org/cl.owl",
        "version": "v1",
    }


def test_add_urls_merges_frameworks(tmp_path: Path) -> None:
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    store.add_urls(
        {
            "UBERON": {
                "url": "https://example.org/uberon.owl",
                "version": "v2",
            }
        }
    )

    assert store.ontology_frameworks == {
        **DEFAULT_ONTOLOGY_FRAMEWORKS,
        "CL": {"url": "https://example.org/cl.owl"},
        "UBERON": {
            "url": "https://example.org/uberon.owl",
            "version": "v2",
        },
    }


def test_download_uses_default_efo_url(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_get(url, *, timeout):
        calls.append({"url": url, "timeout": timeout})
        return FakeResponse(content=b"efo ontology")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(storage_dir=tmp_path)

    result = store.download("efo")

    assert result == tmp_path / "efo.owl"
    assert result.read_bytes() == b"efo ontology"
    assert calls == [{"url": "http://www.ebi.ac.uk/efo/efo.owl", "timeout": 30}]


def test_download_uses_default_mondo_url(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_get(url, *, timeout):
        calls.append({"url": url, "timeout": timeout})
        return FakeResponse(content=b"mondo ontology")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(storage_dir=tmp_path)

    result = store.download("mondo")

    assert result == tmp_path / "mondo-international.owl"
    assert result.read_bytes() == b"mondo ontology"
    assert calls == [
        {
            "url": "http://purl.obolibrary.org/obo/mondo/releases/2026-06-02/mondo-international.owl",
            "timeout": 30,
        }
    ]


def test_download_uses_framework_name_to_route_to_url(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_get(url, *, timeout):
        calls.append({"url": url, "timeout": timeout})
        return FakeResponse(content=b"cl ontology")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.download("CL")

    assert result == tmp_path / "cl.owl"
    assert result.read_bytes() == b"cl ontology"
    assert store.downloaded_paths == {"CL": tmp_path / "cl.owl"}
    assert calls == [{"url": "https://example.org/cl.owl", "timeout": 30}]


def test_download_only_downloads_named_framework(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_get(url, *, timeout):
        calls.append(url)
        return FakeResponse(content=b"uberon ontology")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={
            "CL": {"url": "https://example.org/cl.owl"},
            "UBERON": {"url": "https://example.org/uberon.owl"},
        },
        storage_dir=tmp_path,
    )

    result = store.download("UBERON")

    assert result == tmp_path / "uberon.owl"
    assert result.read_bytes() == b"uberon ontology"
    assert calls == ["https://example.org/uberon.owl"]


def test_download_skips_existing_file(monkeypatch, tmp_path: Path) -> None:
    existing = tmp_path / "cl.owl"
    existing.write_bytes(b"existing ontology")

    def fake_get(url, *, timeout):
        raise AssertionError("requests.get should not be called")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.download("CL")

    assert result == existing
    assert existing.read_bytes() == b"existing ontology"
    assert store.downloaded_paths == {"CL": existing}


def test_download_raises_key_error_for_unknown_framework(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    with pytest.raises(KeyError, match="CL"):
        store.download("CL")


def test_download_raises_value_error_for_missing_url(tmp_path: Path) -> None:
    store = OntoStore(
        ontology_frameworks={"CL": {}},
        storage_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="CL"):
        store.download("CL")


def test_download_raises_value_error_for_url_without_filename(tmp_path: Path) -> None:
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/"}},
        storage_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="filename"):
        store.download("CL")


def test_download_propagates_http_errors(monkeypatch, tmp_path: Path) -> None:
    error = RuntimeError("bad response")

    def fake_get(url, *, timeout):
        return FakeResponse(error=error)

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    with pytest.raises(RuntimeError, match="bad response"):
        store.download("CL")
    assert store.downloaded_paths == {}


def test_get_downloads_missing_ontology_and_returns_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = []

    def fake_get(url, *, timeout):
        calls.append({"url": url, "timeout": timeout})
        return FakeResponse(content=ontology_bytes())

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.get("CL")

    assert result == tmp_path / "jsons" / "cl.json"
    assert (tmp_path / "cl.owl").read_bytes() == ontology_bytes()
    assert '"CL:0000000"' in result.read_text(encoding="utf-8")
    assert store.downloaded_paths == {"CL": tmp_path / "cl.owl"}
    assert calls == [{"url": "https://example.org/cl.owl", "timeout": 30}]


def test_get_uses_existing_downloaded_file(monkeypatch, tmp_path: Path) -> None:
    existing = tmp_path / "cl.owl"
    existing.write_bytes(ontology_bytes())

    def fake_get(url, *, timeout):
        raise AssertionError("requests.get should not be called")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.get("CL")

    assert result == tmp_path / "jsons" / "cl.json"
    assert existing.read_bytes() == ontology_bytes()
    assert '"CL:0000000"' in result.read_text(encoding="utf-8")
    assert store.downloaded_paths == {"CL": existing}


def test_get_returns_existing_json_without_calling_download(tmp_path: Path) -> None:
    existing = tmp_path / "cl.owl"
    existing.write_bytes(b"invalid existing ontology")
    existing_json = tmp_path / "jsons" / "cl.json"
    existing_json.parent.mkdir(parents=True)
    existing_json.write_text('{"cached": true}\n', encoding="utf-8")

    class DownloadFailingStore(OntoStore):
        def download(self, name: str) -> Path:
            raise AssertionError("download should not be called")

    store = DownloadFailingStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.get("CL")

    assert result == existing_json
    assert result.read_text(encoding="utf-8") == '{"cached": true}\n'
    assert store.downloaded_paths == {}


def test_get_force_redownloads_and_reparses_existing_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    existing_owl = tmp_path / "cl.owl"
    existing_owl.write_bytes(ontology_bytes(title="Old Cell Ontology", label="old cell"))
    existing_json = tmp_path / "jsons" / "cl.json"
    existing_json.parent.mkdir(parents=True)
    existing_json.write_text('{"cached": true}\n', encoding="utf-8")
    calls = []

    def fake_get(url, *, timeout):
        calls.append({"url": url, "timeout": timeout})
        return FakeResponse(content=ontology_bytes(title="New Cell Ontology"))

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.get("CL", force=True)

    assert result == existing_json
    assert existing_owl.read_bytes() == ontology_bytes(title="New Cell Ontology")
    assert "New Cell Ontology" in existing_json.read_text(encoding="utf-8")
    assert store.downloaded_paths == {"CL": existing_owl}
    assert calls == [{"url": "https://example.org/cl.owl", "timeout": 30}]


def test_get_propagates_download_errors(monkeypatch, tmp_path: Path) -> None:
    error = RuntimeError("bad response")

    def fake_get(url, *, timeout):
        return FakeResponse(error=error)

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    with pytest.raises(RuntimeError, match="bad response"):
        store.get("CL")
    assert store.downloaded_paths == {}


def test_get_propagates_parse_errors_for_invalid_download(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_get(url, *, timeout):
        return FakeResponse(content=b"not rdf xml")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    with pytest.raises(Owl2jsonParseError):
        store.get("CL")
    assert (tmp_path / "cl.owl").read_bytes() == b"not rdf xml"
    assert not (tmp_path / "jsons" / "cl.json").exists()
    assert store.downloaded_paths == {"CL": tmp_path / "cl.owl"}


def test_harmonize_returns_metadata_only() -> None:
    metadata = {
        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
        "characteristics": [
            {"tag": "disease state", "value": "Normal Oral mucosa"},
            {"tag": "tissue", "value": "lung"},
        ],
    }
    ontology_frameworks = OntoStore()

    result = OntologyHarmonizer().harmonize(
        publication_text="Full publication text",
        metadata=metadata,
        ontology_frameworks=ontology_frameworks,
    )

    assert result == {"metadata": metadata}


def test_harmonize_signature_excludes_title() -> None:
    assert "title" not in inspect.signature(OntologyHarmonizer.harmonize).parameters


def test_harmonize_defaults_to_none_metadata() -> None:
    result = OntologyHarmonizer().harmonize()

    assert result == {"metadata": None}


def test_harmonizer_creates_default_ontostore() -> None:
    assert isinstance(OntologyHarmonizer().ontology_frameworks, OntoStore)


def test_harmonizer_accepts_ontostore_in_constructor() -> None:
    store = OntoStore()

    harmonizer = OntologyHarmonizer(ontology_frameworks=store)

    assert harmonizer.ontology_frameworks is store


def test_harmonizer_accepts_dict_ontology_frameworks_in_constructor() -> None:
    ontology_frameworks = {"anatomy": "UBERON"}

    harmonizer = OntologyHarmonizer(ontology_frameworks=ontology_frameworks)

    assert harmonizer.ontology_frameworks is ontology_frameworks


def test_harmonize_accepts_ontostore_override() -> None:
    metadata = {"organism": [{"taxid": "9606", "value": "Homo sapiens"}]}
    store = OntoStore()

    result = OntologyHarmonizer().harmonize(
        metadata=metadata,
        ontology_frameworks=store,
    )

    assert result == {"metadata": metadata}


def test_harmonize_rejects_dict_ontology_framework_override() -> None:
    with pytest.raises(TypeError, match="OntoStore"):
        OntologyHarmonizer().harmonize(
            metadata={},
            ontology_frameworks={"anatomy": "UBERON"},
        )


def test_extract_harmonization_targets_from_flat_metadata() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"organism": "human", "age": 42, "diseased": True, "missing": None}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "organism",
            "label": "human",
            "field_path": "/organism",
            "label_path": "/organism",
            "parent_path": "",
            "key": "organism",
            "value": "human",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "field": "age",
            "label": "42",
            "field_path": "/age",
            "label_path": "/age",
            "parent_path": "",
            "key": "age",
            "value": 42,
        },
        {
            "id": "target-2",
            "source": "metadata",
            "field": "diseased",
            "label": "True",
            "field_path": "/diseased",
            "label_path": "/diseased",
            "parent_path": "",
            "key": "diseased",
            "value": True,
        },
    ]


def test_target_extractor_extracts_flat_metadata() -> None:
    assert HarmonizationTargetExtractor().extract(
        {"organism": "human", "missing": None}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "organism",
            "label": "human",
            "field_path": "/organism",
            "label_path": "/organism",
            "parent_path": "",
            "key": "organism",
            "value": "human",
        }
    ]


def test_extract_harmonization_targets_from_nested_metadata() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"sample": {"tissue": "lung"}}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "lung",
            "field_path": "/sample/tissue",
            "label_path": "/sample/tissue",
            "parent_path": "/sample",
            "key": "tissue",
            "value": "lung",
        }
    ]


def test_extract_harmonization_targets_from_list_of_dicts() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"samples": [{"tissue": "lung"}, {"tissue": "heart"}]}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "lung",
            "field_path": "/samples/0/tissue",
            "label_path": "/samples/0/tissue",
            "parent_path": "/samples/0",
            "key": "tissue",
            "value": "lung",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "field": "tissue",
            "label": "heart",
            "field_path": "/samples/1/tissue",
            "label_path": "/samples/1/tissue",
            "parent_path": "/samples/1",
            "key": "tissue",
            "value": "heart",
        },
    ]


def test_extract_harmonization_targets_escapes_json_pointer_segments() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"sample/type": {"label~name": "lung"}}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "label~name",
            "label": "lung",
            "field_path": "/sample~1type/label~0name",
            "label_path": "/sample~1type/label~0name",
            "parent_path": "/sample~1type",
            "key": "label~name",
            "value": "lung",
        }
    ]


def test_extract_harmonization_targets_skips_uneditable_metadata() -> None:
    harmonizer = OntologyHarmonizer()

    assert harmonizer._extract_harmonization_targets(None) == []
    assert harmonizer._extract_harmonization_targets("raw metadata") == []
    assert harmonizer._extract_harmonization_targets(["lung", "heart"]) == []
    assert harmonizer._extract_harmonization_targets({"samples": []}) == []


def test_harmonize_accepts_target_paths_without_returning_targets() -> None:
    metadata = {
        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
        "characteristics": [{"tag": "tissue", "value": "lung"}],
    }

    result = OntologyHarmonizer().harmonize(
        metadata=metadata,
        target_paths=[],
    )

    assert result == {"metadata": metadata}


def test_extract_harmonization_targets_starts_from_selected_subtree() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {
            "publication": {"year": 2026},
            "sample": {"tissue": "lung"},
        },
        start_paths=["/sample"],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "lung",
            "field_path": "/sample/tissue",
            "label_path": "/sample/tissue",
            "parent_path": "/sample",
            "key": "tissue",
            "value": "lung",
        }
    ]


def test_extract_harmonization_targets_starts_from_list_item() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"samples": [{"tissue": "lung"}, {"tissue": "heart"}]},
        start_paths=["/samples/1"],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "heart",
            "field_path": "/samples/1/tissue",
            "label_path": "/samples/1/tissue",
            "parent_path": "/samples/1",
            "key": "tissue",
            "value": "heart",
        }
    ]


def test_extract_harmonization_targets_uses_multiple_start_paths_in_order() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {
            "publication": {"organism": "human"},
            "sample": {"tissue": "lung"},
        },
        start_paths=["/sample", "/publication"],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "lung",
            "field_path": "/sample/tissue",
            "label_path": "/sample/tissue",
            "parent_path": "/sample",
            "key": "tissue",
            "value": "lung",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "field": "organism",
            "label": "human",
            "field_path": "/publication/organism",
            "label_path": "/publication/organism",
            "parent_path": "/publication",
            "key": "organism",
            "value": "human",
        },
    ]


def test_extract_harmonization_targets_empty_start_path_uses_metadata_root() -> None:
    metadata = {"sample": {"tissue": "lung"}}
    harmonizer = OntologyHarmonizer()

    assert harmonizer._extract_harmonization_targets(
        metadata,
        start_paths=[""],
    ) == harmonizer._extract_harmonization_targets(metadata)


def test_extract_harmonization_targets_resolves_escaped_start_path() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"sample/type": {"label~name": "lung"}},
        start_paths=["/sample~1type"],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "label~name",
            "label": "lung",
            "field_path": "/sample~1type/label~0name",
            "label_path": "/sample~1type/label~0name",
            "parent_path": "/sample~1type",
            "key": "label~name",
            "value": "lung",
        }
    ]


def test_extract_harmonization_targets_skips_unresolvable_start_paths() -> None:
    harmonizer = OntologyHarmonizer()
    metadata = {
        "sample": {"tissue": "lung"},
        "samples": [{"tissue": "heart"}],
    }

    assert harmonizer._extract_harmonization_targets(
        metadata,
        start_paths=[
            "/missing",
            "/samples/not-an-index",
            "/samples/3",
            "/sample/tissue",
        ],
    ) == []
    assert harmonizer._extract_harmonization_targets(
        None,
        start_paths=[""],
    ) == []
    assert harmonizer._extract_harmonization_targets(
        "raw metadata",
        start_paths=[""],
    ) == []


def test_extract_harmonization_targets_uses_tag_value_path_specs() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {
            "characteristics": [
                {"tag": "disease state", "value": "Normal Oral mucosa"},
                {"tag": "tissue", "value": "Oral buccal mucosa"},
            ]
        },
        start_paths=[{"path": "/characteristics", "mode": "tag_value"}],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "disease state",
            "label": "Normal Oral mucosa",
            "field_path": "/characteristics/0/tag",
            "label_path": "/characteristics/0/value",
            "parent_path": "/characteristics/0",
            "key": "disease state",
            "value": "Normal Oral mucosa",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "field": "tissue",
            "label": "Oral buccal mucosa",
            "field_path": "/characteristics/1/tag",
            "label_path": "/characteristics/1/value",
            "parent_path": "/characteristics/1",
            "key": "tissue",
            "value": "Oral buccal mucosa",
        },
    ]


def test_target_extractor_uses_tag_value_path_specs() -> None:
    assert HarmonizationTargetExtractor().extract(
        {"characteristics": [{"tag": "tissue", "value": "lung"}]},
        start_paths=[{"path": "/characteristics", "mode": "tag_value"}],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "lung",
            "field_path": "/characteristics/0/tag",
            "label_path": "/characteristics/0/value",
            "parent_path": "/characteristics/0",
            "key": "tissue",
            "value": "lung",
        }
    ]


def test_extract_harmonization_targets_uses_container_value_path_specs() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"organism": [{"taxid": "9606", "value": "Homo sapiens"}]},
        start_paths=[{"path": "/organism", "mode": "container_value"}],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "organism",
            "label": "Homo sapiens",
            "field_path": "/organism",
            "label_path": "/organism/0/value",
            "parent_path": "/organism/0",
            "key": "organism",
            "value": "Homo sapiens",
        }
    ]


def test_extract_harmonization_targets_mixes_path_spec_modes_in_order() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {
            "source": "Oral buccal mucosa",
            "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
            "characteristics": [
                {"tag": "tissue", "value": "Oral buccal mucosa"},
            ],
        },
        start_paths=[
            {"path": "/characteristics", "mode": "tag_value"},
            {"path": "/organism", "mode": "container_value"},
            "/source",
        ],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "Oral buccal mucosa",
            "field_path": "/characteristics/0/tag",
            "label_path": "/characteristics/0/value",
            "parent_path": "/characteristics/0",
            "key": "tissue",
            "value": "Oral buccal mucosa",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "field": "organism",
            "label": "Homo sapiens",
            "field_path": "/organism",
            "label_path": "/organism/0/value",
            "parent_path": "/organism/0",
            "key": "organism",
            "value": "Homo sapiens",
        },
    ]


def test_extract_harmonization_targets_defaults_path_specs_to_scalar_mode() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"sample": {"tissue": "lung"}},
        start_paths=[{"path": "/sample"}],
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "field": "tissue",
            "label": "lung",
            "field_path": "/sample/tissue",
            "label_path": "/sample/tissue",
            "parent_path": "/sample",
            "key": "tissue",
            "value": "lung",
        }
    ]


def test_extract_harmonization_targets_skips_invalid_path_specs() -> None:
    metadata = {
        "characteristics": [
            {"tag": "tissue"},
            {"value": "Oral buccal mucosa"},
            {"tag": {"nested": "field"}, "value": "Oral buccal mucosa"},
            {"tag": "tissue", "value": ["Oral buccal mucosa"]},
        ],
        "organism": [
            {"taxid": "9606"},
            {"value": {"nested": "Homo sapiens"}},
        ],
        "sample": {"tissue": "lung"},
    }

    assert OntologyHarmonizer()._extract_harmonization_targets(
        metadata,
        start_paths=[
            {"path": "/characteristics", "mode": "tag_value"},
            {"path": "/organism", "mode": "container_value"},
            {"path": "/sample", "mode": "missing_mode"},
            {"path": "/sample/tissue", "mode": "tag_value"},
            {"mode": "tag_value"},
            "/sample/tissue",
            123,
        ],
    ) == []
