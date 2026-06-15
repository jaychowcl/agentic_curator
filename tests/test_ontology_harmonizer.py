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
    metadata = {"organism": "human", "tissue": "lung"}
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
                "field": "tissue",
                "label": "lung",
                "field_path": "/tissue",
                "label_path": "/tissue",
                "parent_path": "",
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
    metadata = {"sample": {"tissue": "lung"}}

    result = harmonizer.harmonize(metadata=metadata)

    assert result["targets"] == harmonizer._extract_harmonization_targets(metadata)
