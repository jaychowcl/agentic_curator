# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from agentic_curator.curators.ontology_harmonizer import (
    build_miniml_metadata_context,
)


def test_builds_context_from_series_and_supported_sample_channel_fields() -> None:
    miniml = {
        "series": {"title": "  Fibrosis   study  ", "summary": "not included"},
        "platform": {"title": "not included"},
        "sample": [
            {
                "channel": [
                    {
                        "source": "lung tissue",
                        "molecule": "total RNA",
                        "organism": [{"value": "Homo sapiens", "taxid": "9606"}],
                        "characteristics": [
                            {"tag": "disease", "value": "fibrosis"},
                            {"tag": "protocol", "value": "not a protocol section"},
                        ],
                        "extract_protocol": "long protocol text",
                    }
                ]
            }
        ],
    }

    assert build_miniml_metadata_context(miniml) == (
        "Study: Fibrosis study | source=lung tissue; molecule=total RNA; "
        "organism=Homo sapiens; disease=fibrosis; protocol=not a protocol section"
    )


def test_context_is_deterministic_deduplicated_and_limited() -> None:
    miniml = {
        "series": {"title": "Unicode study β"},
        "sample": [
            {"channel": [{"source": "lung", "characteristics": [
                {"tag": "description", "value": "x" * 600}
            ]}]},
            {"channel": [{"source": "lung"}]},
        ],
    }

    context = build_miniml_metadata_context(miniml)

    assert context.startswith("Study: Unicode study β | source=lung; description=")
    assert context.endswith("…")
    assert len(context) == 500
    assert context.count("source=lung") == 1


def test_context_supports_custom_limit_and_invalid_input() -> None:
    assert build_miniml_metadata_context(None) is None
    assert build_miniml_metadata_context("not miniml") is None
    assert build_miniml_metadata_context(
        {"series": {"title": "A long study title"}}, max_chars=10
    ) == "Study: A…"


def test_supplied_targets_preserve_harmonizer_explicit_path_context() -> None:
    assert build_miniml_metadata_context(
        {"series": {"title": "Study"}},
        harmonization_targets=[
            {"pre_hz_field": "custom", "pre_hz_label": "value"}
        ],
    ) == "Study: Study | custom=value"
