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
import re
from pathlib import Path
from importlib.resources import files

import pytest

from agentic_curator import OntologyHarmonizer as RootOntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import ontology_store
from agentic_curator.curators import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import (
    GeminiGroundedSearchClient,
    HarmonizationTargetExtractor,
    OntoStore,
    OntologyHarmonizer as SubpackageOntologyHarmonizer,
    Owl2jsonParseError,
    RagStrategyHandler,
    WebsearchStrategyHandler,
)
from agentic_curator.curators.ontology_harmonizer.harmonization_target_extractor import (
    HarmonizationTargetExtractor as DirectHarmonizationTargetExtractor,
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

ASSIGN_ONTO_FRAMEWORK_PROMPT = files("agentic_curator").joinpath(
    "curators/ontology_harmonizer/prompts/assign_onto_framework.md"
).read_text(encoding="utf-8").strip()
ASSIGN_FIELD_PROMPT = files("agentic_curator").joinpath(
    "curators/ontology_harmonizer/prompts/assign_field.md"
).read_text(encoding="utf-8").strip()
JUDGE_LOOKUP_PROMPT = files("agentic_curator").joinpath(
    "curators/ontology_harmonizer/prompts/judge_lookup.md"
).read_text(encoding="utf-8").strip()


class FakeResponse:
    def __init__(self, content: bytes = b"ontology", error: Exception | None = None):
        self.content = content
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error


class FakeLLM:
    def __init__(self, response=None, responses=None) -> None:
        self.calls = []
        self.response_provided = response is not None
        self.response = (
            {
                "decision": "unsure",
                "confidence": "low",
                "reason": "No clear framework match.",
            }
            if response is None
            else response
        )
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

        if self.response_provided:
            return self.response

        if prompt.startswith(ASSIGN_FIELD_PROMPT):
            field_match = re.search(r'"hz_field": "([^"]+)"', prompt)
            decision = field_match.group(1) if field_match else "field"
            return {
                "decision": decision,
                "confidence": "low",
                "reason": "No clear field match.",
                "new_field": True,
            }

        return self.response


class FakeOlsClient:
    def __init__(self, *, search_results=None, ontology_metadata=None) -> None:
        self.search_results = list(search_results or [])
        self.ontology_metadata = dict(ontology_metadata or {})
        self.search_calls = []
        self.ontology_calls = []

    def search(self, label, *, ontology_id=None, rows=25):
        self.search_calls.append(
            {"label": label, "ontology_id": ontology_id, "rows": rows}
        )
        if self.search_results:
            return self.search_results.pop(0)
        return []

    def ontology(self, ontology_id):
        self.ontology_calls.append(ontology_id)
        return self.ontology_metadata.get(ontology_id, {})


class FakeSearchClient:
    def __init__(self, results=None) -> None:
        self.results = list(results or [])
        self.calls = []

    def search(self, query, *, max_results=25):
        self.calls.append({"query": query, "max_results": max_results})
        return self.results


class FakeGroundedLLM:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.calls = []
        self.response = response or {
            "text": "Lung maps to UBERON:0002048.",
            "citations": [
                {
                    "url": "https://example.org/lung",
                    "title": "Lung ontology entry",
                    "start_index": 0,
                    "end_index": 4,
                }
            ],
            "tool_calls": [
                {
                    "type": "google_search_call",
                    "arguments": {"queries": ["lung ontology"]},
                }
            ],
            "provider": "gemini_enterprise",
        }
        self.error = error

    def generate_response_with_metadata(
        self,
        prompt,
        *,
        model=None,
        config=None,
        tools=None,
        **extra_options,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "config": config,
                "tools": tools,
                "extra_options": extra_options,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


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


def ontology_json_file(tmp_path: Path, name: str, terms: dict) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "ontology": {"title": f"{name} ontology"},
                "terms": terms,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_ontology_harmonizer_can_be_imported_from_subpackage() -> None:
    assert SubpackageOntologyHarmonizer is OntologyHarmonizer


def test_ontology_harmonizer_is_exported_from_package_root() -> None:
    assert RootOntologyHarmonizer is OntologyHarmonizer


def test_ontostore_can_be_imported_from_subpackage() -> None:
    assert OntoStore.__name__ == "OntoStore"


def test_strategy_handlers_can_be_imported_from_subpackage() -> None:
    assert WebsearchStrategyHandler.__name__ == "WebsearchStrategyHandler"
    assert GeminiGroundedSearchClient.__name__ == "GeminiGroundedSearchClient"
    assert RagStrategyHandler.__name__ == "RagStrategyHandler"


def test_harmonization_target_extractor_can_be_imported_from_subpackage() -> None:
    assert HarmonizationTargetExtractor.__name__ == "HarmonizationTargetExtractor"


def test_harmonization_target_extractor_can_be_imported_from_module() -> None:
    assert DirectHarmonizationTargetExtractor is HarmonizationTargetExtractor


def test_harmonizer_uses_harmonization_target_extractor() -> None:
    assert isinstance(OntologyHarmonizer().target_extractor, HarmonizationTargetExtractor)


def test_ontostore_initializes_with_default_frameworks(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    assert store.ontology_frameworks["efo"] == {
        **DEFAULT_ONTOLOGY_FRAMEWORKS["efo"],
        "owl_path": tmp_path / "efo.owl",
        "json_path": tmp_path / "jsons" / "efo.json",
    }
    assert store.ontology_frameworks["mondo"] == {
        **DEFAULT_ONTOLOGY_FRAMEWORKS["mondo"],
        "owl_path": tmp_path / "mondo-international.owl",
        "json_path": tmp_path / "jsons" / "mondo-international.json",
    }
    assert store.storage_dir == tmp_path


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
        **store._normalize_frameworks(DEFAULT_ONTOLOGY_FRAMEWORKS),
        "CL": {
            "url": "https://example.org/cl.owl",
            "owl_path": tmp_path / "cl.owl",
            "json_path": tmp_path / "jsons" / "cl.json",
        },
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
        "owl_path": tmp_path / "custom-efo.owl",
        "json_path": tmp_path / "jsons" / "custom-efo.json",
    }


def test_add_url_adds_single_framework_url_with_extra_attributes(
    tmp_path: Path,
) -> None:
    store = OntoStore(storage_dir=tmp_path)
    owl_path = tmp_path / "downloads" / "cl.owl"
    json_path = tmp_path / "parsed" / "cl.json"

    store.add_url(
        "CL",
        "https://example.org/cl.owl",
        owl_path=owl_path,
        json_path=json_path,
        version="v1",
        title="Cell Ontology",
        description="Cells.",
    )

    assert store.ontology_frameworks["CL"] == {
        "url": "https://example.org/cl.owl",
        "owl_path": owl_path,
        "json_path": json_path,
        "version": "v1",
        "title": "Cell Ontology",
        "description": "Cells.",
    }


def test_add_urls_merges_frameworks_with_extra_attributes(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)
    local_owl = tmp_path / "local.owl"
    local_json = tmp_path / "local.json"

    store.add_urls(
        {
            "CL": {
                "url": "https://example.org/cl.owl",
                "version": "v1",
            },
            "local": {
                "path": local_owl,
                "json_path": local_json,
                "title": "Local Ontology",
            },
        }
    )

    assert store.ontology_frameworks["CL"] == {
        "url": "https://example.org/cl.owl",
        "version": "v1",
        "owl_path": tmp_path / "cl.owl",
        "json_path": tmp_path / "jsons" / "cl.json",
    }
    assert store.ontology_frameworks["local"] == {
        "owl_path": local_owl,
        "json_path": local_json,
        "title": "Local Ontology",
    }


def test_configure_framework_adds_single_framework_url(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    store.configure_framework("CL", url="https://example.org/cl.owl", version="v1")

    assert store.ontology_frameworks["CL"] == {
        "url": "https://example.org/cl.owl",
        "owl_path": tmp_path / "cl.owl",
        "json_path": tmp_path / "jsons" / "cl.json",
        "version": "v1",
    }


def test_configure_framework_adds_single_framework_path(tmp_path: Path) -> None:
    ontology_path = tmp_path / "local.owl"
    store = OntoStore(storage_dir=tmp_path)

    store.configure_framework(
        "local",
        path=ontology_path,
        title="Local Ontology",
        description="A local OWL ontology.",
    )

    assert store.ontology_frameworks["local"] == {
        "owl_path": ontology_path,
        "json_path": tmp_path / "jsons" / "local.json",
        "title": "Local Ontology",
        "description": "A local OWL ontology.",
    }


def test_configure_framework_replaces_existing_framework(tmp_path: Path) -> None:
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    store.configure_framework("CL", url="https://example.org/new-cl.owl")

    assert store.ontology_frameworks["CL"] == {
        "url": "https://example.org/new-cl.owl",
        "owl_path": tmp_path / "new-cl.owl",
        "json_path": tmp_path / "jsons" / "new-cl.json",
    }


def test_configure_framework_removes_framework_config(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "cl.owl"
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )
    store.ontology_frameworks["CL"]["owl_path"] = existing

    store.configure_framework("CL", remove=True)

    assert "CL" not in store.ontology_frameworks


def test_configure_framework_remove_unknown_framework_raises_key_error(
    tmp_path: Path,
) -> None:
    store = OntoStore(storage_dir=tmp_path)

    with pytest.raises(KeyError, match="CL"):
        store.configure_framework("CL", remove=True)


def test_configure_framework_rejects_url_and_path_together(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    with pytest.raises(ValueError, match="exactly one"):
        store.configure_framework(
            "CL",
            url="https://example.org/cl.owl",
            path=tmp_path / "cl.owl",
        )


def test_configure_framework_rejects_missing_url_or_path(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    with pytest.raises(ValueError, match="exactly one"):
        store.configure_framework("CL")


def test_configure_framework_rejects_remove_with_metadata(tmp_path: Path) -> None:
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="remove"):
        store.configure_framework("CL", remove=True, version="v1")


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
    assert store.ontology_frameworks["CL"]["owl_path"] == tmp_path / "cl.owl"
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
    assert store.ontology_frameworks["CL"]["owl_path"] == existing


def test_download_path_framework_returns_local_path_without_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    existing = tmp_path / "local.owl"
    existing.write_bytes(ontology_bytes())

    def fake_get(url, *, timeout):
        raise AssertionError("requests.get should not be called")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(storage_dir=tmp_path)
    store.configure_framework("local", path=existing)

    result = store.download("local")

    assert result == existing
    assert store.ontology_frameworks["local"]["owl_path"] == existing


def test_download_path_framework_missing_file_raises_file_not_found(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.owl"
    store = OntoStore(storage_dir=tmp_path)
    store.configure_framework("local", path=missing)

    with pytest.raises(FileNotFoundError, match="missing.owl"):
        store.download("local")


def test_download_raises_key_error_for_unknown_framework(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    with pytest.raises(KeyError, match="CL"):
        store.download("CL")


def test_download_raises_value_error_for_missing_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="CL"):
        OntoStore(
            ontology_frameworks={"CL": {}},
            storage_dir=tmp_path,
        )


def test_download_raises_value_error_for_url_without_filename(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="filename"):
        OntoStore(
            ontology_frameworks={"CL": {"url": "https://example.org/"}},
            storage_dir=tmp_path,
        )


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
    assert store.ontology_frameworks["CL"]["owl_path"] == tmp_path / "cl.owl"


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
    assert '"id": "CL"' in result.read_text(encoding="utf-8")
    assert store.ontology_frameworks["CL"]["owl_path"] == tmp_path / "cl.owl"
    assert store.ontology_frameworks["CL"]["json_path"] == tmp_path / "jsons" / "cl.json"
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
    assert store.ontology_frameworks["CL"]["owl_path"] == existing


def test_get_returns_existing_json_without_calling_download(tmp_path: Path) -> None:
    existing = tmp_path / "cl.owl"
    existing.write_bytes(b"invalid existing ontology")
    existing_json = tmp_path / "jsons" / "cl.json"
    existing_json.parent.mkdir(parents=True)
    existing_json.write_text(
        '{"cached": true, "ontology": {"title": "cached ontology"}}\n',
        encoding="utf-8",
    )

    class DownloadFailingStore(OntoStore):
        def download(self, name: str) -> Path:
            raise AssertionError("download should not be called")

    store = DownloadFailingStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.get("CL")

    assert result == existing_json
    assert json.loads(result.read_text(encoding="utf-8")) == {
        "cached": True,
        "ontology": {"title": "cached ontology", "id": "CL"},
    }
    assert store.ontology_frameworks["CL"]["json_path"] == existing_json


def test_get_updates_stale_existing_json_ontology_id(tmp_path: Path) -> None:
    existing = tmp_path / "cl.owl"
    existing.write_bytes(b"invalid existing ontology")
    existing_json = tmp_path / "jsons" / "cl.json"
    existing_json.parent.mkdir(parents=True)
    existing_json.write_text(
        '{"ontology": {"id": "old", "title": "cached ontology"}, "terms": {}}\n',
        encoding="utf-8",
    )
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    result = store.get("CL")

    assert result == existing_json
    assert json.loads(result.read_text(encoding="utf-8"))["ontology"] == {
        "id": "CL",
        "title": "cached ontology",
    }


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
    assert store.ontology_frameworks["CL"]["owl_path"] == existing_owl
    assert store.ontology_frameworks["CL"]["json_path"] == existing_json
    assert calls == [{"url": "https://example.org/cl.owl", "timeout": 30}]


def test_get_path_framework_parses_local_ontology_without_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    local_owl = tmp_path / "local.owl"
    local_owl.write_bytes(ontology_bytes())

    def fake_get(url, *, timeout):
        raise AssertionError("requests.get should not be called")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(storage_dir=tmp_path)
    store.configure_framework("local", path=local_owl)

    result = store.get("local")

    assert result == tmp_path / "jsons" / "local.json"
    assert '"CL:0000000"' in result.read_text(encoding="utf-8")
    assert store.ontology_frameworks["local"]["owl_path"] == local_owl
    assert store.ontology_frameworks["local"]["json_path"] == result


def test_get_force_reparses_path_framework_without_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    local_owl = tmp_path / "local.owl"
    local_owl.write_bytes(ontology_bytes(title="New Cell Ontology"))
    existing_json = tmp_path / "jsons" / "local.json"
    existing_json.parent.mkdir(parents=True)
    existing_json.write_text('{"cached": true}\n', encoding="utf-8")

    def fake_get(url, *, timeout):
        raise AssertionError("requests.get should not be called")

    monkeypatch.setattr(ontology_store.requests, "get", fake_get)
    store = OntoStore(storage_dir=tmp_path)
    store.configure_framework("local", path=local_owl)

    result = store.get("local", force=True)

    assert result == existing_json
    assert "New Cell Ontology" in existing_json.read_text(encoding="utf-8")
    assert store.ontology_frameworks["local"]["owl_path"] == local_owl
    assert store.ontology_frameworks["local"]["json_path"] == existing_json


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
    assert store.ontology_frameworks["CL"]["owl_path"] == tmp_path / "cl.owl"


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
    assert store.ontology_frameworks["CL"]["owl_path"] == tmp_path / "cl.owl"
    assert store.ontology_frameworks["CL"]["json_path"] == tmp_path / "jsons" / "cl.json"


def test_ontostore_harmonize_key_normalizes_simple_text() -> None:
    assert OntoStore.harmonize_key("  Oral   Buccal mucosa, ") == "oral_buccal_mucosa"
    assert OntoStore.harmonize_key("UBERON:0002048") == "uberon:0002048"
    assert (
        OntoStore.harmonize_key("HTTP://PURL.OBOLIBRARY.ORG/OBO/UBERON_0002048")
        == "http://purl.obolibrary.org/obo/uberon_0002048"
    )


def test_ontostore_initializes_empty_fields_by_default(tmp_path: Path) -> None:
    assert OntoStore(storage_dir=tmp_path).fields == {}


def test_ontostore_lookup_fields_matches_key_label_and_aliases(
    tmp_path: Path,
) -> None:
    store = OntoStore(
        fields={
            "tissue": {
                "label": "Tissue",
                "aliases": ["sample type", "biospecimen source"],
                "description": "Sample tissue.",
            }
        },
        storage_dir=tmp_path,
    )

    assert store.lookup_fields(" Tissue ") == {
        "field": "tissue",
        "label": "Tissue",
        "aliases": ["sample type", "biospecimen source"],
        "description": "Sample tissue.",
    }
    assert store.lookup_fields("sample   type") == {
        "field": "tissue",
        "label": "Tissue",
        "aliases": ["sample type", "biospecimen source"],
        "description": "Sample tissue.",
    }
    assert store.lookup_fields("unknown") is False


def test_lookup_matches_label_index(tmp_path: Path) -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "lung",
    }
    json_path = ontology_json_file(tmp_path, "uberon", {"label": {"lung": [term]}})
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )

    assert store.lookup(" Lung, ", "uberon") == [{**term, "ontology_id": "uberon"}]


def test_lookup_matches_id_accession_and_iri_indexes(tmp_path: Path) -> None:
    accession_term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "lung",
    }
    id_term = {
        "iri": "https://example.org/custom-id",
        "accession": None,
        "title": "custom id term",
    }
    json_path = ontology_json_file(
        tmp_path,
        "lookup",
        {
            "id": {"custom:1": id_term},
            "accession": {"uberon:0002048": accession_term},
            "iri": {
                "http://purl.obolibrary.org/obo/uberon_0002048": accession_term
            },
        },
    )
    store = OntoStore(
        ontology_frameworks={
            "lookup": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )

    assert store.lookup("CUSTOM:1", "lookup") == [
        {
            **id_term,
            "ontology_id": "lookup",
        }
    ]
    assert store.lookup("UBERON:0002048", "lookup") == [
        {
            **accession_term,
            "ontology_id": "lookup",
        }
    ]
    assert (
        store.lookup("http://purl.obolibrary.org/obo/UBERON_0002048", "lookup")
        == [{**accession_term, "ontology_id": "lookup"}]
    )


def test_lookup_returns_empty_list_when_label_is_absent(tmp_path: Path) -> None:
    json_path = ontology_json_file(tmp_path, "empty", {"label": {}})
    store = OntoStore(
        ontology_frameworks={
            "empty": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )

    assert store.lookup("lung", "empty") == []


def test_lookup_returns_all_hits_across_indexes_with_deduplication(
    tmp_path: Path,
) -> None:
    label_term = {
        "id": "label-hit",
        "iri": "https://example.org/label-hit",
        "accession": "LOOKUP:1",
        "title": "label hit",
    }
    duplicate_term = {
        "id": "duplicate-hit",
        "iri": "https://example.org/duplicate-hit",
        "accession": "LOOKUP:2",
        "title": "duplicate hit",
    }
    id_term = {
        "id": "id-hit",
        "iri": "https://example.org/id-hit",
        "accession": "LOOKUP:3",
        "title": "id hit",
    }
    json_path = ontology_json_file(
        tmp_path,
        "lookup",
        {
            "label": {"lung": [label_term, duplicate_term]},
            "id": {"lung": duplicate_term},
            "accession": {"lung": id_term},
            "iri": {"lung": label_term},
        },
    )
    store = OntoStore(
        ontology_frameworks={
            "lookup": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )

    assert store.lookup("lung", "lookup") == [
        {**label_term, "ontology_id": "lookup"},
        {**duplicate_term, "ontology_id": "lookup"},
        {**id_term, "ontology_id": "lookup"},
    ]


def test_lookup_normalizes_existing_raw_json_index_keys(tmp_path: Path) -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "Oral Buccal Mucosa",
    }
    json_path = ontology_json_file(
        tmp_path,
        "uberon",
        {"label": {"Oral Buccal Mucosa": [term]}},
    )
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )

    assert store.lookup(" oral   buccal mucosa ", "uberon") == [
        {**term, "ontology_id": "uberon"}
    ]


def test_lookup_label_matches_available_store_framework(
    tmp_path: Path,
) -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "lung",
    }
    json_path = ontology_json_file(
        tmp_path,
        "uberon",
        {"label": {"oral_buccal_mucosa": [term]}},
    )
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )
    target = {
        "id": "target-0",
        "pre_hz_field": " Tissue Type ",
        "pre_hz_label": " Oral   Buccal mucosa, ",
        "occurrences": [
            {
                "pre_hz_field": " Tissue Type ",
                "pre_hz_label": " Oral   Buccal mucosa, ",
                "hz_field": " Tissue Type ",
                "hz_label": " Oral   Buccal mucosa, ",
            }
        ],
    }

    result = OntologyHarmonizer().lookup_label(
        target,
        publication_context=None,
        ontostore=store,
        strategy="websearch",
    )

    expected_lookup = {**term, "ontology_id": "uberon"}
    assert result == expected_lookup
    assert target["ontology_id"] == "uberon"
    assert target["ontology_lookup"] == expected_lookup
    assert target["ontology_lookup_hits"] == [expected_lookup]
    assert target["ontology_match"] is True
    assert target["hz_field"] == "tissue_type"
    assert target["hz_label"] == "oral_buccal_mucosa"
    assert target["occurrences"][0]["hz_field"] == "tissue_type"
    assert target["occurrences"][0]["hz_label"] == "oral_buccal_mucosa"


def test_lookup_label_uses_existing_hz_label_after_harmonizing_it(
    tmp_path: Path,
) -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "lung",
    }
    json_path = ontology_json_file(tmp_path, "uberon", {"label": {"lung": [term]}})
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )
    target = {
        "id": "target-0",
        "pre_hz_field": "tissue",
        "pre_hz_label": "does not match",
        "hz_label": " Lung, ",
    }

    result = OntologyHarmonizer().lookup_label(
        target,
        publication_context=None,
        ontostore=store,
        strategy="websearch",
    )

    expected_lookup = {**term, "ontology_id": "uberon"}
    assert result == expected_lookup
    assert target["ontology_lookup"] == expected_lookup
    assert target["ontology_lookup_hits"] == [expected_lookup]
    assert target["hz_field"] == "tissue"
    assert target["hz_label"] == "lung"


