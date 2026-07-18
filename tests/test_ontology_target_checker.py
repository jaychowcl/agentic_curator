# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore


class SequencedLLM:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_response(self, prompt, *, model=None, config=None, **kwargs):
        self.calls.append({"prompt": prompt, "model": model, "config": config})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class PassthroughHarmonizer(OntologyHarmonizer):
    def harmonize(
        self,
        publication_context=None,
        metadata_context=None,
        harmonization_targets=None,
        target=None,
        ontostore=None,
        target_paths=None,
        lookup_llm_judge=True,
        search_llm_judge=True,
        llm=True,
    ):
        self.received_targets = harmonization_targets
        return {
            "publication_context": publication_context,
            "metadata_context": metadata_context,
            "harmonization_targets": harmonization_targets,
            "workflow": self.WORKFLOW,
            "target_paths": target_paths,
        }


class ApplyingHarmonizer(PassthroughHarmonizer):
    def harmonize(self, **kwargs):
        targets = kwargs["harmonization_targets"]
        for target in targets:
            if target["source"] == "target_checker":
                target["hz_field"] = "tissue"
                target["hz_label"] = "lung"
            else:
                target["hz_field"] = "disease"
                target["hz_label"] = "idiopathic pulmonary fibrosis"
        return super().harmonize(**kwargs)


def compound_miniml() -> list[dict]:
    return [
        {
            "series": {"title": "IPF spatial transcriptomics"},
            "sample": [
                {
                    "channel": [
                        {
                            "source": "IPF lung",
                            "characteristics": [
                                {"tag": "tissue", "value": "IPF lung"}
                            ],
                        }
                    ]
                }
            ],
        }
    ]


def addition(source_target_id: str, **overrides) -> dict:
    value = {
        "source_target_id": source_target_id,
        "label": "lung",
        "field_hint": "tissue",
        "confidence": "high",
        "reason": "The compound label contains a distinct anatomical concept.",
    }
    value.update(overrides)
    return value


def test_target_checker_batches_originals_and_merges_equivalent_additions(
    tmp_path: Path,
) -> None:
    llm = SequencedLLM(
        [
            {
                "additions": [
                    addition("target-0"),
                    addition("target-1", reason="The tissue value includes lung."),
                ]
            }
        ]
    )
    miniml_json = compound_miniml()
    original_json = deepcopy(miniml_json)
    harmonizer = PassthroughHarmonizer(
        llm=llm,
        ontostore=OntoStore(
            fields={
                "tissue": {
                    "label": "Tissue",
                    "description": "Anatomical source tissue.",
                }
            },
            storage_dir=tmp_path,
        ),
    )

    result = harmonizer.harmonize_miniml_json(
        publication_context="A study of fibrotic human lung.",
        miniml_json=miniml_json,
    )

    targets = result["harmonization_targets"]
    assert [(item["pre_hz_field"], item["pre_hz_label"]) for item in targets] == [
        ("source", "IPF lung"),
        ("tissue", "IPF lung"),
        ("tissue", "lung"),
    ]
    assert "target_checker_addition" not in targets[0]
    assert "target_checker_addition" not in targets[1]
    added = targets[2]
    assert added["id"] == "target-2"
    assert added["source"] == "target_checker"
    assert len(added["occurrences"]) == 2
    assert [
        item["source_target_id"]
        for item in added["target_checker_addition"]["sources"]
    ] == ["target-0", "target-1"]
    assert result["target_checker"]["proposed_count"] == 2
    assert result["target_checker"]["added_count"] == 1
    assert result["target_checker"]["merged_proposal_count"] == 1
    assert len(llm.calls) == 1
    assert '"id": "target-0"' in llm.calls[0]["prompt"]
    assert '"id": "target-1"' in llm.calls[0]["prompt"]
    assert "`total RNA` target must not add `RNA`" in llm.calls[0]["prompt"]
    assert "A study of fibrotic human lung." in llm.calls[0]["prompt"]
    assert "Study: IPF spatial transcriptomics" in llm.calls[0]["prompt"]
    assert "Anatomical source tissue." in llm.calls[0]["prompt"]
    assert original_json[0]["sample"][0]["channel"][0]["source"] == "IPF lung"


