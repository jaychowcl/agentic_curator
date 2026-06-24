from pathlib import Path

import pytest

from agentic_curator import OntologyHarmonizer as RootOntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import ontology_store
from agentic_curator.curators import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import (
    OntoStore,
    OntologyHarmonizer as SubpackageOntologyHarmonizer,
)


class FakeResponse:
    def __init__(self, content: bytes = b"ontology", error: Exception | None = None):
        self.content = content
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error


def test_ontology_harmonizer_can_be_imported_from_subpackage() -> None:
    assert SubpackageOntologyHarmonizer is OntologyHarmonizer


def test_ontology_harmonizer_is_exported_from_package_root() -> None:
    assert RootOntologyHarmonizer is OntologyHarmonizer


def test_ontostore_can_be_imported_from_subpackage() -> None:
    assert OntoStore.__name__ == "OntoStore"


def test_ontostore_initializes_with_empty_frameworks(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    assert store.ontology_frameworks == {}
    assert store.storage_dir == tmp_path


def test_ontostore_accepts_constructor_frameworks(tmp_path: Path) -> None:
    ontology_frameworks = {"CL": {"url": "https://example.org/cl.owl"}}

    store = OntoStore(
        ontology_frameworks=ontology_frameworks,
        storage_dir=tmp_path,
    )

    assert store.ontology_frameworks == ontology_frameworks


def test_add_url_adds_single_framework_url(tmp_path: Path) -> None:
    store = OntoStore(storage_dir=tmp_path)

    store.add_url("CL", "https://example.org/cl.owl")

    assert store.ontology_frameworks == {
        "CL": {"url": "https://example.org/cl.owl"}
    }


def test_add_urls_merges_frameworks(tmp_path: Path) -> None:
    store = OntoStore(
        ontology_frameworks={"CL": {"url": "https://example.org/cl.owl"}},
        storage_dir=tmp_path,
    )

    store.add_urls({"UBERON": {"url": "https://example.org/uberon.owl"}})

    assert store.ontology_frameworks == {
        "CL": {"url": "https://example.org/cl.owl"},
        "UBERON": {"url": "https://example.org/uberon.owl"},
    }


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


def test_harmonize_returns_metadata_only() -> None:
    metadata = {
        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
        "characteristics": [
            {"tag": "disease state", "value": "Normal Oral mucosa"},
            {"tag": "tissue", "value": "lung"},
        ],
    }
    ontology_frameworks = {
        "anatomy": "UBERON",
        "cell_type": "CL",
    }

    result = OntologyHarmonizer().harmonize(
        publication_text="Full publication text",
        metadata=metadata,
        title="Fibrosis atlas publication",
        ontology_frameworks=ontology_frameworks,
    )

    assert result == {"metadata": metadata}


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
