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

from agentic_curator.cli import cli_query_generator


class RecordingGenerator:
    calls = []

    def generate_queries(self, theme, max_queries=3):
        self.__class__.calls.append(
            {"theme": theme, "max_queries": max_queries}
        )
        return {"queries": ["query"], "details": [], "strategy_summary": "test"}


@pytest.fixture(autouse=True)
def _patch_generator(monkeypatch):
    RecordingGenerator.calls = []
    monkeypatch.setattr(cli_query_generator, "QueryGenerator", RecordingGenerator)


def test_cli_generates_queries_from_direct_theme(capsys) -> None:
    assert cli_query_generator.main(
        ["--theme", "fibrosis", "--max-queries", "2"]
    ) == 0

    output = capsys.readouterr()
    assert json.loads(output.out)["queries"] == ["query"]
    assert output.err == ""
    assert RecordingGenerator.calls == [{"theme": "fibrosis", "max_queries": 2}]


def test_cli_theme_file_takes_precedence_and_writes_output(tmp_path, capsys) -> None:
    theme_file = tmp_path / "theme.md"
    out_file = tmp_path / "queries.json"
    theme_file.write_text("theme from file", encoding="utf-8")

    assert cli_query_generator.main(
        [
            "--theme",
            "ignored",
            "--theme-file",
            str(theme_file),
            "--out",
            str(out_file),
            "--verbosity",
            "debug",
        ]
    ) == 0

    assert json.loads(out_file.read_text(encoding="utf-8"))["queries"] == ["query"]
    assert capsys.readouterr().out == ""
    assert RecordingGenerator.calls == [
        {"theme": "theme from file", "max_queries": 3}
    ]


@pytest.mark.parametrize("value", ["0", "4"])
def test_cli_rejects_out_of_range_max_queries(value) -> None:
    with pytest.raises(SystemExit):
        cli_query_generator.main(
            ["--theme", "fibrosis", "--max-queries", value]
        )