def test_target_checker_addition_applies_beside_harmonized_original(
    tmp_path: Path,
) -> None:
    llm = SequencedLLM([{"additions": [addition("target-0")]}])
    miniml_json = [{"sample": [{"channel": [{"source": "IPF lung"}]}]}]
    harmonizer = ApplyingHarmonizer(
        llm=llm,
        ontostore=OntoStore(fields={}, storage_dir=tmp_path),
    )

    result = harmonizer.harmonize_miniml_json(miniml_json=miniml_json)

    channel = result["miniml_json"][0]["sample"][0]["channel"][0]
    assert channel["source"] == "IPF lung"
    assert channel["hz_disease"] == "idiopathic pulmonary fibrosis"
    assert channel["hz_tissue"] == "lung"


def test_target_checker_rejects_existing_low_confidence_unknown_and_excess(
    tmp_path: Path,
) -> None:
    proposals = [
        addition("target-0", field_hint="source", label="IPF lung"),
        addition("target-0", confidence="low"),
        addition("missing"),
        addition("target-0"),
        addition("target-0", field_hint="disease", label="IPF"),
        addition("target-0", field_hint="anatomy", label="pulmonary organ"),
        addition("target-0", field_hint="condition", label="fibrosis"),
    ]
    llm = SequencedLLM([{"additions": proposals}])
    miniml_json = [{"sample": [{"channel": [{"source": "IPF lung"}]}]}]
    harmonizer = PassthroughHarmonizer(
        llm=llm,
        ontostore=OntoStore(fields={}, storage_dir=tmp_path),
    )

    result = harmonizer.harmonize_miniml_json(miniml_json=miniml_json)

    assert result["target_checker"]["proposed_count"] == 7
    assert result["target_checker"]["added_count"] == 3
    assert result["target_checker"]["rejected_count"] == 4
    assert {item["reason"] for item in result["target_checker"]["rejected"]} == {
        "already_present",
        "confidence_below_medium",
        "unknown_source_target",
        "per_source_limit_exceeded",
    }


def test_target_checker_retries_malformed_response_then_succeeds(
    tmp_path: Path,
) -> None:
    llm = SequencedLLM(["not json", {"additions": []}])
    harmonizer = PassthroughHarmonizer(
        llm=llm,
        ontostore=OntoStore(fields={}, storage_dir=tmp_path),
    )

    result = harmonizer.harmonize_miniml_json(
        miniml_json=[{"sample": [{"channel": [{"source": "lung"}]}]}]
    )

    assert result["target_checker"]["status"] == "completed"
    assert [item["status"] for item in result["target_checker"]["attempts"]] == [
        "invalid",
        "accepted",
    ]
    assert len(llm.calls) == 2
    assert "Correction Required:" in llm.calls[1]["prompt"]


def test_target_checker_fails_open_after_two_call_failures(tmp_path: Path) -> None:
    llm = SequencedLLM([RuntimeError("offline"), RuntimeError("still offline")])
    harmonizer = PassthroughHarmonizer(
        llm=llm,
        ontostore=OntoStore(fields={}, storage_dir=tmp_path),
    )

    result = harmonizer.harmonize_miniml_json(
        miniml_json=[{"sample": [{"channel": [{"source": "lung"}]}]}]
    )

    assert len(result["harmonization_targets"]) == 1
    assert result["target_checker"]["status"] == "failed"
    assert result["target_checker"]["added_count"] == 0
    assert [item["error"] for item in result["target_checker"]["attempts"]] == [
        "offline",
        "still offline",
    ]


def test_target_checker_is_disabled_by_flag_or_global_llm_switch(
    tmp_path: Path,
) -> None:
    llm = SequencedLLM([])
    harmonizer = PassthroughHarmonizer(
        llm=llm,
        ontostore=OntoStore(fields={}, storage_dir=tmp_path),
    )
    miniml_json = [{"sample": [{"channel": [{"source": "lung"}]}]}]

    disabled = harmonizer.harmonize_miniml_json(
        miniml_json=deepcopy(miniml_json),
        target_checker=False,
    )
    no_llm = harmonizer.harmonize_miniml_json(
        miniml_json=deepcopy(miniml_json),
        llm=False,
    )

    assert disabled["target_checker"] == {
        "status": "disabled",
        "reason": "target_checker_disabled",
        "added_count": 0,
    }
    assert no_llm["target_checker"] == {
        "status": "disabled",
        "reason": "llm_disabled",
        "added_count": 0,
    }
    assert llm.calls == []


def test_target_checker_response_schema_requires_addition_fields() -> None:
    schema = OntologyHarmonizer()._target_checker_response_schema()

    assert schema["required"] == ["additions"]
    item = schema["properties"]["additions"]["items"]
    assert item["required"] == [
        "source_target_id",
        "label",
        "field_hint",
        "confidence",
        "reason",
    ]
