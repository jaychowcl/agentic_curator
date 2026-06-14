import json

import pytest

from agentic_curator.cli import cli_thematic_reviewer


class RecordingReviewer:
    calls: list[dict] = []

    def review_relevancy(
        self,
        publication_text=None,
        theme=None,
        metadata=None,
        title=None,
    ):
        self.__class__.calls.append(
            {
                "publication_text": publication_text,
                "theme": theme,
                "metadata": metadata,
                "title": title,
            }
        )
        return {}


def test_cli_direct_inputs_prints_json_to_stdout(
    capsys: pytest.CaptureFixture[str],
    monkeypatch,
) -> None:
    RecordingReviewer.calls = []
    monkeypatch.setattr(cli_thematic_reviewer, "ThematicReviewer", RecordingReviewer)

    assert (
        cli_thematic_reviewer.main(
            [
                "--publication-text",
                "Publication text",
                "--theme",
                "fibrosis",
                "--metadata",
                "metadata text",
                "--title",
                "Publication title",
            ]
        )
        == 0
    )

    output = capsys.readouterr()
    assert json.loads(output.out) == {}
    assert output.err == ""
    assert RecordingReviewer.calls == [
        {
            "publication_text": "Publication text",
            "theme": "fibrosis",
            "metadata": "metadata text",
            "title": "Publication title",
        }
    ]


def test_cli_file_inputs_are_read_as_strings(
    capsys: pytest.CaptureFixture[str],
    monkeypatch,
    tmp_path,
) -> None:
    publication_text_file = tmp_path / "publication.txt"
    theme_file = tmp_path / "theme.txt"
    metadata_file = tmp_path / "metadata.txt"
    title_file = tmp_path / "title.txt"
    publication_text_file.write_text("Publication text from file", encoding="utf-8")
    theme_file.write_text("Theme from file", encoding="utf-8")
    metadata_file.write_text('{"organism": "human"}', encoding="utf-8")
    title_file.write_text("Title from file", encoding="utf-8")
    RecordingReviewer.calls = []
    monkeypatch.setattr(cli_thematic_reviewer, "ThematicReviewer", RecordingReviewer)

    assert (
        cli_thematic_reviewer.main(
            [
                "--publication-text-file",
                str(publication_text_file),
                "--theme-file",
                str(theme_file),
                "--metadata-file",
                str(metadata_file),
                "--title-file",
                str(title_file),
            ]
        )
        == 0
    )

    output = capsys.readouterr()
    assert json.loads(output.out) == {}
    assert output.err == ""
    assert RecordingReviewer.calls == [
        {
            "publication_text": "Publication text from file",
            "theme": "Theme from file",
            "metadata": '{"organism": "human"}',
            "title": "Title from file",
        }
    ]


def test_cli_file_inputs_override_direct_values(
    capsys: pytest.CaptureFixture[str],
    monkeypatch,
    tmp_path,
) -> None:
    theme_file = tmp_path / "theme.txt"
    theme_file.write_text("Theme from file", encoding="utf-8")
    RecordingReviewer.calls = []
    monkeypatch.setattr(cli_thematic_reviewer, "ThematicReviewer", RecordingReviewer)

    assert (
        cli_thematic_reviewer.main(
            [
                "--theme",
                "direct theme",
                "--theme-file",
                str(theme_file),
            ]
        )
        == 0
    )

    output = capsys.readouterr()
    assert json.loads(output.out) == {}
    assert RecordingReviewer.calls == [
        {
            "publication_text": None,
            "theme": "Theme from file",
            "metadata": None,
            "title": None,
        }
    ]


def test_cli_out_writes_json_and_keeps_stdout_quiet(
    capsys: pytest.CaptureFixture[str],
    monkeypatch,
    tmp_path,
) -> None:
    outfile = tmp_path / "decision.json"
    RecordingReviewer.calls = []
    monkeypatch.setattr(cli_thematic_reviewer, "ThematicReviewer", RecordingReviewer)

    assert cli_thematic_reviewer.main(["--out", str(outfile)]) == 0

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == ""
    assert json.loads(outfile.read_text(encoding="utf-8")) == {}