def test_lookup_label_selects_first_hit_without_llm_judge_by_default(
    tmp_path: Path,
) -> None:
    first_hit = {
        "id": "UBERON:1",
        "iri": "https://example.org/UBERON_1",
        "accession": "UBERON:1",
        "title": "first lung",
    }
    second_hit = {
        "id": "UBERON:2",
        "iri": "https://example.org/UBERON_2",
        "accession": "UBERON:2",
        "title": "second lung",
    }
    json_path = ontology_json_file(
        tmp_path,
        "uberon",
        {"label": {"lung": [first_hit, second_hit]}},
    )
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )
    fake_llm = FakeLLM()
    target = {"id": "target-0", "pre_hz_label": "lung"}

    result = OntologyHarmonizer(llm=fake_llm).lookup_label(
        target,
        publication_context="lung sample context",
        ontostore=store,
        strategy="websearch",
    )

    expected_hits = [
        {**first_hit, "ontology_id": "uberon"},
        {**second_hit, "ontology_id": "uberon"},
    ]
    assert result == expected_hits[0]
    assert target["ontology_lookup"] == expected_hits[0]
    assert target["ontology_lookup_hits"] == expected_hits
    assert "ontology_lookup_judgement" not in target
    assert fake_llm.calls == []


def test_lookup_label_llm_judge_is_not_called_below_threshold(
    tmp_path: Path,
) -> None:
    hit = {
        "id": "UBERON:1",
        "iri": "https://example.org/UBERON_1",
        "accession": "UBERON:1",
        "title": "lung",
    }
    json_path = ontology_json_file(tmp_path, "uberon", {"label": {"lung": [hit]}})
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )
    fake_llm = FakeLLM(response={"decision": "UBERON:1"})
    target = {"id": "target-0", "pre_hz_label": "lung"}

    result = OntologyHarmonizer(llm=fake_llm).lookup_label(
        target,
        publication_context="context",
        ontostore=store,
        strategy="websearch",
        lookup_llm_judge=True,
    )

    expected_hit = {**hit, "ontology_id": "uberon"}
    assert result == expected_hit
    assert target["ontology_lookup"] == expected_hit
    assert target["ontology_lookup_hits"] == [expected_hit]
    assert "ontology_lookup_judgement" not in target
    assert fake_llm.calls == []


