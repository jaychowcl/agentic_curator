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
    terms = ["lung fibrosis", "fibroblast"]
    context = {"organism": "human", "tissue": "lung"}

    result = OntologyHarmonizer().harmonize(
        terms=terms,
        ontology="UBERON",
        context=context,
    )

    assert result == {
        "status": "placeholder",
        "terms": terms,
        "ontology": "UBERON",
        "context": context,
        "matches": [],
    }


def test_harmonize_defaults_to_empty_placeholder_values() -> None:
    result = OntologyHarmonizer().harmonize()

    assert result == {
        "status": "placeholder",
        "terms": [],
        "ontology": None,
        "context": None,
        "matches": [],
    }
