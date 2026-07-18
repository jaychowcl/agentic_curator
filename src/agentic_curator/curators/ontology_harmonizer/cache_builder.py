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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterable

import ijson

from agentic_curator.curators.ontology_harmonizer.ontology_store import OntoStore


ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / ".dev"

FRAMEWORK_ORDER = [
    "efo",
    "obi",
    "pato",
    "cl",
    "uberon",
    "hp",
    "mondo",
    "chebi",
    "ncit",
    "ncbitaxon",
    "snomed",
]


def default_max_workers() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def child_code() -> str:
    return r"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from agentic_curator.curators.ontology_harmonizer import OntoStore

name = sys.argv[1]
force = sys.argv[2] == "1"
started = time.monotonic()
store = OntoStore()
framework = store.ontology_frameworks[name]
owl_path = Path(framework["owl_path"])
json_path = Path(framework["json_path"])
had_owl = owl_path.exists()
had_json = json_path.exists()

result_path = store.get(name, force=force)

payload = {
    "framework": name,
    "status": "force_rebuilt" if force else ("cached" if had_json else ("parsed" if had_owl else "downloaded_parsed")),
    "owl_path": str(owl_path),
    "json_path": str(result_path),
    "had_owl": had_owl,
    "had_json": had_json,
    "owl_exists": owl_path.exists(),
    "json_exists": Path(result_path).exists(),
    "owl_size": owl_path.stat().st_size if owl_path.exists() else None,
    "json_size": Path(result_path).stat().st_size if Path(result_path).exists() else None,
    "elapsed_seconds": round(time.monotonic() - started, 3),
}
print(json.dumps(payload, sort_keys=True))
"""


def load_frameworks() -> list[str]:
    available = set(OntoStore.DEFAULT_ONTOLOGY_FRAMEWORKS)
    ordered = [name for name in FRAMEWORK_ORDER if name in available]
    ordered.extend(sorted(available.difference(ordered)))
    return ordered


def run_framework(name: str, timeout: int, *, force: bool) -> dict[str, Any]:
    env = dict(os.environ)
    pythonpath = str(SRC)
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    started = time.monotonic()
    command = [sys.executable, "-c", child_code(), name, "1" if force else "0"]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "framework": name,
            "status": "timeout",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "timeout_seconds": timeout,
            "stdout": exc.stdout,
            "stderr": exc.stderr,
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        return {
            "framework": name,
            "status": "failed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    try:
        payload = json.loads(stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {
            "framework": name,
            "status": "failed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "error": f"Could not parse child JSON: {exc}",
        }

    if stderr:
        payload["stderr"] = stderr
    return payload


def validate_successes(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validations = []
    for result in results:
        if result.get("status") not in {
            "cached",
            "parsed",
            "downloaded_parsed",
            "force_rebuilt",
        }:
            continue
        json_path = Path(result["json_path"])
        started = time.monotonic()
        try:
            ontology_is_mapping = False
            terms_is_mapping = False
            with json_path.open("rb") as handle:
                for prefix, event, _value in ijson.parse(handle):
                    if prefix == "ontology" and event == "start_map":
                        ontology_is_mapping = True
                    elif prefix == "terms" and event == "start_map":
                        terms_is_mapping = True
            valid = ontology_is_mapping and terms_is_mapping
            validations.append(
                {
                    "framework": result["framework"],
                    "json_path": str(json_path),
                    "valid": valid,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
        except Exception as exc:  # noqa: BLE001 - manifest should preserve failures.
            validations.append(
                {
                    "framework": result["framework"],
                    "json_path": str(json_path),
                    "valid": False,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "error": repr(exc),
                }
            )
    return validations


def sync_sqlite_cache(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Index every successfully generated ontology JSON in the shared database."""
    successful = [
        result
        for result in results
        if result.get("status")
        in {"cached", "parsed", "downloaded_parsed", "force_rebuilt"}
        and result.get("json_path")
    ]
    store = OntoStore()
    framework_names = []
    for result in successful:
        name = str(result["framework"])
        if name not in store.ontology_frameworks:
            continue
        store.ontology_frameworks[name]["json_path"] = Path(result["json_path"])
        framework_names.append(name)

    return {
        "path": str(store.sqlite_path),
        "frameworks": store.sync_sqlite(framework_names),
    }