def test_lookup_label_llm_judge_selects_best_hit_by_id(
    tmp_path: Path,
) -> None:
    first_hit = {
        "id": "UBERON:1",
        "iri": "https://example.org/UBERON_1",
        "accession": "UBERON:1",
        "title": "generic lung",
    }
    second_hit = {
        "id": "UBERON:2",
        "iri": "https://example.org/UBERON_2",
        "accession": "UBERON:2",
        "title": "oral buccal mucosa",
    }
    response = {
        "decision": "UBERON:2",
        "confidence": "high",
        "reason": "Publication context describes oral buccal tissue.",
    }
    json_path = ontology_json_file(
        tmp_path,
        "uberon",
        {"label": {"lung": [first_hit, second_hit]}},
    )
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )
    fake_llm = FakeLLM(response=json.dumps(response))
    target = {
        "id": "target-0",
        "pre_hz_field": "tissue",
        "pre_hz_label": "lung",
    }

    result = OntologyHarmonizer(llm=fake_llm).lookup_label(
        target,
        publication_context="sample is oral buccal tissue",
        ontostore=store,
        strategy="websearch",
        lookup_llm_judge=True,
    )

    expected_hits = [
        {**first_hit, "ontology_id": "uberon"},
        {**second_hit, "ontology_id": "uberon"},
    ]
    assert result == expected_hits[1]
    assert target["ontology_lookup"] == expected_hits[1]
    assert target["ontology_lookup_hits"] == expected_hits
    assert target["ontology_lookup_judgement"] == response
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0]["config"] == {
        "response_mime_type": "application/json",
        "response_schema": OntologyHarmonizer()._lookup_judge_response_schema(),
    }
    assert fake_llm.calls[0]["prompt"].startswith(JUDGE_LOOKUP_PROMPT)
    assert "Publication Context:\nsample is oral buccal tissue" in fake_llm.calls[0][
        "prompt"
    ]
    assert '"id": "target-0"' in fake_llm.calls[0]["prompt"]
    assert '"id": "UBERON:2"' in fake_llm.calls[0]["prompt"]


def test_lookup_label_llm_judge_rejects_unknown_decision(
    tmp_path: Path,
) -> None:
    hits = [
        {
            "id": "UBERON:1",
            "iri": "https://example.org/UBERON_1",
            "accession": "UBERON:1",
            "title": "first lung",
        },
        {
            "id": "UBERON:2",
            "iri": "https://example.org/UBERON_2",
            "accession": "UBERON:2",
            "title": "second lung",
        },
    ]
    json_path = ontology_json_file(tmp_path, "uberon", {"label": {"lung": hits}})
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )
    response = {
        "decision": "UBERON:missing",
        "confidence": "low",
        "reason": "bad decision",
    }

    with pytest.raises(ValueError, match="known lookup hit id"):
        OntologyHarmonizer(llm=FakeLLM(response=response)).lookup_label(
            {"id": "target-0", "pre_hz_label": "lung"},
            publication_context=None,
            ontostore=store,
            strategy="websearch",
            lookup_llm_judge=True,
        )


def test_lookup_judge_response_schema_requires_decision_fields() -> None:
    assert OntologyHarmonizer()._lookup_judge_response_schema() == {
        "type": "OBJECT",
        "properties": {
            "decision": {"type": "STRING"},
            "confidence": {"type": "STRING"},
            "reason": {"type": "STRING"},
        },
        "required": ["decision", "confidence", "reason"],
    }


def test_lookup_label_llm_judge_raises_value_error_for_invalid_json_response(
    tmp_path: Path,
) -> None:
    hits = [
        {"id": "UBERON:1", "title": "first lung"},
        {"id": "UBERON:2", "title": "second lung"},
    ]
    json_path = ontology_json_file(tmp_path, "uberon", {"label": {"lung": hits}})
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="valid JSON"):
        OntologyHarmonizer(llm=FakeLLM(response="not json")).lookup_label(
            {"id": "target-0", "pre_hz_label": "lung"},
            publication_context=None,
            ontostore=store,
            strategy="websearch",
            lookup_llm_judge=True,
        )


def test_lookup_label_respects_target_framework_subset(
    tmp_path: Path,
) -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "lung",
    }
    empty_json = ontology_json_file(tmp_path, "empty", {"label": {}})
    uberon_json = ontology_json_file(
        tmp_path, "uberon", {"label": {"lung": [term]}}
    )
    store = OntoStore(
        ontology_frameworks={
            "empty": {"path": tmp_path / "missing-empty.owl", "json_path": empty_json},
            "uberon": {
                "path": tmp_path / "missing-uberon.owl",
                "json_path": uberon_json,
            },
        },
        storage_dir=tmp_path,
    )
    target = {
        "id": "target-0",
        "pre_hz_label": "lung",
        "ontology_frameworks": ["empty"],
    }

    result = OntologyHarmonizer().lookup_label(
        target,
        publication_context=None,
        ontostore=store,
        strategy="websearch",
    )

    assert result is False
    assert "ontology_match" not in target
    assert "ontology_id" not in target
    assert "ontology_lookup" not in target


def test_assign_onto_framework_uses_llm_framework_decision(tmp_path: Path) -> None:
    response = {
        "decision": "anatomy",
        "confidence": "high",
        "reason": "The target is an anatomical tissue.",
    }
    fake_llm = FakeLLM(response=json.dumps(response))
    store = OntoStore(
        ontology_frameworks={
            "anatomy": {
                "title": "Anatomy Ontology",
                "url": "https://example.org/anatomy.owl",
                "description": "Anatomical entities.",
                "version": "2026-01-01",
            },
            "disease": {
                "title": "Disease Ontology",
                "url": "https://example.org/disease.owl",
                "description": "Disease entities.",
            },
        },
        storage_dir=tmp_path,
    )
    target = {
        "id": "target-0",
        "pre_hz_label": "lung",
        "ontology_id": "old",
        "ontology_lookup": {"title": "old"},
        "ontology_ids": ["anatomy"],
    }

    result = OntologyHarmonizer(llm=fake_llm).assign_onto_framework(
        target,
        publication_context="sample is from lung tissue",
        ontostore=store,
    )

    assert result == response
    assert target["ontology_match"] is False
    assert target["ontology_id"] == "anatomy"
    assert "ontology_lookup" not in target
    assert target["ontology_framework_assignment"] == response
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0]["model"] is None
    assert fake_llm.calls[0]["extra_options"] == {}
    assert fake_llm.calls[0]["config"] == {
        "response_mime_type": "application/json",
        "response_schema": OntologyHarmonizer()._assign_onto_framework_response_schema(),
    }
    assert fake_llm.calls[0]["prompt"].startswith(ASSIGN_ONTO_FRAMEWORK_PROMPT)
    assert "Strategy:" not in fake_llm.calls[0]["prompt"]
    assert "Publication Context:\nsample is from lung tissue" in fake_llm.calls[0][
        "prompt"
    ]
    assert '"id": "target-0"' in fake_llm.calls[0]["prompt"]
    assert '"anatomy"' in fake_llm.calls[0]["prompt"]
    assert '"id": "anatomy"' in fake_llm.calls[0]["prompt"]
    assert '"title": "Anatomy Ontology"' in fake_llm.calls[0]["prompt"]
    assert '"description": "Anatomical entities."' in fake_llm.calls[0]["prompt"]
    assert '"version": "2026-01-01"' in fake_llm.calls[0]["prompt"]
    assert '"url"' not in fake_llm.calls[0]["prompt"]
    assert '"path"' not in fake_llm.calls[0]["prompt"]
    assert '"owl_path"' not in fake_llm.calls[0]["prompt"]
    assert '"json_path"' not in fake_llm.calls[0]["prompt"]
    assert "https://example.org/anatomy.owl" not in fake_llm.calls[0]["prompt"]
    assert str(tmp_path) not in fake_llm.calls[0]["prompt"]
    assert '"Disease Ontology"' not in fake_llm.calls[0]["prompt"]


def test_assign_onto_framework_stores_false_decision_without_ontology_id() -> None:
    response = {
        "decision": "false",
        "confidence": "none",
        "reason": "No configured framework matches.",
    }
    target = {
        "id": "target-0",
        "pre_hz_label": "unmapped",
        "ontology_id": "old",
        "ontology_lookup": {"title": "old"},
    }

    result = OntologyHarmonizer(llm=FakeLLM(response=response)).assign_onto_framework(
        target,
        publication_context=None,
        ontostore=OntoStore(),
    )

    assert result == response
    assert target["ontology_match"] is False
    assert "ontology_id" not in target
    assert "ontology_lookup" not in target
    assert target["ontology_framework_assignment"] == response


