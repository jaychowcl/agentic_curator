# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

import json

import pytest

from agentic_curator.cli import cli_ontology_harmonizer


class RecordingStore:
    calls: list[dict] = []

    def __init__(
        self,
        ontology_frameworks=None,
        fields=None,
        storage_dir=None,
    ) -> None:
        self.__class__.calls.append(
            {
                "ontology_frameworks": ontology_frameworks,
                "fields": fields,
                "storage_dir": storage_dir,
            }
        )


class RecordingHarmonizer:
    calls: list[dict] = []

    def __init__(self, ontostore=None) -> None:
        self.ontostore = ontostore

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
        search_llm_judge=True,
        llm=True,
    ):
        self.__class__.calls.append(
            {
                "method": "harmonize",
                "publication_context": publication_context,
                "harmonization_targets": harmonization_targets,
                "target": target,
                "strategy": strategy,
                "ontostore": ontostore,
                "target_paths": target_paths,
                "lookup_llm_judge": lookup_llm_judge,
                "lookup_llm_threshold": lookup_llm_threshold,
                "search_llm_judge": search_llm_judge,
                "llm": llm,
            }
        )
        return {"harmonization_targets": []}

    def harmonize_miniml_json(
        self,
        publication_context=None,
        miniml_json=None,
        ontostore=None,
        target_paths=None,
        strategy="websearch",
        lookup_llm_judge=False,
        lookup_llm_threshold=2,
        search_llm_judge=True,
        llm=True,
    ):
        self.__class__.calls.append(
            {
                "method": "harmonize_miniml_json",
                "publication_context": publication_context,
                "miniml_json": miniml_json,
                "ontostore": ontostore,
                "target_paths": target_paths,
                "strategy": strategy,
                "lookup_llm_judge": lookup_llm_judge,
                "lookup_llm_threshold": lookup_llm_threshold,
                "search_llm_judge": search_llm_judge,
                "llm": llm,
            }
        )
        return {"miniml_json": miniml_json}


@pytest.fixture(autouse=True)
def _patch_cli(monkeypatch):
    RecordingStore.calls = []
    RecordingHarmonizer.calls = []
    monkeypatch.setattr(cli_ontology_harmonizer, "OntoStore", RecordingStore)
    monkeypatch.setattr(
        cli_ontology_harmonizer,
        "OntologyHarmonizer",
        RecordingHarmonizer,
    )


def test_cli_harmonize_passes_all_options_to_harmonizer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        cli_ontology_harmonizer.main(
            [
                "harmonize",
                "--publication-context",
                "Publication text",
                "--target",
                '{"id": "target-1", "pre_hz_label": "lung"}',
                "--target-paths",
                '[{"path": "/organism", "mode": "container_value"}]',
                "--ontology-frameworks",
                '{"custom": {"path": "custom.owl"}}',
                "--fields",
                '{"organism": {"label": "organism"}}',
                "--storage-dir",
                "store",
                "--strategy",
                "rag",
                "--lookup-llm-judge",
                "--lookup-llm-threshold",
                "3",
                "--no-search-llm-judge",
                "--no-llm",
            ]
        )
        == 0
    )

    output = capsys.readouterr()
    assert json.loads(output.out) == {"harmonization_targets": []}
    assert RecordingStore.calls == [
        {
            "ontology_frameworks": {"custom": {"path": "custom.owl"}},
            "fields": {"organism": {"label": "organism"}},
            "storage_dir": "store",
        }
    ]
    assert RecordingHarmonizer.calls == [
        {
            "method": "harmonize",
            "publication_context": "Publication text",
            "harmonization_targets": None,
            "target": {"id": "target-1", "pre_hz_label": "lung"},
            "strategy": "rag",
            "ontostore": None,
            "target_paths": [{"path": "/organism", "mode": "container_value"}],
            "lookup_llm_judge": True,
            "lookup_llm_threshold": 3,
            "search_llm_judge": False,
            "llm": False,
        }
    ]


def test_cli_harmonize_miniml_json_passes_json_file_inputs(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    miniml_file = tmp_path / "miniml.json"
    miniml_file.write_text('{"sample": []}', encoding="utf-8")
    context_file = tmp_path / "context.txt"
    context_file.write_text("Publication context", encoding="utf-8")

    assert (
        cli_ontology_harmonizer.main(
            [
                "harmonize-miniml-json",
                "--publication-context-file",
                str(context_file),
                "--miniml-json-file",
                str(miniml_file),
            ]
        )
        == 0
    )

    output = capsys.readouterr()
    assert json.loads(output.out) == {"miniml_json": {"sample": []}}
    assert RecordingHarmonizer.calls == [
        {
            "method": "harmonize_miniml_json",
            "publication_context": "Publication context",
            "miniml_json": {"sample": []},
            "ontostore": None,
            "target_paths": None,
            "strategy": "websearch",
            "lookup_llm_judge": False,
            "lookup_llm_threshold": 2,
            "search_llm_judge": True,
            "llm": True,
        }
    ]


def test_cli_invalid_json_exits_with_parser_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_ontology_harmonizer.main(["harmonize", "--target", "{bad json"])

    output = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "Invalid JSON" in output.err
