from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentic_curator import ThematicReviewer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli_thematic_reviewer",
        description="Review a publication against a thematic curation target.",
    )
    parser.add_argument("--publication-text", default=None)
    parser.add_argument("--publication-text-file", default=None)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--theme-file", default=None)
    parser.add_argument("--metadata", default=None)
    parser.add_argument("--metadata-file", default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--title-file", default=None)
    parser.add_argument("--out", default=None)
    return parser


def _input_value(value: str | None, file: str | None) -> str | None:
    if file is not None:
        return Path(file).read_text(encoding="utf-8")

    return value


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    result = ThematicReviewer().review_relevancy(
        publication_text=_input_value(
            value=args.publication_text,
            file=args.publication_text_file,
        ),
        theme=_input_value(value=args.theme, file=args.theme_file),
        metadata=_input_value(value=args.metadata, file=args.metadata_file),
        title=_input_value(value=args.title, file=args.title_file),
    )

    if args.out is not None:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    else:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
