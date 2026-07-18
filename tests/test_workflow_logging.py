# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

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
        return '''{"accession_assessments": [{
            "accession": "GSE1",
            "human_samples": {"status": "meets", "evidence": "human"},
            "transcriptomics_assay": {"status": "meets", "evidence": "RNA-seq"},
            "established_fibrosis": {"status": "meets", "evidence": "fibrosis"},
            "accession_linkage": {"status": "meets", "evidence": "GSE1"},
            "confidence": "high",
            "reason": "All criteria meet."
        }]}'''


def test_thematic_reviewer_logs_orchestrator_steps(caplog) -> None:
    reviewer = ThematicReviewer(llm=StaticReviewerLlm())

    with caplog.at_level(logging.INFO):
        reviewer.review_relevancy(
            publication_text="Text", theme="fibrosis", accessions=["GSE1"]
        )

    messages = [record.getMessage() for record in caplog.records]
    assert "Starting thematic relevance review strategy=direct." in messages
    assert (
        "Completed thematic relevance review strategy=direct judgement=relevant "
        "accession_rejections=0."
    ) in messages


def test_ontology_harmonizer_logs_target_workflow(caplog) -> None:
    class NoNetworkOntologyHarmonizer(OntologyHarmonizer):
        def harmonize_label(
            self,
            target,
            *,
            publication_context,
            ontostore,
            strategy,
            search_llm_judge=True,
        ):
            return {"strategy": strategy, "status": "not_harmonized"}

    store = OntoStore(ontology_frameworks={}, fields={"organism": {"label": "organism"}})
    harmonizer = NoNetworkOntologyHarmonizer(ontostore=store)

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
    assert (
        "Completed ontology harmonization. targets=1 matched=0 unmatched=1 "
        "strategy=websearch."
    ) in messages


def test_ontostore_logs_field_lookup(caplog) -> None:
    store = OntoStore(ontology_frameworks={}, fields={"organism": {"label": "Organism"}})

    with caplog.at_level(logging.INFO):
        store.lookup_fields("organism")

    messages = [record.getMessage() for record in caplog.records]
    assert "Looking up ontology field." in messages
    assert "Ontology field lookup matched organism." in messages