def test_assign_onto_framework_response_schema_requires_decision_fields() -> None:
    assert OntologyHarmonizer()._assign_onto_framework_response_schema() == {
        "type": "OBJECT",
        "properties": {
            "decision": {"type": "STRING"},
            "confidence": {"type": "STRING"},
            "reason": {"type": "STRING"},
        },
        "required": ["decision", "confidence", "reason"],
    }


def test_assign_onto_framework_raises_value_error_for_invalid_json_response() -> None:
    target = {"id": "target-0", "pre_hz_label": "lung"}

    with pytest.raises(ValueError, match="valid JSON"):
        OntologyHarmonizer(llm=FakeLLM(response="not json")).assign_onto_framework(
            target,
            publication_context=None,
            ontostore=OntoStore(),
        )


def test_harmonize_field_uses_ontostore_field_lookup(tmp_path: Path) -> None:
    store = OntoStore(
        fields={
            "tissue": {
                "label": "Tissue",
                "aliases": ["sample source"],
                "description": "Sample tissue.",
            }
        },
        storage_dir=tmp_path,
    )
    target = {
        "id": "target-0",
        "pre_hz_field": " Sample Source ",
        "pre_hz_label": "lung",
    }

    result = OntologyHarmonizer().harmonize_field(
        target,
        publication_context="context",
        ontostore=store,
    )

    assert result == {
        "field": "tissue",
        "label": "Tissue",
        "aliases": ["sample source"],
        "description": "Sample tissue.",
    }
    assert target["hz_field"] == "tissue"
    assert target["field_lookup"] == result
    assert "field_assignment" not in target


def test_assign_field_generates_json_response_and_adds_new_field(
    tmp_path: Path,
) -> None:
    response = {
        "decision": "development_stage",
        "confidence": "medium",
        "reason": "The source field describes sample development stage.",
        "new_field": True,
    }
    fake_llm = FakeLLM(response=json.dumps(response))
    store = OntoStore(
        fields={"tissue": {"label": "Tissue"}},
        storage_dir=tmp_path,
    )
    target = {
        "id": "target-0",
        "pre_hz_field": "developmental stage",
        "hz_field": "developmental_stage",
        "pre_hz_label": "adult",
    }

    result = OntologyHarmonizer(llm=fake_llm).assign_field(
        target,
        publication_context="sample metadata context",
        ontostore=store,
    )

    assert result == response
    assert target["hz_field"] == "development_stage"
    assert target["field_assignment"] == response
    assert store.fields["development_stage"] == {
        "label": "development_stage",
        "source": "llm",
        "confidence": "medium",
        "reason": "The source field describes sample development stage.",
    }
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0]["config"] == {
        "response_mime_type": "application/json",
        "response_schema": OntologyHarmonizer()._assign_field_response_schema(),
    }
    assert fake_llm.calls[0]["prompt"].startswith(ASSIGN_FIELD_PROMPT)
    assert "Publication Context:\nsample metadata context" in fake_llm.calls[0][
        "prompt"
    ]
    assert '"id": "target-0"' in fake_llm.calls[0]["prompt"]
    assert '"tissue"' in fake_llm.calls[0]["prompt"]


def test_assign_field_response_schema_requires_assignment_fields() -> None:
    assert OntologyHarmonizer()._assign_field_response_schema() == {
        "type": "OBJECT",
        "properties": {
            "decision": {"type": "STRING"},
            "confidence": {"type": "STRING"},
            "reason": {"type": "STRING"},
            "new_field": {"type": "BOOLEAN"},
        },
        "required": ["decision", "confidence", "reason", "new_field"],
    }


def test_assign_field_raises_value_error_for_invalid_json_response() -> None:
    target = {"id": "target-0", "pre_hz_field": "stage"}

    with pytest.raises(ValueError, match="valid JSON"):
        OntologyHarmonizer(llm=FakeLLM(response="not json")).assign_field(
            target,
            publication_context=None,
            ontostore=OntoStore(),
        )


def test_harmonize_assigns_ontology_metadata_from_store(tmp_path: Path) -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "lung",
    }
    json_path = ontology_json_file(tmp_path, "uberon", {"label": {"lung": [term]}})
    store = OntoStore(
        ontology_frameworks={
            "uberon": {"path": tmp_path / "missing.owl", "json_path": json_path}
        },
        storage_dir=tmp_path,
    )

    result = OntologyHarmonizer(ontostore=store).harmonize(
        target={
            "id": "target-0",
            "pre_hz_label": "lung",
            "ontology_ids": ["uberon"],
        }
    )

    target = result["harmonization_targets"][0]
    assert target["ontology_match"] is True
    assert target["ontology_id"] == "uberon"
    assert target["ontology_lookup"] == {**term, "ontology_id": "uberon"}
    assert target["ontology_lookup_hits"] == [{**term, "ontology_id": "uberon"}]


def test_harmonize_llm_false_skips_framework_and_field_assignment() -> None:
    fake_llm = FakeLLM()
    target = {
        "id": "target-0",
        "pre_hz_field": "unmapped field",
        "pre_hz_label": "unmapped label",
    }

    result = OntologyHarmonizer(llm=fake_llm).harmonize(
        publication_context="context",
        target=target,
        llm=False,
    )

    assert result["harmonization_targets"] == [target]
    assert target["ontology_match"] is False
    assert "ontology_framework_assignment" not in target
    assert "field_assignment" not in target
    assert fake_llm.calls == []


def miniml_metadata() -> dict:
    return {
        "sample": [
            {
                "iid": "GSM1",
                "channel": [
                    {
                        "position": "1",
                        "source": "Oral buccal mucosa",
                        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
                        "characteristics": [
                            {"tag": "disease state", "value": "Normal"},
                            {"tag": "tissue", "value": "Oral buccal mucosa"},
                        ],
                        "molecule": "total RNA",
                        "extract_protocol": "Long protocol text is not a target.",
                    }
                ],
            },
            {
                "iid": "GSM2",
                "channel": [
                    {
                        "position": "1",
                        "source": "Oral buccal mucosa",
                        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
                        "characteristics": [
                            {"tag": "disease state", "value": "Disease"},
                            {"tag": "tissue", "value": "Oral buccal mucosa"},
                        ],
                        "molecule": "total RNA",
                    }
                ],
            },
        ]
    }


def test_harmonize_returns_targets_wrapper() -> None:
    harmonization_targets = [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
        }
    ]
    ontostore = OntoStore()

    result = OntologyHarmonizer(llm=FakeLLM()).harmonize(
        publication_context="Full publication context",
        harmonization_targets=harmonization_targets,
        ontostore=ontostore,
        target_paths=["/sample"],
    )

    assert result == {
        "publication_context": "Full publication context",
        "harmonization_targets": harmonization_targets,
        "strategy": "websearch",
        "target_paths": ["/sample"],
    }


def test_harmonize_accepts_single_target() -> None:
    target = {
        "id": "target-0",
        "source": "metadata",
        "pre_hz_field": "tissue",
        "pre_hz_label": "lung",
    }

    result = OntologyHarmonizer(llm=FakeLLM()).harmonize(target=target)

    assert result == {
        "publication_context": None,
        "harmonization_targets": [target],
        "strategy": "websearch",
        "target_paths": None,
    }


def test_harmonize_accepts_dict_harmonization_target() -> None:
    target = {
        "id": "target-0",
        "source": "metadata",
        "pre_hz_field": "organism",
        "pre_hz_label": "Homo sapiens",
    }

    result = OntologyHarmonizer(llm=FakeLLM()).harmonize(harmonization_targets=target)

    assert result["harmonization_targets"] == [target]


def test_harmonize_rejects_target_and_targets_together() -> None:
    with pytest.raises(ValueError, match="target"):
        OntologyHarmonizer().harmonize(
            target={"id": "target-0"},
            harmonization_targets=[{"id": "target-1"}],
        )


def test_harmonize_rejects_noop_strategy() -> None:
    with pytest.raises(ValueError, match="strategy"):
        OntologyHarmonizer().harmonize(
            harmonization_targets=[],
            strategy="noop",
        )


def test_harmonize_rejects_identity_strategy() -> None:
    with pytest.raises(ValueError, match="strategy"):
        OntologyHarmonizer().harmonize(
            harmonization_targets=[],
            strategy="identity",
        )


def test_harmonize_accepts_websearch_and_rag_strategies() -> None:
    assert OntologyHarmonizer().harmonize(
        harmonization_targets=[], strategy="websearch"
    )["strategy"] == "websearch"
    assert OntologyHarmonizer().harmonize(harmonization_targets=[], strategy="rag")[
        "strategy"
    ] == "rag"


def test_harmonize_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="strategy"):
        OntologyHarmonizer().harmonize(strategy="exact_match")


def test_harmonize_rejects_direct_strategy() -> None:
    with pytest.raises(ValueError, match="strategy"):
        OntologyHarmonizer().harmonize(strategy="direct")


def test_harmonize_signature_excludes_old_metadata_api() -> None:
    parameters = inspect.signature(OntologyHarmonizer.harmonize).parameters

    assert "title" not in parameters
    assert "metadata" not in parameters
    assert "publication_text" not in parameters
    assert "ontology_frameworks" not in parameters


def test_harmonize_defaults_to_empty_targets() -> None:
    result = OntologyHarmonizer().harmonize()

    assert result == {
        "publication_context": None,
        "harmonization_targets": [],
        "strategy": "websearch",
        "target_paths": None,
    }


def test_harmonizer_creates_default_ontostore() -> None:
    assert isinstance(OntologyHarmonizer().ontostore, OntoStore)


def test_harmonizer_accepts_ontostore_in_constructor() -> None:
    store = OntoStore()

    harmonizer = OntologyHarmonizer(ontostore=store)

    assert harmonizer.ontostore is store


def test_harmonizer_accepts_llm_in_constructor() -> None:
    fake_llm = FakeLLM()

    harmonizer = OntologyHarmonizer(llm=fake_llm)

    assert harmonizer.llm is fake_llm


def test_harmonizer_rejects_ontology_frameworks_constructor_arg() -> None:
    with pytest.raises(TypeError):
        OntologyHarmonizer(ontology_frameworks={"anatomy": "UBERON"})


def test_harmonizer_accepts_custom_frameworks_through_ontostore() -> None:
    store = OntoStore(
        ontology_frameworks={"anatomy": {"url": "https://example.org/anatomy.owl"}}
    )

    harmonizer = OntologyHarmonizer(ontostore=store)

    assert harmonizer.ontostore.ontology_frameworks["anatomy"] == {
        "url": "https://example.org/anatomy.owl",
        "owl_path": OntoStore.DEFAULT_STORAGE_DIR / "anatomy.owl",
        "json_path": OntoStore.DEFAULT_STORAGE_DIR / "jsons" / "anatomy.json",
    }


