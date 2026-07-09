import logging

from agentic_curator.curators.ontology_harmonizer import OntoStore
from agentic_curator.curators.ontology_harmonizer.harmonizer import OntologyHarmonizer
from agentic_curator.curators.thematic_reviewer.reviewer import ThematicReviewer


class StaticReviewerLlm:
    def generate_response(self, prompt, *, config=None):
        schema = (config or {}).get("response_schema", {})
        required = schema.get("required", [])
        if "evidences" in required:
            return '{"evidences": []}'
        return '{"judgement": "relevant", "reasoning": "ok", "confidence": "high"}'


def test_thematic_reviewer_logs_orchestrator_steps(caplog) -> None:
    reviewer = ThematicReviewer(llm=StaticReviewerLlm())

    with caplog.at_level(logging.INFO):
        reviewer.review_relevancy(publication_text="Text", theme="fibrosis")

    messages = [record.getMessage() for record in caplog.records]
    assert "Starting thematic relevance review." in messages
    assert "Completed thematic relevance review." in messages


def test_ontology_harmonizer_logs_target_workflow(caplog) -> None:
    store = OntoStore(ontology_frameworks={}, fields={"organism": {"label": "organism"}})
    harmonizer = OntologyHarmonizer(ontostore=store)

    with caplog.at_level(logging.INFO):
        harmonizer.harmonize(
            target={
                "id": "target-1",
                "pre_hz_field": "Organism",
                "pre_hz_label": "lung",
            },
            llm=False,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert "Starting ontology harmonization." in messages
    assert "Ontology lookup missed for target target-1." in messages
    assert "Completed ontology harmonization." in messages


def test_ontostore_logs_field_lookup(caplog) -> None:
    store = OntoStore(ontology_frameworks={}, fields={"organism": {"label": "Organism"}})

    with caplog.at_level(logging.INFO):
        store.lookup_fields("organism")

    messages = [record.getMessage() for record in caplog.records]
    assert "Looking up ontology field." in messages
    assert "Ontology field lookup matched organism." in messages
