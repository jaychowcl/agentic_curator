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


def _repository_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    )
    return [ROOT / line for line in output.splitlines()]


def _is_prompt_markdown(path: Path) -> bool:
    return path.suffix == ".md" and "prompts" in path.parts


def _requires_header(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if relative in {"LICENSE", "README.md"}:
        return False
    if _is_prompt_markdown(path):
        return False
    return path.suffix in {".py", ".md", ".toml"} or path.name in {
        ".gitignore",
        "requirements.txt",
    }


def test_tracked_comment_capable_files_have_authors_header() -> None:
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in _repository_files()
        if _requires_header(path)
        and AUTHORS_TEXT not in path.read_text(encoding="utf-8")
    ]

    assert missing == []


def test_prompt_markdown_and_license_do_not_have_authors_header() -> None:
    unexpected = [
        path.relative_to(ROOT).as_posix()
        for path in _repository_files()
        if (path.relative_to(ROOT).as_posix() == "LICENSE" or _is_prompt_markdown(path))
        and AUTHORS_TEXT in path.read_text(encoding="utf-8")
    ]

    assert unexpected == []
