# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_curator.curators.ontology_harmonizer import cache_builder


def test_default_max_workers_caps_cpu_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_builder.os, "cpu_count", lambda: 16)

    assert cache_builder.default_max_workers() == 4


def test_default_max_workers_handles_missing_cpu_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cache_builder.os, "cpu_count", lambda: None)

    assert cache_builder.default_max_workers() == 1


def test_load_frameworks_uses_order_then_appends_unknowns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cache_builder, "FRAMEWORK_ORDER", ["beta", "alpha"])

    class FakeStore:
        DEFAULT_ONTOLOGY_FRAMEWORKS = {
            "gamma": {},
            "alpha": {},
            "beta": {},
        }

    monkeypatch.setattr(cache_builder, "OntoStore", FakeStore)

    assert cache_builder.load_frameworks() == ["beta", "alpha", "gamma"]


def test_build_ontology_cache_collects_results_in_framework_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_run_framework(name: str, timeout: int, *, force: bool) -> dict:
        calls.append((name, force))
        status = "failed" if name == "beta" else "cached"
        return {
            "framework": name,
            "status": status,
            "elapsed_seconds": 0.1,
            "json_path": str(tmp_path / f"{name}.json"),
        }

    monkeypatch.setattr(cache_builder, "run_framework", fake_run_framework)
    monkeypatch.setattr(cache_builder, "validate_successes", lambda results: [])

    manifest = cache_builder.build_ontology_cache(
        frameworks=["alpha", "beta", "gamma"],
        out_dir=tmp_path,
        prefix="manifest",
        timeout=10,
        force_frameworks={"beta"},
        max_workers=2,
    )

    assert calls == [("alpha", False), ("beta", True), ("gamma", False)]
    assert [result["framework"] for result in manifest["results"]] == [
        "alpha",
        "beta",
        "gamma",
    ]
    assert manifest["summary"] == {"cached": 2, "failed": 1}
    assert manifest["max_workers"] == 2
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "manifest.log").exists()


def test_build_ontology_cache_uses_default_max_workers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cache_builder, "default_max_workers", lambda: 3)
    monkeypatch.setattr(
        cache_builder,
        "run_framework",
        lambda name, timeout, *, force: {
            "framework": name,
            "status": "cached",
            "elapsed_seconds": 0.1,
            "json_path": str(tmp_path / f"{name}.json"),
        },
    )
    monkeypatch.setattr(cache_builder, "validate_successes", lambda results: [])

    manifest = cache_builder.build_ontology_cache(
        frameworks=["alpha"],
        out_dir=tmp_path,
        prefix="manifest",
    )

    assert manifest["max_workers"] == 3


def test_main_writes_manifest_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cache_builder, "load_frameworks", lambda: ["alpha"])
    monkeypatch.setattr(
        cache_builder,
        "run_framework",
        lambda name, timeout, *, force: {
            "framework": name,
            "status": "cached",
            "elapsed_seconds": 0.1,
            "json_path": str(tmp_path / "alpha.json"),
        },
    )
    monkeypatch.setattr(cache_builder, "validate_successes", lambda results: [])

    assert (
        cache_builder.main(
            [
                "--out-dir",
                str(tmp_path),
                "--out-prefix",
                "cache",
                "--max-workers",
                "2",
                "--timeout",
                "5",
                "--force-framework",
                "alpha",
            ]
        )
        == 0
    )

    manifest = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    output = capsys.readouterr()
    assert manifest["force_frameworks"] == ["alpha"]
    assert manifest["max_workers"] == 2
    assert "manifest:" in output.out
    assert "log:" in output.out


def test_pyproject_exposes_build_ontology_cache_console_script() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert (
        'build_ontology_cache = "agentic_curator.curators.'
        'ontology_harmonizer.cache_builder:main"'
    ) in pyproject