def test_harmonize_accepts_ontostore_override() -> None:
    store = OntoStore()

    result = OntologyHarmonizer().harmonize(
        harmonization_targets=[],
        ontostore=store,
    )

    assert result == {
        "publication_context": None,
        "harmonization_targets": [],
        "strategy": "websearch",
        "target_paths": None,
    }


def test_harmonize_calls_assign_onto_framework_for_each_target() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def assign_onto_framework(
            self,
            target,
            *,
            publication_context,
            ontostore,
        ):
            calls.append(
                {
                    "target": target,
                    "publication_context": publication_context,
                    "ontostore": ontostore,
                }
            )

        def harmonize_field(self, target, *, publication_context, ontostore, llm=True):
            return False

    store = OntoStore()
    targets = [
        {"id": "target-0", "pre_hz_field": "tissue", "pre_hz_label": "lung"},
        {"id": "target-1", "pre_hz_field": "organism", "pre_hz_label": "human"},
    ]

    result = RecordingHarmonizer(ontostore=store).harmonize(
        publication_context="context",
        harmonization_targets=targets,
    )

    assert result["harmonization_targets"] == targets
    assert calls == [
        {
            "target": targets[0],
            "publication_context": "context",
            "ontostore": store,
        },
        {
            "target": targets[1],
            "publication_context": "context",
            "ontostore": store,
        },
    ]


def test_harmonize_calls_lookup_label_before_assign_onto_framework() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def lookup_label(
            self,
            target,
            *,
            publication_context,
            ontostore,
            strategy,
            lookup_llm_judge=False,
            lookup_llm_threshold=2,
        ):
            calls.append(("lookup", target["id"], publication_context, strategy))
            return False

        def assign_onto_framework(
            self,
            target,
            *,
            publication_context,
            ontostore,
        ):
            calls.append(("assign", target["id"], publication_context))
            return False

        def harmonize_field(self, target, *, publication_context, ontostore, llm=True):
            return False

    target = {"id": "target-0", "pre_hz_label": "lung"}

    RecordingHarmonizer().harmonize(
        publication_context="context",
        target=target,
    )

    assert calls == [
        ("lookup", "target-0", "context", "websearch"),
        ("assign", "target-0", "context"),
    ]


def test_harmonize_skips_assign_onto_framework_when_lookup_label_succeeds() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def lookup_label(
            self,
            target,
            *,
            publication_context,
            ontostore,
            strategy,
            lookup_llm_judge=False,
            lookup_llm_threshold=2,
        ):
            calls.append("lookup")
            target["ontology_match"] = True
            return {"title": "lung"}

        def assign_onto_framework(
            self,
            target,
            *,
            publication_context,
            ontostore,
        ):
            calls.append("assign")
            return False

        def harmonize_field(self, target, *, publication_context, ontostore, llm=True):
            return False

    target = {"id": "target-0", "pre_hz_label": "lung"}

    result = RecordingHarmonizer().harmonize(target=target)

    assert calls == ["lookup"]
    assert result["harmonization_targets"] == [target]
    assert target["ontology_match"] is True


def test_harmonize_single_target_calls_assign_onto_framework_once() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def assign_onto_framework(
            self,
            target,
            *,
            publication_context,
            ontostore,
        ):
            calls.append(target)

        def harmonize_field(self, target, *, publication_context, ontostore, llm=True):
            return False

    target = {"id": "target-0", "pre_hz_field": "tissue", "pre_hz_label": "lung"}

    result = RecordingHarmonizer().harmonize(target=target)

    assert result["harmonization_targets"] == [target]
    assert calls == [target]


def test_harmonize_without_targets_does_not_call_assign_onto_framework() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def assign_onto_framework(
            self,
            target,
            *,
            publication_context,
            ontostore,
        ):
            calls.append(target)

        def harmonize_field(self, target, *, publication_context, ontostore, llm=True):
            return False

    RecordingHarmonizer().harmonize()

    assert calls == []


def test_harmonize_assign_onto_framework_receives_ontostore_override() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def assign_onto_framework(
            self,
            target,
            *,
            publication_context,
            ontostore,
        ):
            calls.append(ontostore)

        def harmonize_field(self, target, *, publication_context, ontostore, llm=True):
            return False

    constructor_store = OntoStore()
    override_store = OntoStore()

    RecordingHarmonizer(ontostore=constructor_store).harmonize(
        target={"id": "target-0"},
        ontostore=override_store,
    )

    assert calls == [override_store]


def test_harmonize_calls_field_harmonization_before_strategy_handler() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def lookup_label(
            self,
            target,
            *,
            publication_context,
            ontostore,
            strategy,
            lookup_llm_judge=False,
            lookup_llm_threshold=2,
        ):
            calls.append("lookup")
            return False

        def assign_onto_framework(
            self,
            target,
            *,
            publication_context,
            ontostore,
        ):
            calls.append("assign_framework")
            return {"decision": "unsure", "confidence": "low", "reason": "none"}

        def harmonize_field(self, target, *, publication_context, ontostore, llm=True):
            calls.append("harmonize_field")
            return {"field": "tissue"}

        def harmonize_label(
            self,
            target,
            *,
            publication_context,
            ontostore,
            strategy,
            lookup_llm_judge=False,
            lookup_llm_threshold=2,
        ):
            calls.append(("strategy", strategy))
            return {"strategy": strategy}

    RecordingHarmonizer().harmonize(
        publication_context="context",
        target={"id": "target-0", "pre_hz_field": "tissue", "pre_hz_label": "lung"},
        strategy="websearch",
    )

    assert calls == [
        "lookup",
        "assign_framework",
        "harmonize_field",
        ("strategy", "websearch"),
    ]


def test_harmonize_routes_failed_lookup_to_strategy_handler() -> None:
    calls = []

    class RecordingHandler:
        def handle(self, target, *, publication_context, ontostore):
            result = {
                "strategy": "websearch",
                "status": "recorded",
                "reason": "recorded strategy call",
            }
            calls.append(
                {
                    "target": target,
                    "publication_context": publication_context,
                    "ontostore": ontostore,
                }
            )
            target["ontology_strategy_result"] = result
            return result

    class RecordingHarmonizer(OntologyHarmonizer):
        STRATEGY_HANDLERS = {"websearch": RecordingHandler}

    store = OntoStore()
    target = {"id": "target-0", "pre_hz_label": "lung"}

    result = RecordingHarmonizer(ontostore=store, llm=FakeLLM()).harmonize(
        publication_context="context",
        target=target,
        strategy="websearch",
    )

    assert result["strategy"] == "websearch"
    assert calls == [
        {
            "target": target,
            "publication_context": "context",
            "ontostore": store,
        }
    ]
    assert target["ontology_strategy_result"] == {
        "strategy": "websearch",
        "status": "recorded",
        "reason": "recorded strategy call",
    }


def test_gemini_grounded_search_client_returns_citation_hits() -> None:
    llm = FakeGroundedLLM()
    client = GeminiGroundedSearchClient(llm=llm)

    hits = client.search("tissue: lung ontology", max_results=25)

    assert hits == [
        {
            "title": "Lung ontology entry",
            "link": "https://example.org/lung",
            "snippet": "Lung maps to UBERON:0002048.",
            "source": "gemini_google_search",
            "provider": "gemini_enterprise",
        }
    ]
    assert client.last_response["text"] == "Lung maps to UBERON:0002048."
    assert client.last_error is None
    assert llm.calls == [
        {
            "prompt": (
                "Search the web for ontology evidence related to this query:\n"
                "tissue: lung ontology\n\n"
                "Return concise evidence for ontology term candidates, including "
                "term labels, IDs, IRIs, and ontology framework names when found."
            ),
            "model": None,
            "config": None,
            "tools": [{"type": "google_search"}],
            "extra_options": {},
        }
    ]


def test_gemini_grounded_search_client_respects_request_budget() -> None:
    llm = FakeGroundedLLM()
    client = GeminiGroundedSearchClient(llm=llm, request_budget=1)

    assert client.search("first query")
    assert client.search("second query") == []
    assert client.last_error == "Google search request budget exhausted."
    assert len(llm.calls) == 1


def test_gemini_grounded_search_client_records_rate_limit_error() -> None:
    llm = FakeGroundedLLM(error=RuntimeError("429 RESOURCE_EXHAUSTED"))
    client = GeminiGroundedSearchClient(llm=llm)

    assert client.search("tissue: lung ontology") == []
    assert client.last_error == "429 RESOURCE_EXHAUSTED"


def test_websearch_strategy_includes_web_search_error_on_fallback() -> None:
    search_client = GeminiGroundedSearchClient(
        llm=FakeGroundedLLM(error=RuntimeError("429 RESOURCE_EXHAUSTED"))
    )
    ols_client = FakeOlsClient(search_results=[[], []])
    target = {
        "id": "target-0",
        "hz_field": "tissue",
        "hz_label": "lung",
        "ontology_id": "uberon",
    }

    result = WebsearchStrategyHandler(
        ols_client=ols_client,
        search_client=search_client,
    ).handle(
        target,
        publication_context=None,
        ontostore=OntoStore(),
    )

    assert result["status"] == "not_harmonized"
    assert result["web_hits"] == []
    assert result["web_search_error"] == "429 RESOURCE_EXHAUSTED"
    assert target["ontology_strategy_result"] == result


def test_websearch_strategy_uses_restricted_ols_hit_without_fallbacks() -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "ontology_name": "uberon",
        "short_form": "UBERON_0002048",
        "obo_id": "UBERON:0002048",
        "label": "lung",
        "description": ["Respiration organ."],
    }
    ols_client = FakeOlsClient(
        search_results=[[term]],
        ontology_metadata={
            "uberon": {
                "config": {
                    "id": "uberon",
                    "title": "Uber-anatomy ontology",
                    "description": "An anatomy ontology.",
                    "version": "2026-06-19",
                    "versionIri": "https://example.org/uberon.owl",
                    "fileLocation": "https://fallback.example.org/uberon.owl",
                }
            }
        },
    )
    search_client = FakeSearchClient(results=[{"title": "unused"}])
    store = OntoStore(
        ontology_frameworks={"uberon": {"url": "https://example.org/old.owl"}}
    )
    target = {
        "id": "target-0",
        "hz_field": "tissue",
        "hz_label": "lung",
        "ontology_id": "uberon",
    }

    result = WebsearchStrategyHandler(
        ols_client=ols_client,
        search_client=search_client,
    ).handle(
        target,
        publication_context="lung sample",
        ontostore=store,
    )

    expected_lookup = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "id": "UBERON_0002048",
        "accession": "UBERON:0002048",
        "title": "lung",
        "description": ["Respiration organ."],
        "ontology_id": "uberon",
        "ontology_prefix": None,
        "type": None,
    }
    assert result == {
        "strategy": "websearch",
        "status": "matched",
        "decision": "UBERON_0002048",
        "confidence": "medium",
        "reason": "Restricted OLS search returned a usable ontology hit.",
        "ols_hits": [expected_lookup],
        "web_hits": [],
        "ontology_framework_config": {
            "id": "uberon",
            "title": "Uber-anatomy ontology",
            "description": "An anatomy ontology.",
            "version": "2026-06-19",
            "url": "https://example.org/uberon.owl",
        },
    }
    assert target["ontology_strategy_result"] == result
    assert target["ontology_lookup"] == expected_lookup
    assert target["ontology_lookup_hits"] == [expected_lookup]
    assert target["ontology_match"] is True
    assert target["ontology_id"] == "uberon"
    assert ols_client.search_calls == [
        {"label": "lung", "ontology_id": "uberon", "rows": 25}
    ]
    assert search_client.calls == []
    assert store.ontology_frameworks["uberon"]["title"] == "Uber-anatomy ontology"
    assert store.ontology_frameworks["uberon"]["version"] == "2026-06-19"
    assert store.ontology_frameworks["uberon"]["url"] == "https://example.org/uberon.owl"


