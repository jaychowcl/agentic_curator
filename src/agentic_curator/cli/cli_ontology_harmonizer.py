# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

import argparse
import logging
from typing import Any

from agentic_curator import OntologyHarmonizer
from agentic_curator.cli.common import (
    add_verbosity_argument,
    configure_logging,
    input_value,
    json_input,
    write_json_output,
)
from agentic_curator.curators.ontology_harmonizer import OntoStore, RequestPolicy


LOGGER = logging.getLogger(__name__)


def _add_publication_context(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--publication-context", default=None)
    parser.add_argument("--publication-context-file", default=None)


def _add_metadata_context(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--metadata-context", default=None)
    parser.add_argument("--metadata-context-file", default=None)


def _add_store_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ontology-frameworks", default=None)
    parser.add_argument("--ontology-frameworks-file", default=None)
    parser.add_argument("--fields", default=None)
    parser.add_argument("--fields-file", default=None)
    parser.add_argument("--storage-dir", default=None)


def _add_harmonize_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--strategy", choices=["ols", "rag"], default="ols")
    parser.add_argument("--target-paths", default=None)
    parser.add_argument("--target-paths-file", default=None)
    parser.add_argument("--lookup-llm-judge", dest="lookup_llm_judge", action="store_true", default=True)
    parser.add_argument("--no-lookup-llm-judge", dest="lookup_llm_judge", action="store_false")
    parser.add_argument("--lookup-llm-threshold", type=int, default=2)
    parser.add_argument(
        "--search-llm-judge",
        dest="search_llm_judge",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--no-search-llm-judge",
        dest="search_llm_judge",
        action="store_false",
    )
    parser.add_argument("--llm", dest="llm", action="store_true", default=True)
    parser.add_argument("--no-llm", dest="llm", action="store_false")
    parser.add_argument("--request-timeout", type=float, default=30)
    parser.add_argument("--request-max-attempts", type=int, default=3)
    parser.add_argument("--request-backoff", type=float, default=1)
    parser.add_argument("--cache-ttl-seconds", type=int, default=7 * 24 * 60 * 60)
    parser.add_argument("--force-refresh", action="store_true")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli_ontology_harmonizer",
        description="Run ontology harmonization workflows.",
    )
    add_verbosity_argument(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    harmonize = subparsers.add_parser(
        "harmonize",
        help="Run OntologyHarmonizer.harmonize.",
    )
    add_verbosity_argument(harmonize, default=None, dest="command_verbosity")
    _add_publication_context(harmonize)
    _add_metadata_context(harmonize)
    _add_store_options(harmonize)
    _add_harmonize_options(harmonize)
    harmonize.add_argument("--harmonization-targets", default=None)
    harmonize.add_argument("--harmonization-targets-file", default=None)
    harmonize.add_argument("--target", default=None)
    harmonize.add_argument("--target-file", default=None)
    harmonize.add_argument("--out", default=None)

    miniml = subparsers.add_parser(
        "harmonize-miniml-json",
        help="Run OntologyHarmonizer.harmonize_miniml_json.",
    )
    add_verbosity_argument(miniml, default=None, dest="command_verbosity")
    _add_publication_context(miniml)
    _add_store_options(miniml)
    _add_harmonize_options(miniml)
    miniml.add_argument("--miniml-json", default=None)
    miniml.add_argument("--miniml-json-file", default=None)
    miniml.add_argument("--out", default=None)

    return parser


def _store_from_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> OntoStore:
    ontology_frameworks = json_input(
        parser,
        value=args.ontology_frameworks,
        file=args.ontology_frameworks_file,
        name="ontology-frameworks",
    )
    fields = json_input(
        parser,
        value=args.fields,
        file=args.fields_file,
        name="fields",
    )
    policy = RequestPolicy(
        timeout_seconds=args.request_timeout,
        max_attempts=args.request_max_attempts,
        backoff_base_seconds=args.request_backoff,
        cache_ttl_seconds=args.cache_ttl_seconds,
        force_refresh=args.force_refresh,
    )
    store = OntoStore(
        ontology_frameworks=ontology_frameworks,
        fields=fields,
        storage_dir=args.storage_dir,
    )
    store.request_policy = policy
    return store


def _target_paths(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> list[Any] | None:
    return json_input(
        parser,
        value=args.target_paths,
        file=args.target_paths_file,
        name="target-paths",
    )


def _publication_context(args: argparse.Namespace) -> str | None:
    return input_value(
        value=args.publication_context,
        file=args.publication_context_file,
    )


def _metadata_context(args: argparse.Namespace) -> str | None:
    return input_value(
        value=args.metadata_context,
        file=args.metadata_context_file,
    )


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Any:
    LOGGER.info("Running ontology harmonizer method %s.", args.command)
    ontostore = _store_from_args(args, parser)
    harmonizer = OntologyHarmonizer(ontostore=ontostore)

    if args.command == "harmonize":
        return harmonizer.harmonize(
            publication_context=_publication_context(args),
            metadata_context=_metadata_context(args),
            harmonization_targets=json_input(
                parser,
                value=args.harmonization_targets,
                file=args.harmonization_targets_file,
                name="harmonization-targets",
            ),
            target=json_input(
                parser,
                value=args.target,
                file=args.target_file,
                name="target",
            ),
            strategy=args.strategy,
            target_paths=_target_paths(args, parser),
            lookup_llm_judge=args.lookup_llm_judge,
            lookup_llm_threshold=args.lookup_llm_threshold,
            search_llm_judge=args.search_llm_judge,
            llm=args.llm,
        )

    if args.command == "harmonize-miniml-json":
        return harmonizer.harmonize_miniml_json(
            publication_context=_publication_context(args),
            miniml_json=json_input(
                parser,
                value=args.miniml_json,
                file=args.miniml_json_file,
                name="miniml-json",
            ),
            target_paths=_target_paths(args, parser),
            strategy=args.strategy,
            lookup_llm_judge=args.lookup_llm_judge,
            lookup_llm_threshold=args.lookup_llm_threshold,
            search_llm_judge=args.search_llm_judge,
            llm=args.llm,
        )

    parser.error(f"Unknown command {args.command!r}.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(
        getattr(args, "command_verbosity", None) or args.verbosity
    )
    result = _run(args, parser)
    write_json_output(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
