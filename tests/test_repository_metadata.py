# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHORS_TEXT = (
    "Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026"
)
AUTHOR_LINES = (
    AUTHORS_TEXT,
    "https://github.com/jaychowcl",
    "https://saezlab.org",
    "https://www.gsk.com/",
)
HASH_AUTHORS_HEADER = "\n".join(
    (
        "# " + "=" * 77,
        "# Authors",
        "# " + "=" * 77,
        "# " + AUTHORS_TEXT,
        "# https://github.com/jaychowcl",
        "# https://saezlab.org",
        "# https://www.gsk.com/",
        "# " + "=" * 77,
        "",
    )
)
MARKDOWN_AUTHORS_HEADER = "\n".join(
    (
        "<!--",
        "=" * 77,
        "Authors",
        "=" * 77,
        AUTHORS_TEXT,
        "https://github.com/jaychowcl",
        "https://saezlab.org",
        "https://www.gsk.com/",
        "=" * 77,
        "-->",
        "",
    )
)


def _repository_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    )
    return [ROOT / line for line in output.splitlines()]


def _requires_header(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if relative in {"LICENSE", "README.md"}:
        return False
    if "prompts" in path.parts:
        return False
    return path.suffix in {".py", ".md", ".toml"} or path.name in {
        ".gitignore",
        "requirements.txt",
    }


def test_tracked_comment_capable_files_have_one_complete_authors_header() -> None:
    invalid = []
    for path in _repository_files():
        if not _requires_header(path):
            continue
        text = path.read_text(encoding="utf-8")
        is_markdown = path.suffix == ".md"
        expected_header = MARKDOWN_AUTHORS_HEADER if is_markdown else HASH_AUTHORS_HEADER
        if (
            not text.startswith(expected_header)
            or text.count(expected_header) != 1
            or any(line not in text for line in AUTHOR_LINES)
        ):
            invalid.append(path.relative_to(ROOT).as_posix())

    assert invalid == []


def test_external_license_has_no_project_authors_header() -> None:
    assert AUTHORS_TEXT not in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_project_prompt_markdown_excludes_authors_context() -> None:
    prompts = [path for path in _repository_files() if "prompts" in path.parts]
    assert prompts
    assert all(AUTHORS_TEXT not in path.read_text(encoding="utf-8") for path in prompts)
    assert all("Authors" not in path.read_text(encoding="utf-8") for path in prompts)


def test_readme_has_required_guide_structure_and_links() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required_headings = [
        "# agentic-curator",
        "## Description",
        "## Installation",
        "### Requirements",
        "## Quickstart",
        "### Inputs & Outputs",
        "## Guide",
        "### Code flow",
        "## Docs",
        "## Authors",
    ]

    positions = [readme.index(heading) for heading in required_headings]
    assert positions == sorted(positions)
    assert "[Codebase handoff](docs/codebase.md)" in readme
    assert "[Documentation index](docs/index.md)" in readme
    assert "Created by [jaychowcl](https://github.com/jaychowcl)" in readme


def test_readme_has_linked_authors_and_complete_citation() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "[Saez-Rodriguez Group](https://saezlab.org)" in readme
    assert "[GSK](https://www.gsk.com/)" in readme
    assert "### Please cite us using" in readme
    citation = readme.split("### Please cite us using", maxsplit=1)[1]
    for value in (
        "Jay Chow",
        "Saez-Rodriguez Group",
        "GSK",
        "June 2026",
        "agentic-curator",
        "Version 0.1.0",
        "Computer software",
        "https://github.com/jaychowcl/agentic_curator",
    ):
        assert value in citation


def test_readme_covers_supported_interfaces_and_current_controls() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for interface in (
        "Python Query Generation",
        "CLI Query Generation",
        "Python Thematic Review",
        "CLI Thematic Review",
        "Python Ontology Harmonization",
        "CLI Ontology Harmonization",
        "Ontology Cache Builder",
        "Python LLM Facade",
        "Docker",
    ):
        assert interface in readme

    for option in (
        "--max-queries",
        "--no-direct-lookup-judge",
        "--no-rag-lookup",
        "--no-rag-lookup-judge",
        "--no-ols-lookup",
        "--no-ols-lookup-judge",
        "--no-field-assignment-judge",
        "--request-timeout",
        "--request-max-attempts",
        "--request-backoff",
        "--cache-ttl-seconds",
        "--force-refresh",
        "--force-framework",
    ):
        assert option in readme

    assert "does not currently provide a Dockerfile" in readme