def test_websearch_strategy_falls_back_to_unrestricted_ols_and_web_search() -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/CL_0000000",
        "ontology_name": "cl",
        "ontology_prefix": "CL",
        "short_form": "CL_0000000",
        "obo_id": "CL:0000000",
        "label": "cell",
        "description": ["A cell."],
        "type": "class",
    }
    ols_client = FakeOlsClient(
        search_results=[[], [term]],
        ontology_metadata={
            "cl": {
                "config": {
                    "id": "cl",
                    "title": "Cell Ontology",
                    "description": "An ontology of cell types.",
                    "version": None,
                    "versionIri": "http://purl.obolibrary.org/obo/cl/releases/2026-06-08/cl.owl",
                    "fileLocation": "http://purl.obolibrary.org/obo/cl.owl",
                }
            }
        },
    )
    search_client = FakeSearchClient(results=[{"title": "Cell Ontology page"}])
    store = OntoStore(
        ontology_frameworks={"uberon": {"url": "https://example.org/old.owl"}}
    )
    target = {
        "id": "target-0",
        "hz_field": "cell type",
        "hz_label": "cell",
        "ontology_id": "uberon",
    }

    result = WebsearchStrategyHandler(
        ols_client=ols_client,
        search_client=search_client,
    ).handle(
        target,
        publication_context=None,
        ontostore=store,
    )

    assert result["status"] == "matched"
    assert result["decision"] == "CL_0000000"
    assert result["confidence"] == "medium"
    assert result["web_hits"] == [{"title": "Cell Ontology page"}]
    assert target["ontology_id"] == "cl"
    assert target["ontology_lookup"]["accession"] == "CL:0000000"
    assert ols_client.search_calls == [
        {"label": "cell", "ontology_id": "uberon", "rows": 25},
        {"label": "cell", "ontology_id": None, "rows": 25},
    ]
    assert search_client.calls == [
        {"query": "cell type: cell ontology", "max_results": 25}
    ]
    assert store.ontology_frameworks["cl"]["title"] == "Cell Ontology"
    assert store.ontology_frameworks["cl"]["version"] == "2026-06-08"
    assert store.ontology_frameworks["cl"]["url"] == (
        "http://purl.obolibrary.org/obo/cl/releases/2026-06-08/cl.owl"
    )


def test_websearch_strategy_does_not_harmonize_without_complete_framework_config() -> None:
    term = {
        "iri": "http://purl.obolibrary.org/obo/UBERON_0002048",
        "ontology_name": "uberon",
        "short_form": "UBERON_0002048",
        "obo_id": "UBERON:0002048",
        "label": "lung",
    }
    ols_client = FakeOlsClient(
        search_results=[[term]],
        ontology_metadata={
            "uberon": {
                "config": {
                    "id": "uberon",
                    "title": "Uber-anatomy ontology",
                    "description": "",
                    "version": None,
                    "versionIri": "",
                    "fileLocation": "",
                }
            }
        },
    )
    store = OntoStore(
        ontology_frameworks={"uberon": {"url": "https://example.org/old.owl"}}
    )
    before = dict(store.ontology_frameworks["uberon"])
    target = {"id": "target-0", "hz_label": "lung", "ontology_id": "uberon"}

    result = WebsearchStrategyHandler(ols_client=ols_client).handle(
        target,
        publication_context=None,
        ontostore=store,
    )

    assert result["strategy"] == "websearch"
    assert result["status"] == "not_harmonized"
    assert result["decision"] == "false"
    assert result["confidence"] == "none"
    assert "complete ontology framework metadata" in result["reason"]
    assert result["ols_hits"][0]["id"] == "UBERON_0002048"
    assert result["web_hits"] == []
    assert "ontology_framework_config" not in result
    assert target["ontology_strategy_result"] == result
    assert target["ontology_match"] is False
    assert "ontology_lookup" not in target
    assert store.ontology_frameworks["uberon"] == before


def test_websearch_strategy_returns_not_harmonized_without_assigned_framework() -> None:
    target = {"id": "target-0", "hz_label": "lung"}
    result = WebsearchStrategyHandler().handle(
        target,
        publication_context=None,
        ontostore=OntoStore(),
    )

    assert result == {
        "strategy": "websearch",
        "status": "not_harmonized",
        "decision": "false",
        "confidence": "none",
        "reason": "No assigned ontology framework is available for websearch.",
        "ols_hits": [],
        "web_hits": [],
    }
    assert target["ontology_strategy_result"] == result


def test_rag_placeholder_strategy_handler_mutates_target() -> None:
    target = {"id": "target-rag", "pre_hz_label": "lung"}

    result = OntologyHarmonizer(llm=FakeLLM()).harmonize(
        target=target,
        strategy="rag",
    )

    assert result["strategy"] == "rag"
    assert target["ontology_strategy_result"] == {
        "strategy": "rag",
        "status": "placeholder",
        "decision": "false",
        "confidence": "none",
        "reason": "RAG ontology harmonization is not implemented yet.",
    }


def test_harmonize_default_strategy_routes_to_websearch_handler() -> None:
    target = {"id": "target-websearch", "pre_hz_label": "lung"}

    result = OntologyHarmonizer(llm=FakeLLM()).harmonize(target=target)

    assert result["strategy"] == "websearch"
    assert target["ontology_match"] is False
    assert "ontology_framework_assignment" in target
    assert target["ontology_strategy_result"] == {
        "strategy": "websearch",
        "status": "not_harmonized",
        "decision": "false",
        "confidence": "none",
        "reason": "No assigned ontology framework is available for websearch.",
        "ols_hits": [],
        "web_hits": [],
    }


def test_harmonize_skips_strategy_handler_when_lookup_label_succeeds() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def lookup_label(
            self,
            target,
            *,
            publication_context,
            ontostore,
            strategy,
            lookup_llm_judge=False,
            lookup_llm_threshold=2,
        ):
            target["ontology_match"] = True
            return {"title": "lung"}

        def harmonize_label(
            self,
            target,
            *,
            publication_context,
            ontostore,
            strategy,
        ):
            calls.append(target)

    target = {"id": "target-0", "pre_hz_label": "lung"}

    result = RecordingHarmonizer().harmonize(target=target, strategy="rag")

    assert calls == []
    assert result["strategy"] == "rag"
    assert target["ontology_match"] is True
    assert "ontology_strategy_result" not in target


def test_harmonize_rejects_dict_ontostore_override() -> None:
    with pytest.raises(TypeError, match="OntoStore"):
        OntologyHarmonizer().harmonize(
            harmonization_targets=[],
            ontostore={"anatomy": "UBERON"},
        )


def test_harmonize_rejects_constructor_non_ontostore_without_override() -> None:
    with pytest.raises(TypeError, match="OntoStore"):
        OntologyHarmonizer(ontostore={"anatomy": "UBERON"}).harmonize()


def test_target_extractor_builds_miniml_sample_target_paths() -> None:
    assert HarmonizationTargetExtractor().build_miniml_sample_target_paths(
        miniml_metadata()
    ) == [
        {"path": "/sample/0/channel/0/source", "mode": "field_value"},
        {"path": "/sample/0/channel/0/molecule", "mode": "field_value"},
        {"path": "/sample/0/channel/0/organism", "mode": "container_value"},
        {"path": "/sample/0/channel/0/characteristics", "mode": "tag_value"},
        {"path": "/sample/1/channel/0/source", "mode": "field_value"},
        {"path": "/sample/1/channel/0/molecule", "mode": "field_value"},
        {"path": "/sample/1/channel/0/organism", "mode": "container_value"},
        {"path": "/sample/1/channel/0/characteristics", "mode": "tag_value"},
    ]


def test_target_extractor_builds_miniml_sample_target_paths_from_package_list() -> None:
    assert HarmonizationTargetExtractor().build_miniml_sample_target_paths(
        [miniml_metadata()]
    )[:4] == [
        {"path": "/0/sample/0/channel/0/source", "mode": "field_value"},
        {"path": "/0/sample/0/channel/0/molecule", "mode": "field_value"},
        {"path": "/0/sample/0/channel/0/organism", "mode": "container_value"},
        {"path": "/0/sample/0/channel/0/characteristics", "mode": "tag_value"},
    ]


def test_target_extractor_dedupes_field_label_pairs_with_occurrences() -> None:
    targets = [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample/0/channel/0/characteristics/0/tag",
            "pre_hz_label_path": "/sample/0/channel/0/characteristics/0/value",
            "parent_path": "/sample/0/channel/0/characteristics/0",
            "hz_field": "tissue",
            "hz_label": "lung",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample/1/channel/0/characteristics/0/tag",
            "pre_hz_label_path": "/sample/1/channel/0/characteristics/0/value",
            "parent_path": "/sample/1/channel/0/characteristics/0",
            "hz_field": "tissue",
            "hz_label": "lung",
        },
        {
            "id": "target-2",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "heart",
            "pre_hz_field_path": "/sample/2/channel/0/characteristics/0/tag",
            "pre_hz_label_path": "/sample/2/channel/0/characteristics/0/value",
            "parent_path": "/sample/2/channel/0/characteristics/0",
            "hz_field": "tissue",
            "hz_label": "heart",
        },
    ]

    assert HarmonizationTargetExtractor().dedupe_targets(targets) == [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "hz_field": "tissue",
            "hz_label": "lung",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/0/channel/0/characteristics/0/tag",
                    "pre_hz_label_path": "/sample/0/channel/0/characteristics/0/value",
                    "parent_path": "/sample/0/channel/0/characteristics/0",
                    "hz_field": "tissue",
                    "hz_label": "lung",
                },
                {
                    "pre_hz_field_path": "/sample/1/channel/0/characteristics/0/tag",
                    "pre_hz_label_path": "/sample/1/channel/0/characteristics/0/value",
                    "parent_path": "/sample/1/channel/0/characteristics/0",
                    "hz_field": "tissue",
                    "hz_label": "lung",
                },
            ],
        },
        {
            "id": "target-1",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "heart",
            "hz_field": "tissue",
            "hz_label": "heart",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/2/channel/0/characteristics/0/tag",
                    "pre_hz_label_path": "/sample/2/channel/0/characteristics/0/value",
                    "parent_path": "/sample/2/channel/0/characteristics/0",
                    "hz_field": "tissue",
                    "hz_label": "heart",
                }
            ],
        },
    ]