def build_rag_indexes(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build semantic indexes for every successfully cached framework."""
    store = OntoStore()
    indexed: dict[str, Any] = {}
    for result in results:
        if result.get("status") not in {
            "cached",
            "parsed",
            "downloaded_parsed",
            "force_rebuilt",
        } or not result.get("json_path"):
            continue
        name = str(result["framework"])
        if name not in store.ontology_frameworks:
            continue
        store.ontology_frameworks[name]["json_path"] = Path(result["json_path"])
        started = time.monotonic()
        try:
            index_path = store.build_rag_index(name)
            indexed[name] = {
                "status": "built",
                "index_path": str(index_path),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        except Exception as exc:  # noqa: BLE001 - preserve a complete manifest.
            indexed[name] = {
                "status": "failed",
                "error": repr(exc),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
    return {"frameworks": indexed}


def build_ontology_cache(
    *,
    frameworks: Iterable[str] | None = None,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    prefix: str | None = None,
    timeout: int = 2700,
    force_frameworks: Iterable[str] = (),
    max_workers: int | None = None,
    rag_index: bool = False,
) -> dict[str, Any]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_prefix = prefix or f"ontology-cache-build.{timestamp}"
    manifest_path = output_dir / f"{output_prefix}.json"
    log_path = output_dir / f"{output_prefix}.log"

    framework_names = list(load_frameworks() if frameworks is None else frameworks)
    force_names = set(force_frameworks)
    worker_count = default_max_workers() if max_workers is None else max(1, max_workers)
    results_by_name: dict[str, dict[str, Any]] = {}
    started = time.monotonic()

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Ontology cache build started {timestamp}\n")
        log.write(f"Frameworks: {', '.join(framework_names)}\n")
        log.write(f"Max workers: {worker_count}\n")
        log.flush()

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    run_framework,
                    name,
                    timeout,
                    force=name in force_names,
                ): (index, name)
                for index, name in enumerate(framework_names, start=1)
            }
            for _future, (index, name) in futures.items():
                message = f"[{index}/{len(framework_names)}] {name}: start\n"
                print(message, end="", flush=True)
                log.write(message)
            log.flush()

            for future in as_completed(futures):
                index, name = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - preserve worker failures.
                    result = {
                        "framework": name,
                        "status": "failed",
                        "elapsed_seconds": None,
                        "error": repr(exc),
                    }
                results_by_name[name] = result
                done = (
                    f"[{index}/{len(framework_names)}] {name}: "
                    f"{result['status']} in {result.get('elapsed_seconds')}s\n"
                )
                print(done, end="", flush=True)
                log.write(done)
                if result.get("stderr"):
                    log.write(f"stderr:\n{result['stderr']}\n")
                if result.get("stdout") and result["status"] == "failed":
                    log.write(f"stdout:\n{result['stdout']}\n")
                log.flush()

    results = [results_by_name[name] for name in framework_names]
    validations = validate_successes(results)
    sqlite_result = sync_sqlite_cache(results)
    rag_result = build_rag_indexes(results) if rag_index else None
    manifest = {
        "started_at": timestamp,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "timeout_seconds": timeout,
        "max_workers": worker_count,
        "force_frameworks": sorted(force_names),
        "frameworks": framework_names,
        "results": results,
        "validations": validations,
        "sqlite": sqlite_result,
        **({"rag": rag_result} if rag_result is not None else {}),
        "manifest_path": str(manifest_path),
        "log_path": str(log_path),
        "summary": {
            status: sum(1 for item in results if item.get("status") == status)
            for status in sorted({str(item.get("status")) for item in results})
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_ontology_cache",
        description="Download and parse configured OWL ontologies into JSON caches.",
    )
    parser.add_argument("--timeout", type=int, default=2700)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--out-prefix", default=None)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument(
        "--rag-index",
        action="store_true",
        help="Build persistent semantic indexes after caching ontology JSON.",
    )
    parser.add_argument(
        "--force-framework",
        action="append",
        default=[],
        help="Framework id to redownload/reparse. May be passed more than once.",
    )
    args = parser.parse_args(argv)

    manifest = build_ontology_cache(
        out_dir=args.out_dir,
        prefix=args.out_prefix,
        timeout=args.timeout,
        force_frameworks=args.force_framework,
        max_workers=args.max_workers,
        rag_index=args.rag_index,
    )
    print(f"manifest: {manifest['manifest_path']}")
    print(f"log: {manifest['log_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
