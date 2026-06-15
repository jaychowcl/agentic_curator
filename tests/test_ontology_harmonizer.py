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
    }