def test_target_extractor_schema_excludes_old_target_keys() -> None:
    targets = HarmonizationTargetExtractor().dedupe_targets(
        HarmonizationTargetExtractor().extract({"sample": {"tissue": "lung"}})
    )

    assert targets
    old_keys = {"field", "label", "field_path", "label_path", "key", "value"}
    top_level_path_keys = {"pre_hz_field_path", "pre_hz_label_path", "parent_path"}
    occurrence_path_keys = {
        "pre_hz_field_path",
        "pre_hz_label_path",
        "parent_path",
    }
    assert old_keys.isdisjoint(targets[0])
    assert old_keys.isdisjoint(targets[0]["occurrences"][0])
    assert top_level_path_keys.isdisjoint(targets[0])
    assert occurrence_path_keys.issubset(targets[0]["occurrences"][0])


def test_apply_targets_adds_scalar_field_alternatives() -> None:
    miniml_json = {"sample": [{"channel": [{"source": "lung"}]}]}
    targets = [
        {
            "id": "target-0",
            "hz_field": "sample_source",
            "hz_label": "lung tissue",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/0/channel/0/source",
                    "pre_hz_label_path": "/sample/0/channel/0/source",
                    "parent_path": "/sample/0/channel/0",
                }
            ],
        }
    ]

    result = OntologyHarmonizer().apply_targets(miniml_json, targets)

    assert result is miniml_json
    assert miniml_json["sample"][0]["channel"][0]["source"] == "lung"
    assert miniml_json["sample"][0]["channel"][0]["source_hz_alternatives"] == [
        {
            "hz_field": "sample_source",
            "hz_label": "lung tissue",
            "target_id": "target-0",
        }
    ]


def test_apply_targets_adds_tag_value_object_alternatives() -> None:
    miniml_json = {
        "sample": [
            {
                "channel": [
                    {
                        "characteristics": [
                            {"tag": "disease state", "value": "Normal"}
                        ]
                    }
                ]
            }
        ]
    }
    targets = [
        {
            "id": "target-0",
            "hz_field": "disease_state",
            "hz_label": "normal",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/0/channel/0/characteristics/0/tag",
                    "pre_hz_label_path": "/sample/0/channel/0/characteristics/0/value",
                    "parent_path": "/sample/0/channel/0/characteristics/0",
                }
            ],
        }
    ]

    OntologyHarmonizer().apply_targets(miniml_json, targets)

    characteristic = miniml_json["sample"][0]["channel"][0]["characteristics"][0]
    assert characteristic["hz_field"] == "disease_state"
    assert characteristic["hz_label"] == "normal"
    assert characteristic["hz_alternatives"] == [
        {
            "hz_field": "disease_state",
            "hz_label": "normal",
            "target_id": "target-0",
        }
    ]


def test_apply_targets_adds_container_value_object_alternatives() -> None:
    miniml_json = {
        "sample": [
            {
                "channel": [
                    {"organism": [{"taxid": "9606", "value": "Homo sapiens"}]}
                ]
            }
        ]
    }
    targets = [
        {
            "id": "target-0",
            "hz_field": "organism",
            "hz_label": "homo_sapiens",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/0/channel/0/organism",
                    "pre_hz_label_path": "/sample/0/channel/0/organism/0/value",
                    "parent_path": "/sample/0/channel/0/organism/0",
                }
            ],
        }
    ]

    OntologyHarmonizer().apply_targets(miniml_json, targets)

    organism = miniml_json["sample"][0]["channel"][0]["organism"][0]
    assert organism["hz_field"] == "organism"
    assert organism["hz_label"] == "homo_sapiens"
    assert organism["hz_alternatives"] == [
        {
            "hz_field": "organism",
            "hz_label": "homo_sapiens",
            "target_id": "target-0",
        }
    ]


def test_apply_targets_appends_colliding_scalar_alternatives_without_duplicates() -> None:
    miniml_json = {"sample": {"tissue": "lung"}}
    targets = [
        {
            "id": "target-0",
            "hz_field": "tissue",
            "hz_label": "lung",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/tissue",
                    "pre_hz_label_path": "/sample/tissue",
                    "parent_path": "/sample",
                }
            ],
        },
        {
            "id": "target-1",
            "hz_field": "anatomical_structure",
            "hz_label": "lung",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/tissue",
                    "pre_hz_label_path": "/sample/tissue",
                    "parent_path": "/sample",
                }
            ],
        },
        {
            "id": "target-1",
            "hz_field": "anatomical_structure",
            "hz_label": "lung",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/tissue",
                    "pre_hz_label_path": "/sample/tissue",
                    "parent_path": "/sample",
                }
            ],
        },
    ]

    OntologyHarmonizer().apply_targets(miniml_json, targets)

    assert miniml_json["sample"]["tissue_hz_alternatives"] == [
        {"hz_field": "tissue", "hz_label": "lung", "target_id": "target-0"},
        {
            "hz_field": "anatomical_structure",
            "hz_label": "lung",
            "target_id": "target-1",
        },
    ]


def test_apply_targets_applies_deduped_target_to_all_occurrences() -> None:
    miniml_json = {
        "sample": [
            {"channel": [{"source": "lung"}]},
            {"channel": [{"source": "lung"}]},
        ]
    }
    targets = [
        {
            "id": "target-0",
            "hz_field": "sample_source",
            "hz_label": "lung",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample/0/channel/0/source",
                    "pre_hz_label_path": "/sample/0/channel/0/source",
                    "parent_path": "/sample/0/channel/0",
                },
                {
                    "pre_hz_field_path": "/sample/1/channel/0/source",
                    "pre_hz_label_path": "/sample/1/channel/0/source",
                    "parent_path": "/sample/1/channel/0",
                },
            ],
        }
    ]

    OntologyHarmonizer().apply_targets(miniml_json, targets)

    assert miniml_json["sample"][0]["channel"][0]["source_hz_alternatives"] == [
        {"hz_field": "sample_source", "hz_label": "lung", "target_id": "target-0"}
    ]
    assert miniml_json["sample"][1]["channel"][0]["source_hz_alternatives"] == [
        {"hz_field": "sample_source", "hz_label": "lung", "target_id": "target-0"}
    ]


def test_apply_targets_resolves_escaped_paths_and_skips_missing_paths() -> None:
    miniml_json = {"sample/type": {"label~name": "lung"}}
    targets = [
        {
            "id": "target-0",
            "hz_field": "label_name",
            "hz_label": "lung",
            "occurrences": [
                {
                    "pre_hz_field_path": "/sample~1type/label~0name",
                    "pre_hz_label_path": "/sample~1type/label~0name",
                    "parent_path": "/sample~1type",
                },
                {
                    "pre_hz_field_path": "/sample~1type/missing",
                    "pre_hz_label_path": "/sample~1type/missing",
                    "parent_path": "/sample~1type",
                },
            ],
        }
    ]

    OntologyHarmonizer().apply_targets(miniml_json, targets)

    assert miniml_json["sample/type"]["label~name_hz_alternatives"] == [
        {"hz_field": "label_name", "hz_label": "lung", "target_id": "target-0"}
    ]
    assert "missing_hz_alternatives" not in miniml_json["sample/type"]


def test_harmonize_miniml_json_extracts_default_targets() -> None:
    miniml_json = miniml_metadata()
    result = OntologyHarmonizer(llm=FakeLLM()).harmonize_miniml_json(
        publication_context="Full publication context",
        miniml_json=miniml_json,
    )

    assert result["publication_context"] == "Full publication context"
    assert result["miniml_json"] is miniml_json
    assert result["target_paths"] == [
        {"path": "/sample/0/channel/0/source", "mode": "field_value"},
        {"path": "/sample/0/channel/0/molecule", "mode": "field_value"},
        {"path": "/sample/0/channel/0/organism", "mode": "container_value"},
        {"path": "/sample/0/channel/0/characteristics", "mode": "tag_value"},
        {"path": "/sample/1/channel/0/source", "mode": "field_value"},
        {"path": "/sample/1/channel/0/molecule", "mode": "field_value"},
        {"path": "/sample/1/channel/0/organism", "mode": "container_value"},
        {"path": "/sample/1/channel/0/characteristics", "mode": "tag_value"},
    ]
    assert [target["pre_hz_field"] for target in result["harmonization_targets"]] == [
        "source",
        "molecule",
        "organism",
        "disease state",
        "tissue",
        "disease state",
    ]
    assert [target["pre_hz_label"] for target in result["harmonization_targets"]] == [
        "Oral buccal mucosa",
        "total RNA",
        "Homo sapiens",
        "Normal",
        "Oral buccal mucosa",
        "Disease",
    ]
    assert [target["id"] for target in result["harmonization_targets"]] == [
        "target-0",
        "target-1",
        "target-2",
        "target-3",
        "target-4",
        "target-5",
    ]
    by_pre_hz_field_label = {
        (target["pre_hz_field"], target["pre_hz_label"]): target
        for target in result["harmonization_targets"]
    }
    assert len(by_pre_hz_field_label[("source", "Oral buccal mucosa")]["occurrences"]) == 2
    assert len(by_pre_hz_field_label[("molecule", "total RNA")]["occurrences"]) == 2
    assert len(by_pre_hz_field_label[("organism", "Homo sapiens")]["occurrences"]) == 2
    assert len(by_pre_hz_field_label[("tissue", "Oral buccal mucosa")]["occurrences"]) == 2
    assert ("position", "1") not in by_pre_hz_field_label
    assert ("extract_protocol", "Long protocol text is not a target.") not in by_pre_hz_field_label
    first_channel = miniml_json["sample"][0]["channel"][0]
    assert first_channel["source_hz_alternatives"] == [
        {"hz_field": "source", "hz_label": "oral_buccal_mucosa", "target_id": "target-0"}
    ]
    assert first_channel["molecule_hz_alternatives"] == [
        {"hz_field": "molecule", "hz_label": "total_rna", "target_id": "target-1"}
    ]
    assert first_channel["organism"][0]["hz_alternatives"] == [
        {"hz_field": "organism", "hz_label": "homo_sapiens", "target_id": "target-2"}
    ]
    assert first_channel["characteristics"][0]["hz_alternatives"] == [
        {"hz_field": "disease_state", "hz_label": "normal", "target_id": "target-3"}
    ]
    assert first_channel["characteristics"][1]["hz_alternatives"] == [
        {"hz_field": "tissue", "hz_label": "oral_buccal_mucosa", "target_id": "target-4"}
    ]


