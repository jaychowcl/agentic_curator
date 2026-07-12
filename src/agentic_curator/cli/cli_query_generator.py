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

from agentic_curator import QueryGenerator
from agentic_curator.cli.common import (
    add_verbosity_argument,
    configure_logging,
    input_value,
    write_json_output,
)

MIN_QUERIES = 1
MAX_QUERIES = 3


def _query_count(value: str) -> int:
    count = int(value)
    if not MIN_QUERIES <= count <= MAX_QUERIES:
        raise argparse.ArgumentTypeError("must be an integer from 1 to 3")
    return count


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli_query_generator",
        description="Generate bounded Europe PMC queries from a theme.",
    )
    add_verbosity_argument(parser)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--theme-file", default=None)
    parser.add_argument("--max-queries", type=_query_count, default=3)
    parser.add_argument("--out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbosity)
    result = QueryGenerator().generate_queries(
        theme=input_value(value=args.theme, file=args.theme_file),
        max_queries=args.max_queries,
    )
    write_json_output(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
