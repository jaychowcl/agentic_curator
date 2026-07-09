from __future__ import annotations

import argparse
import logging
from typing import Any

from agentic_curator import ThematicReviewer
from agentic_curator.cli.common import (
    add_verbosity_argument,
    configure_logging,
    input_value,
    json_input,
    write_json_output,
)


LOGGER = logging.getLogger(__name__)
COMMANDS = {"review", "extract-evidence", "judge-evidence"}


def _add_reviewer_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--publication-text", default=None)
    parser.add_argument("--publication-text-file", default=None)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--theme-file", default=None)
    parser.add_argument("--metadata", default=None)
    parser.add_argument("--metadata-file", default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--title-file", default=None)


def _add_common_outputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", default=None)


def _build_parser(*, include_legacy_options: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli_thematic_reviewer",
        description="Run thematic curation reviewer workflows.",
    )
    add_verbosity_argument(parser)
    if include_legacy_options:
        _add_reviewer_inputs(parser)
        _add_common_outputs(parser)

    subparsers = parser.add_subparsers(dest="command")

    review = subparsers.add_parser(
        "review",
        help="Run review_relevancy.",
    )
    add_verbosity_argument(review, default=None, dest="command_verbosity")
    _add_reviewer_inputs(review)
    _add_common_outputs(review)

    extract_evidence = subparsers.add_parser(
        "extract-evidence",
        help="Run extract_evidence.",
    )
    add_verbosity_argument(
        extract_evidence,
        default=None,
        dest="command_verbosity",
    )
    _add_reviewer_inputs(extract_evidence)
    _add_common_outputs(extract_evidence)

    judge_evidence = subparsers.add_parser(
        "judge-evidence",
        help="Run judge_evidence.",
    )
    add_verbosity_argument(judge_evidence, default=None, dest="command_verbosity")
    judge_evidence.add_argument("--evidences", default=None)
    judge_evidence.add_argument("--evidences-file", default=None)
    judge_evidence.add_argument("--theme", default=None)
    judge_evidence.add_argument("--theme-file", default=None)
    judge_evidence.add_argument("--title", default=None)
    judge_evidence.add_argument("--title-file", default=None)
    _add_common_outputs(judge_evidence)

    return parser


def _parser_for_argv(argv: list[str] | None) -> argparse.ArgumentParser:
    args = [] if argv is None else list(argv)
    include_legacy_options = not any(arg in COMMANDS for arg in args)
    return _build_parser(include_legacy_options=include_legacy_options)


def _reviewer_inputs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "publication_text": input_value(
            value=args.publication_text,
            file=args.publication_text_file,
        ),
        "theme": input_value(value=args.theme, file=args.theme_file),
        "metadata": input_value(value=args.metadata, file=args.metadata_file),
        "title": input_value(value=args.title, file=args.title_file),
    }


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Any:
    command = args.command or "review"
    LOGGER.info("Running thematic reviewer method %s.", command)
    reviewer = ThematicReviewer()

    if command == "review":
        return reviewer.review_relevancy(**_reviewer_inputs(args))

    if command == "extract-evidence":
        return reviewer.extract_evidence(**_reviewer_inputs(args))

    if command == "judge-evidence":
        evidences = json_input(
            parser,
            value=args.evidences,
            file=args.evidences_file,
            name="evidences",
        )
        return reviewer.judge_evidence(
            evidences=evidences,
            theme=input_value(value=args.theme, file=args.theme_file),
            title=input_value(value=args.title, file=args.title_file),
        )

    parser.error(f"Unknown command {command!r}.")


def main(argv: list[str] | None = None) -> int:
    parser = _parser_for_argv(argv)
    args = parser.parse_args(argv)
    configure_logging(
        getattr(args, "command_verbosity", None) or args.verbosity
    )
    result = _run(args, parser)
    write_json_output(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