def test_harmonize_miniml_json_accepts_explicit_target_paths() -> None:
    miniml_json = {"sample": {"tissue": "lung"}}
    result = OntologyHarmonizer(llm=FakeLLM()).harmonize_miniml_json(
        miniml_json=miniml_json,
        target_paths=["/sample"],
    )

    assert result == {
        "publication_context": None,
        "harmonization_targets": [
            {
                "id": "target-0",
                "source": "metadata",
                "pre_hz_field": "tissue",
                "pre_hz_label": "lung",
                "pre_hz_field_path": "/sample/tissue",
                "pre_hz_label_path": "/sample/tissue",
                "parent_path": "/sample",
                "hz_field": "tissue",
                "hz_label": "lung",
                "ontology_match": False,
                    "ontology_framework_assignment": {
                        "decision": "unsure",
                        "confidence": "low",
                        "reason": "No clear framework match.",
                    },
                    "field_assignment": {
                        "decision": "tissue",
                        "confidence": "low",
                        "reason": "No clear field match.",
                        "new_field": True,
                    },
                    "ontology_strategy_result": {
                        "strategy": "websearch",
                        "status": "not_harmonized",
                        "decision": "false",
                        "confidence": "none",
                        "reason": (
                            "No assigned ontology framework is available for "
                            "websearch."
                        ),
                        "ols_hits": [],
                        "web_hits": [],
                    },
                }
            ],
        "strategy": "websearch",
        "target_paths": ["/sample"],
        "miniml_json": {
            "sample": {
                "tissue": "lung",
                "tissue_hz_alternatives": [
                    {
                        "hz_field": "tissue",
                        "hz_label": "lung",
                        "target_id": "target-0",
                    }
                ],
            }
        },
    }
    assert result["miniml_json"] is miniml_json


def test_harmonize_miniml_json_delegates_to_harmonize() -> None:
    calls = []

    class RecordingHarmonizer(OntologyHarmonizer):
        def harmonize(
            self,
            publication_context=None,
            harmonization_targets=None,
            target=None,
            strategy="websearch",
            ontostore=None,
            target_paths=None,
            lookup_llm_judge=False,
            lookup_llm_threshold=2,
            llm=True,
        ):
            calls.append(
                {
                    "publication_context": publication_context,
                    "harmonization_targets": harmonization_targets,
                    "target": target,
                    "strategy": strategy,
                    "ontostore": ontostore,
                    "target_paths": target_paths,
                    "lookup_llm_judge": lookup_llm_judge,
                    "lookup_llm_threshold": lookup_llm_threshold,
                    "llm": llm,
                }
            )
            return {
                "delegated": True,
                "harmonization_targets": harmonization_targets,
            }

    store = OntoStore()
    miniml_json = {"sample": {"tissue": "lung"}}
    result = RecordingHarmonizer().harmonize_miniml_json(
        publication_context="context",
        miniml_json=miniml_json,
        ontostore=store,
        target_paths=["/sample"],
    )

    assert result == {
        "delegated": True,
        "harmonization_targets": [
            {
                "id": "target-0",
                "source": "metadata",
                "pre_hz_field": "tissue",
                "pre_hz_label": "lung",
                "pre_hz_field_path": "/sample/tissue",
                "pre_hz_label_path": "/sample/tissue",
                "parent_path": "/sample",
                "hz_field": "tissue",
                "hz_label": "lung",
            }
        ],
        "miniml_json": {
            "sample": {
                "tissue": "lung",
                "tissue_hz_alternatives": [
                    {
                        "hz_field": "tissue",
                        "hz_label": "lung",
                        "target_id": "target-0",
                    }
                ],
            }
        },
    }
    assert result["miniml_json"] is miniml_json
    assert calls == [
        {
            "publication_context": "context",
            "harmonization_targets": [
                {
                    "id": "target-0",
                    "source": "metadata",
                    "pre_hz_field": "tissue",
                    "pre_hz_label": "lung",
                    "pre_hz_field_path": "/sample/tissue",
                    "pre_hz_label_path": "/sample/tissue",
                    "parent_path": "/sample",
                    "hz_field": "tissue",
                    "hz_label": "lung",
                }
            ],
            "target": None,
            "strategy": "websearch",
            "ontostore": store,
            "target_paths": ["/sample"],
            "lookup_llm_judge": False,
            "lookup_llm_threshold": 2,
            "llm": True,
        }
    ]


def test_extract_harmonization_targets_from_flat_metadata() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"organism": "human", "age": 42, "diseased": True, "missing": None}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "organism",
            "pre_hz_label": "human",
            "pre_hz_field_path": "/organism",
            "pre_hz_label_path": "/organism",
            "parent_path": "",
            "hz_field": "organism",
            "hz_label": "human",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "pre_hz_field": "age",
            "pre_hz_label": "42",
            "pre_hz_field_path": "/age",
            "pre_hz_label_path": "/age",
            "parent_path": "",
            "hz_field": "age",
            "hz_label": 42,
        },
        {
            "id": "target-2",
            "source": "metadata",
            "pre_hz_field": "diseased",
            "pre_hz_label": "True",
            "pre_hz_field_path": "/diseased",
            "pre_hz_label_path": "/diseased",
            "parent_path": "",
            "hz_field": "diseased",
            "hz_label": True,
        },
    ]


def test_target_extractor_extracts_flat_metadata() -> None:
    assert HarmonizationTargetExtractor().extract(
        {"organism": "human", "missing": None}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "organism",
            "pre_hz_label": "human",
            "pre_hz_field_path": "/organism",
            "pre_hz_label_path": "/organism",
            "parent_path": "",
            "hz_field": "organism",
            "hz_label": "human",
        }
    ]


def test_extract_harmonization_targets_from_nested_metadata() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"sample": {"tissue": "lung"}}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample/tissue",
            "pre_hz_label_path": "/sample/tissue",
            "parent_path": "/sample",
            "hz_field": "tissue",
            "hz_label": "lung",
        }
    ]


def test_extract_harmonization_targets_from_list_of_dicts() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"samples": [{"tissue": "lung"}, {"tissue": "heart"}]}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/samples/0/tissue",
            "pre_hz_label_path": "/samples/0/tissue",
            "parent_path": "/samples/0",
            "hz_field": "tissue",
            "hz_label": "lung",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "heart",
            "pre_hz_field_path": "/samples/1/tissue",
            "pre_hz_label_path": "/samples/1/tissue",
            "parent_path": "/samples/1",
            "hz_field": "tissue",
            "hz_label": "heart",
        },
    ]


def test_extract_harmonization_targets_escapes_json_pointer_segments() -> None:
    assert OntologyHarmonizer()._extract_harmonization_targets(
        {"sample/type": {"label~name": "lung"}}
    ) == [
        {
            "id": "target-0",
            "source": "metadata",
            "pre_hz_field": "label~name",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample~1type/label~0name",
            "pre_hz_label_path": "/sample~1type/label~0name",
            "parent_path": "/sample~1type",
            "hz_field": "label~name",
            "hz_label": "lung",
        }
    ]


def test_extract_harmonization_targets_skips_uneditable_metadata() -> None:
    harmonizer = OntologyHarmonizer()

    assert harmonizer._extract_harmonization_targets(None) == []
    assert harmonizer._extract_harmonization_targets("raw metadata") == []
    assert harmonizer._extract_harmonization_targets(["lung", "heart"]) == []
    assert harmonizer._extract_harmonization_targets({"samples": []}) == []


def test_harmonize_accepts_target_paths() -> None:
    result = OntologyHarmonizer().harmonize(
        harmonization_targets=[],
        target_paths=[],
    )

    assert result == {
        "publication_context": None,
        "harmonization_targets": [],
        "strategy": "websearch",
        "target_paths": [],
    }


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
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample/tissue",
            "pre_hz_label_path": "/sample/tissue",
            "parent_path": "/sample",
            "hz_field": "tissue",
            "hz_label": "lung",
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
            "pre_hz_field": "tissue",
            "pre_hz_label": "heart",
            "pre_hz_field_path": "/samples/1/tissue",
            "pre_hz_label_path": "/samples/1/tissue",
            "parent_path": "/samples/1",
            "hz_field": "tissue",
            "hz_label": "heart",
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
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample/tissue",
            "pre_hz_label_path": "/sample/tissue",
            "parent_path": "/sample",
            "hz_field": "tissue",
            "hz_label": "lung",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "pre_hz_field": "organism",
            "pre_hz_label": "human",
            "pre_hz_field_path": "/publication/organism",
            "pre_hz_label_path": "/publication/organism",
            "parent_path": "/publication",
            "hz_field": "organism",
            "hz_label": "human",
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
            "pre_hz_field": "label~name",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample~1type/label~0name",
            "pre_hz_label_path": "/sample~1type/label~0name",
            "parent_path": "/sample~1type",
            "hz_field": "label~name",
            "hz_label": "lung",
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
            "pre_hz_field": "disease state",
            "pre_hz_label": "Normal Oral mucosa",
            "pre_hz_field_path": "/characteristics/0/tag",
            "pre_hz_label_path": "/characteristics/0/value",
            "parent_path": "/characteristics/0",
            "hz_field": "disease state",
            "hz_label": "Normal Oral mucosa",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "pre_hz_field": "tissue",
            "pre_hz_label": "Oral buccal mucosa",
            "pre_hz_field_path": "/characteristics/1/tag",
            "pre_hz_label_path": "/characteristics/1/value",
            "parent_path": "/characteristics/1",
            "hz_field": "tissue",
            "hz_label": "Oral buccal mucosa",
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
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/characteristics/0/tag",
            "pre_hz_label_path": "/characteristics/0/value",
            "parent_path": "/characteristics/0",
            "hz_field": "tissue",
            "hz_label": "lung",
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
            "pre_hz_field": "organism",
            "pre_hz_label": "Homo sapiens",
            "pre_hz_field_path": "/organism",
            "pre_hz_label_path": "/organism/0/value",
            "parent_path": "/organism/0",
            "hz_field": "organism",
            "hz_label": "Homo sapiens",
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
            "pre_hz_field": "tissue",
            "pre_hz_label": "Oral buccal mucosa",
            "pre_hz_field_path": "/characteristics/0/tag",
            "pre_hz_label_path": "/characteristics/0/value",
            "parent_path": "/characteristics/0",
            "hz_field": "tissue",
            "hz_label": "Oral buccal mucosa",
        },
        {
            "id": "target-1",
            "source": "metadata",
            "pre_hz_field": "organism",
            "pre_hz_label": "Homo sapiens",
            "pre_hz_field_path": "/organism",
            "pre_hz_label_path": "/organism/0/value",
            "parent_path": "/organism/0",
            "hz_field": "organism",
            "hz_label": "Homo sapiens",
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
            "pre_hz_field": "tissue",
            "pre_hz_label": "lung",
            "pre_hz_field_path": "/sample/tissue",
            "pre_hz_label_path": "/sample/tissue",
            "parent_path": "/sample",
            "hz_field": "tissue",
            "hz_label": "lung",
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
