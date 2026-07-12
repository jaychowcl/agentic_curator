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

from agentic_curator.curators.ontology_harmonizer import OntoStore, RequestPolicy


def ontology_json(tmp_path: Path, terms: dict) -> Path:
    path = tmp_path / "test.json"
    path.write_text(
        json.dumps({"ontology": {"id": "test"}, "terms": terms}) + "\n",
        encoding="utf-8",
    )
    return path


def test_request_policy_defaults() -> None:
    policy = RequestPolicy()

    assert policy.timeout_seconds == 30
    assert policy.max_attempts == 3
    assert policy.backoff_base_seconds == 1
    assert policy.cache_ttl_seconds == 7 * 24 * 60 * 60
    assert policy.force_refresh is False


def test_field_registry_persists_crud_across_store_instances(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "ontologies.sqlite3"
    store = OntoStore(
        ontology_frameworks={}, storage_dir=tmp_path, sqlite_path=sqlite_path
    )

    store.add_field(
        "sample_type",
        {
            "label": "Sample type",
            "aliases": ["source material"],
            "description": "Type of biological sample.",
            "expected_ontologies": ["efo"],
            "allowed_modes": ["field_value", "tag_value"],
            "source": "llm",
            "review_status": "unreviewed",
        },
    )
    store.update_field("sample_type", description="Updated description.")

    reopened = OntoStore(
        ontology_frameworks={}, storage_dir=tmp_path, sqlite_path=sqlite_path
    )
    assert reopened.get_field("sample_type") == {
        "field": "sample_type",
        "label": "Sample type",
        "aliases": ["source material"],
        "description": "Updated description.",
        "expected_ontologies": ["efo"],
        "allowed_modes": ["field_value", "tag_value"],
        "source": "llm",
        "review_status": "unreviewed",
    }
    reopened.set_field_review_status("sample_type", "approved")
    assert reopened.list_fields(review_status="approved")[0]["field"] == "sample_type"
    assert reopened.remove_field("sample_type") is True
    assert reopened.remove_field("sample_type") is False


def test_field_registry_rejects_alias_conflicts(tmp_path: Path) -> None:
    store = OntoStore(ontology_frameworks={}, storage_dir=tmp_path)
    store.add_field("source", {"label": "Source", "aliases": ["sample"]})

    with pytest.raises(ValueError, match="alias"):
        store.add_field("sample_type", {"label": "Sample type", "aliases": ["sample"]})


def test_external_cache_respects_expiry_and_force_refresh(tmp_path: Path) -> None:
    store = OntoStore(ontology_frameworks={}, storage_dir=tmp_path)
    key = {"query": "lung", "ontology_id": "uberon", "rows": 25}
    store.set_cached_response("ols", "search", key, [{"id": "UBERON:1"}], now=100)

    assert store.get_cached_response(
        "ols", "search", key, ttl_seconds=60, now=159
    ) == [{"id": "UBERON:1"}]
    assert store.get_cached_response(
        "ols", "search", key, ttl_seconds=60, now=161
    ) is None
    assert store.get_cached_response(
        "ols", "search", key, ttl_seconds=60, now=120, force_refresh=True
    ) is None
    assert store.clear_cached_responses(provider="ols", operation="search") == 1


def test_lookup_with_metadata_prefers_exact_then_falls_back_to_fts(
    tmp_path: Path,
) -> None:
    exact = {"id": "TEST:1", "title": "lung"}
    approximate = {
        "id": "TEST:2",
        "title": "Caenorhabditis elegans embryo",
        "synonyms": {"exact": ["nematode embryo"]},
        "description": ["An embryo of Caenorhabditis elegans."],
    }
    path = ontology_json(
        tmp_path,
        {
            "label": {"lung": exact, "caenorhabditis_elegans_embryo": approximate},
            "id": {"test:1": exact, "test:2": approximate},
        },
    )
    store = OntoStore(
        ontology_frameworks={"test": {"path": tmp_path / "missing.owl", "json_path": path}},
        storage_dir=tmp_path,
    )

    exact_result = store.lookup_with_metadata("lung", "test")
    fts_result = store.lookup_with_metadata("nematode embryo", "test")

    assert exact_result["match_type"] == "exact"
    assert exact_result["hits"][0]["id"] == "TEST:1"
    assert fts_result["match_type"] == "fts"
    assert fts_result["hits"][0]["id"] == "TEST:2"
    assert isinstance(fts_result["ranking"][0]["score"], float)
