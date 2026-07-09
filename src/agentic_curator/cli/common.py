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
import json
import logging
import sys
from pathlib import Path
from typing import Any


VERBOSITY_LEVELS = {
    "quiet": logging.CRITICAL + 1,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def add_verbosity_argument(
    parser: argparse.ArgumentParser,
    *,
    default: str | None = "warning",
    dest: str = "verbosity",
) -> None:
    parser.add_argument(
        "--verbosity",
        dest=dest,
        choices=sorted(VERBOSITY_LEVELS),
        default=default,
        help="Set stderr logging verbosity.",
    )


def configure_logging(verbosity: str | None) -> None:
    if verbosity is None:
        verbosity = "warning"
    level = VERBOSITY_LEVELS[verbosity]
    logging.basicConfig(
        level=level,
        format="%(levelname)s:%(name)s:%(message)s",
        stream=sys.stderr,
        force=True,
    )
    if verbosity == "quiet":
        logging.disable(logging.CRITICAL)
    else:
        logging.disable(logging.NOTSET)


def input_value(value: str | None, file: str | None) -> str | None:
    if file is not None:
        logging.getLogger(__name__).debug("Reading UTF-8 input file %s.", file)
        return Path(file).read_text(encoding="utf-8")

    return value


def json_input(
    parser: argparse.ArgumentParser,
    *,
    value: str | None,
    file: str | None,
    name: str,
) -> Any:
    text = input_value(value=value, file=file)
    if text is None:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        parser.error(f"Invalid JSON for {name}: {exc.msg}")


def write_json_output(result: Any, out: str | None) -> None:
    if out is not None:
        logging.getLogger(__name__).debug("Writing JSON output to %s.", out)
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
        return

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
