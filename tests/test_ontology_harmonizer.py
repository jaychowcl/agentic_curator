from agentic_curator import OntologyHarmonizer as RootOntologyHarmonizer
from agentic_curator.curators import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import (
    OntologyHarmonizer as SubpackageOntologyHarmonizer,
)


def test_ontology_harmonizer_can_be_imported_from_subpackage() -> None:
    assert SubpackageOntologyHarmonizer is OntologyHarmonizer


def test_ontology_harmonizer_is_exported_from_package_root() -> None:
    assert RootOntologyHarmonizer is OntologyHarmonizer


def test_harmonize_returns_placeholder_envelope_with_supplied_inputs() -> None:
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

    assert result == {
        "status": "placeholder",
        "publication_text": "Full publication text",
        "metadata": metadata,
        "title": "Fibrosis atlas publication",
        "ontology_frameworks": ontology_frameworks,
        "matches": [],
        "targets": [
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
            },
            {
                "id": "target-1",
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
                "id": "target-2",
                "source": "metadata",
                "field": "tissue",
                "label": "lung",
                "field_path": "/characteristics/1/tag",
                "label_path": "/characteristics/1/value",
                "parent_path": "/characteristics/1",
                "key": "tissue",
                "value": "lung",
            },
        ],
    }


def test_harmonize_defaults_to_empty_placeholder_values() -> None:
    result = OntologyHarmonizer().harmonize()

    assert result == {
        "status": "placeholder",
        "publication_text": None,
        "metadata": None,
        "title": None,
        "ontology_frameworks": {},
        "matches": [],
        "targets": [],
    }


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


def test_harmonize_includes_extracted_harmonization_targets() -> None:
    harmonizer = OntologyHarmonizer()
    metadata = {
        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
        "characteristics": [{"tag": "tissue", "value": "lung"}],
    }

    result = harmonizer.harmonize(metadata=metadata)

    assert result["targets"] == harmonizer._extract_harmonization_targets(
        metadata,
        start_paths=harmonizer.DEFAULT_TARGET_PATHS,
    )


def test_harmonize_target_paths_override_default_paths() -> None:
    metadata = {
        "sample": {"tissue": "lung"},
        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
        "characteristics": [{"tag": "disease state", "value": "normal"}],
    }

    result = OntologyHarmonizer().harmonize(
        metadata=metadata,
        target_paths=["/sample"],
    )

    assert result["targets"] == [
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


def test_harmonize_empty_target_paths_returns_no_targets() -> None:
    metadata = {
        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
        "characteristics": [{"tag": "tissue", "value": "lung"}],
    }

    result = OntologyHarmonizer().harmonize(
        metadata=metadata,
        target_paths=[],
    )

    assert result["targets"] == []


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
