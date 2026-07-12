# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Iterable, Iterator
from urllib.parse import urlparse

import requests

from agentic_curator.curators.ontology_harmonizer.normalization import (
    harmonize_key as normalize_key,
)
from agentic_curator.curators.ontology_harmonizer.owl2json import Owl2json
from agentic_curator.curators.ontology_harmonizer.owl2sqlite import Owl2SqliteTerms
from agentic_curator.curators.ontology_harmonizer.request_policy import RequestPolicy, request_with_retry


OntologyFrameworkConfig = dict[str, dict[str, Any]]
LOGGER = logging.getLogger(__name__)


class OntologyCacheError(RuntimeError):
    """Raised after an eager ontology cache build has attempted every framework."""

    def __init__(self, results: dict[str, Any]):
        self.results = results
        failed = ", ".join(results.get("failed", []))
        super().__init__(f"Failed to cache ontology frameworks: {failed}")


class OntoStore:
    """Store for downloading, parsing, and serving ontologies."""

    DEFAULT_ONTOLOGY_FRAMEWORKS: OntologyFrameworkConfig = {
        "efo": {
            "title": "Experimental Factor Ontology",
            "url": "http://www.ebi.ac.uk/efo/efo.owl",
            "version": None,
            "description": "The Experimental Factor Ontology (EFO) provides a systematic description of many experimental variables available in EBI databases, and for projects such as the NHGRI-EBI GWAS catalog. It combines parts of several biological ontologies, such as UBERON anatomy, ChEBI chemical compounds, Cell Ontology and the Monarch Disease Ontology (MONDO). The scope of EFO is to support the annotation, analysis and visualization of data handled by many groups at the EBI and as the core ontology for Open Targets.",
        },
        "mondo": {
            "title": "Mondo Disease Ontology",
            "url": "http://purl.obolibrary.org/obo/mondo/releases/2026-06-02/mondo-international.owl",
            "version": "2026-06-02",
            "description": "A semi-automatically constructed ontology that merges in multiple disease resources to yield a coherent merged ontology.",
        },
        "uberon": {
            "title": "Uber-anatomy ontology",
            "url": "http://purl.obolibrary.org/obo/uberon.owl",
            "version": None,
            "description": "Uberon is an integrated cross-species anatomy ontology representing a variety of entities classified according to traditional anatomical criteria such as structure, function and developmental lineage. The ontology includes comprehensive relationships to taxon-specific anatomical ontologies, allowing integration of functional, phenotype and expression data.",
        },
        "hp": {
            "title": "Human Phenotype Ontology",
            "url": "http://purl.obolibrary.org/obo/hp/releases/2026-06-23/hp-international.owl",
            "version": "2026-06-23",
            "description": "The Human Phenotype Ontology (HPO) provides a standardized vocabulary of phenotypic abnormalities and clinical features encountered in human disease.",
        },
        "cl": {
            "title": "Cell Ontology",
            "url": "http://purl.obolibrary.org/obo/cl/releases/2026-06-08/cl.owl",
            "version": "2026-06-08",
            "description": "An ontology of cell types.",
        },
        "chebi": {
            "title": "Chemical Entities of Biological Interest",
            "url": "http://purl.obolibrary.org/obo/chebi/252/chebi.owl",
            "version": "252",
            "description": "A structured classification of molecular entities of biological interest focusing on 'small' chemical compounds.",
        },
        "pato": {
            "title": "PATO - the Phenotype And Trait Ontology",
            "url": "http://purl.obolibrary.org/obo/pato/releases/2025-05-14/pato.owl",
            "version": "2025-05-14",
            "description": "An ontology of phenotypic qualities (properties, attributes or characteristics).",
        },
        "obi": {
            "title": "Ontology for Biomedical Investigations",
            "url": "http://purl.obolibrary.org/obo/obi/2026-05-08/obi.owl",
            "version": "2026-05-08",
            "description": "An ontology for representing biomedical investigations, including study designs, the collection and preparation of the targets of investigation, assays, instrumentation and reagents used, as well as the data generated and the types of analysis performed on the data to reach conclusions, and their documentation.",
        },
        "snomed": {
            "title": "SNOMED CT (International Edition)",
            "url": "http://snomed.info/sct/900000000000207008/version/20251017",
            "version": "20251017",
            "description": "SNOMED CT or SNOMED Clinical Terms is a systematically organized computer processable collection of medical terms providing codes, terms, synonyms and definitions used in clinical documentation and reporting.",
        },
        "ncit": {
            "title": "NCI Thesaurus OBO Edition",
            "url": "http://purl.obolibrary.org/obo/ncit/releases/2026-03-19/ncit.owl",
            "version": "26.02d",
            "description": "NCI Thesaurus (NCIt)is a reference terminology that includes broad coverage of the cancer domain, including cancer related diseases, findings and abnormalities. The NCIt OBO Edition aims to increase integration of the NCIt with OBO Library ontologies. NCIt OBO Edition releases should be considered experimental.",
        },
        "ncbitaxon": {
            "title": "NCBI organismal classification",
            "url": "http://purl.obolibrary.org/obo/ncbitaxon/2026-05-13/ncbitaxon.owl",
            "version": "2026-05-13",
            "description": "An ontology representation of the NCBI organismal taxonomy",
        },
    }
    DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent / "ontology_frameworks"
    SQLITE_SCHEMA_VERSION = "3"
    LOOKUP_INDEXES = ("label", "id", "accession", "iri")

    def __init__(
        self,
        ontology_frameworks: OntologyFrameworkConfig | None = None,
        fields: dict[str, dict[str, Any]] | None = None,
        storage_dir: str | Path | None = None,
        sqlite_path: str | Path | None = None,
        request_policy: RequestPolicy | None = None,
    ) -> None:
        self.storage_dir = (
            self.DEFAULT_STORAGE_DIR if storage_dir is None else Path(storage_dir)
        )
        self.ontology_frameworks = self._normalize_frameworks(
            {
                **self.DEFAULT_ONTOLOGY_FRAMEWORKS,
                **(ontology_frameworks or {}),
            }
        )
        self.sqlite_path = (
            self.storage_dir / "sqlite" / "ontologies.sqlite3"
            if sqlite_path is None
            else Path(sqlite_path)
        )
        self.request_policy = request_policy or RequestPolicy()
        with self._sqlite_connection():
            pass
        self.fields = self._load_persisted_fields()
        self.fields.update(self._normalize_fields(fields or {}))

    def configure_framework(
        self,
        name: str,
        *,
        url: str | None = None,
        path: str | Path | None = None,
        owl_path: str | Path | None = None,
        json_path: str | Path | None = None,
        version: str | None = None,
        title: str | None = None,
        description: str | None = None,
        remove: bool = False,
    ) -> None:
        LOGGER.info("Configuring ontology framework %s.", name)
        metadata = {
            "version": version,
            "title": title,
            "description": description,
        }
        if remove:
            if (
                url is not None
                or path is not None
                or owl_path is not None
                or json_path is not None
                or any(value is not None for value in metadata.values())
            ):
                raise ValueError(
                    "remove=True cannot be combined with url, path, or metadata."
                )
            del self.ontology_frameworks[name]
            LOGGER.info("Removed ontology framework %s.", name)
            return

        raw_framework: dict[str, Any] = {}
        if url is not None:
            raw_framework["url"] = url
        if path is not None:
            raw_framework["path"] = path
        if owl_path is not None:
            raw_framework["owl_path"] = owl_path
        if json_path is not None:
            raw_framework["json_path"] = json_path
        raw_framework.update(
            {key: value for key, value in metadata.items() if value is not None}
        )
        self.ontology_frameworks[name] = self._normalize_framework(
            name=name,
            framework=raw_framework,
        )
        LOGGER.debug("Configured ontology framework %s.", name)

    def add_url(
        self,
        name: str,
        url: str,
        *,
        owl_path: str | Path | None = None,
        json_path: str | Path | None = None,
        version: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> None:
        LOGGER.info("Adding ontology framework URL %s.", name)
        self.configure_framework(
            name,
            url=url,
            owl_path=owl_path,
            json_path=json_path,
            version=version,
            title=title,
            description=description,
        )

    def add_urls(self, ontology_frameworks: OntologyFrameworkConfig) -> None:
        LOGGER.info("Adding %d ontology framework URLs/configs.", len(ontology_frameworks))
        self.ontology_frameworks.update(
            self._normalize_frameworks(ontology_frameworks)
        )

    def _normalize_frameworks(
        self,
        ontology_frameworks: OntologyFrameworkConfig,
    ) -> OntologyFrameworkConfig:
        return {
            name: self._normalize_framework(name=name, framework=framework)
            for name, framework in ontology_frameworks.items()
        }

    def _normalize_framework(
        self,
        *,
        name: str,
        framework: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(framework)
        url = normalized.get("url")
        configured_path = normalized.pop("path", None)
        configured_owl_path = normalized.get("owl_path")

        if url is not None:
            if configured_path is not None:
                raise ValueError("Configure exactly one of url or path.")
            if not isinstance(url, str) or not url:
                raise ValueError(f"Ontology framework {name!r} requires a string URL.")
            owl_path = configured_owl_path
            if owl_path is None:
                owl_path = self.storage_dir / self._filename_from_url(
                    name=name,
                    url=url,
                )
        else:
            owl_path = (
                configured_owl_path
                if configured_owl_path is not None
                else configured_path
            )
            if owl_path is None:
                raise ValueError(
                    f"Ontology framework {name!r} must configure exactly one of "
                    "url or path."
                )

        normalized["owl_path"] = self._path_value(
            value=owl_path,
            name=name,
            field="owl_path",
        )
        normalized["json_path"] = self._json_path_value(
            value=normalized.get("json_path"),
            owl_path=normalized["owl_path"],
            name=name,
        )
        return normalized

    def _normalize_fields(
        self,
        fields: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        return {
            self.harmonize_key(field): dict(metadata)
            for field, metadata in fields.items()
        }

    def get(self, name: str, force: bool = False) -> Path:
        LOGGER.info("Getting ontology framework %s.", name)
        owl_path = self._target_path(name)
        json_path = self._json_target_path(name)
        if json_path.exists() and not force:
            LOGGER.debug("Using cached ontology JSON %s.", json_path)
            return self._ensure_json_ontology_id(json_path, name)

        if force and self._is_url_framework(name):
            LOGGER.info("Redownloading ontology framework %s.", name)
            self._download_to_path(name, owl_path)
        elif not owl_path.exists():
            owl_path = self.download(name)

        json_path.parent.mkdir(parents=True, exist_ok=True)
        result = Owl2json(owl_path).write_json(json_path, ontology_id=name)
        LOGGER.info("Wrote ontology JSON for %s.", name)
        return result

    def lookup(self, label: str, ontology_id: str) -> list[dict[str, Any]]:
        return self.lookup_with_metadata(label, ontology_id)["hits"]

    def lookup_with_metadata(
        self,
        label: str,
        ontology_id: str,
    ) -> dict[str, Any]:
        LOGGER.info("Looking up ontology label.")
        self.index_framework(ontology_id)
        result = self.lookup_exact(label, ontology_id, ensure_index=False)
        if result:
            return {"match_type": "exact", "hits": result, "ranking": []}

        self._ensure_fts_framework(ontology_id)
        query = self._fts_query(label)
        if not query:
            return {"match_type": "none", "hits": [], "ranking": []}
        with self._sqlite_connection() as connection:
            rows = connection.execute(
                """
                SELECT terms.payload, term_search.term_key, bm25(term_search)
                FROM term_search
                JOIN terms
                  ON terms.ontology_id = term_search.ontology_id
                 AND terms.term_key = term_search.term_key
                WHERE term_search MATCH ? AND term_search.ontology_id = ?
                ORDER BY bm25(term_search)
                LIMIT 25
                """,
                (query, ontology_id),
            ).fetchall()
        fts_hits = self._dedupe_lookup_hits(
            self._metadata_with_ontology_id(
                [json.loads(row[0]) for row in rows], ontology_id
            )
        )
        ranking = [
            {"term_key": row[1], "score": float(row[2])}
            for row in rows[: len(fts_hits)]
        ]
        LOGGER.info(
            "Ontology label lookup returned %d hits for %s.",
            len(fts_hits),
            ontology_id,
        )
        return {
            "match_type": "fts" if fts_hits else "none",
            "hits": fts_hits,
            "ranking": ranking,
        }

    def lookup_exact(
        self,
        label: str,
        ontology_id: str,
        *,
        ensure_index: bool = True,
    ) -> list[dict[str, Any]]:
        if ensure_index:
            self.index_framework(ontology_id)
        lookup_label = self.harmonize_key(label)
        with self._sqlite_connection() as connection:
            rows = connection.execute(
                """
                SELECT terms.payload
                FROM lookup_entries
                JOIN terms
                  ON terms.ontology_id = lookup_entries.ontology_id
                 AND terms.term_key = lookup_entries.term_key
                WHERE lookup_entries.ontology_id = ?
                  AND lookup_entries.lookup_key = ?
                ORDER BY lookup_entries.index_rank, lookup_entries.source_order
                """,
                (ontology_id, lookup_label),
            ).fetchall()
        hits = [json.loads(row[0]) for row in rows]
        result = self._dedupe_lookup_hits(
            self._metadata_with_ontology_id(hits, ontology_id)
        )
        return result

    def index_framework(self, ontology_id: str, force: bool = False) -> Path:
        """Add or refresh one configured framework in the shared SQLite index."""
        json_path = self._json_target_path(ontology_id)
        if not json_path.exists():
            return self.index_owl_framework(ontology_id, force=force)
        stat = json_path.stat()

        with self._sqlite_connection() as connection:
            if not force and self._sqlite_framework_is_current(
                connection, ontology_id, json_path, stat, source_kind="json"
            ):
                return self.sqlite_path

        ontology = self._load_ontology_json(json_path)
        terms = ontology.get("terms", {})
        if not isinstance(terms, dict):
            terms = {}

        with self._sqlite_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "DELETE FROM frameworks WHERE ontology_id = ?", (ontology_id,)
                )
                connection.execute(
                    "DELETE FROM term_search WHERE ontology_id = ?", (ontology_id,)
                )
                connection.execute(
                    """
                    INSERT INTO frameworks(
                        ontology_id, json_path, json_size, json_mtime_ns,
                        indexed_at, source_kind
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 'json')
                    """,
                    (
                        ontology_id,
                        str(json_path.resolve()),
                        stat.st_size,
                        stat.st_mtime_ns,
                    ),
                )
                self._insert_lookup_terms(connection, ontology_id, terms)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        LOGGER.info("Indexed ontology framework %s in SQLite.", ontology_id)
        return self.sqlite_path

    def index_owl_framework(
        self,
        ontology_id: str,
        force: bool = False,
        batch_size: int = 1_000,
    ) -> Path:
        """Stream one OWL framework through staging SQLite into the shared index."""
        owl_path = self._target_path(ontology_id)
        if force and self._is_url_framework(ontology_id):
            self._download_to_path(ontology_id, owl_path)
        elif not owl_path.exists():
            owl_path = self.download(ontology_id)
        stat = owl_path.stat()

        with self._sqlite_connection() as connection:
            if not force and self._sqlite_framework_is_current(
                connection, ontology_id, owl_path, stat, source_kind="owl"
            ):
                return self.sqlite_path

        staging_path = (
            self.storage_dir / "sqlite" / "staging" / f"{ontology_id}.sqlite3"
        )
        parser = Owl2SqliteTerms(owl_path, staging_path)
        try:
            parser.stage(batch_size=max(batch_size, 1))
            with self._sqlite_connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        "DELETE FROM frameworks WHERE ontology_id = ?", (ontology_id,)
                    )
                    connection.execute(
                        "DELETE FROM term_search WHERE ontology_id = ?", (ontology_id,)
                    )
                    connection.execute(
                        """
                        INSERT INTO frameworks(
                            ontology_id, json_path, json_size, json_mtime_ns,
                            indexed_at, source_kind
                        ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 'owl')
                        """,
                        (
                            ontology_id,
                            str(owl_path.resolve()),
                            stat.st_size,
                            stat.st_mtime_ns,
                        ),
                    )
                    self._insert_streamed_terms(
                        connection,
                        ontology_id,
                        parser.iter_terms(),
                        batch_size=max(batch_size, 1),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        finally:
            parser.cleanup()

        LOGGER.info("Stream-indexed ontology framework %s in SQLite.", ontology_id)
        return self.sqlite_path

    def remove_indexed_framework(self, ontology_id: str) -> bool:
        """Remove one framework from SQLite while retaining its source caches."""
        with self._sqlite_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM frameworks WHERE ontology_id = ?", (ontology_id,)
            )
            connection.commit()
            return cursor.rowcount > 0

    def sync_sqlite(
        self,
        frameworks: Iterable[str] | None = None,
        force: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Index configured frameworks that currently have JSON or OWL caches."""
        names = list(self.ontology_frameworks if frameworks is None else frameworks)
        results: dict[str, dict[str, Any]] = {}
        for ontology_id in names:
            json_path = self._json_target_path(ontology_id)
            owl_path = self._target_path(ontology_id)
            if not json_path.exists() and not owl_path.exists():
                continue
            source_path = json_path if json_path.exists() else owl_path
            source_kind = "json" if json_path.exists() else "owl"
            was_current = False
            with self._sqlite_connection() as connection:
                was_current = self._sqlite_framework_is_current(
                    connection, ontology_id, source_path, source_path.stat(), source_kind
                )
            self.index_framework(ontology_id, force=force)
            with self._sqlite_connection() as connection:
                term_count = connection.execute(
                    "SELECT COUNT(*) FROM terms WHERE ontology_id = ?",
                    (ontology_id,),
                ).fetchone()[0]
                lookup_count = connection.execute(
                    "SELECT COUNT(*) FROM lookup_entries WHERE ontology_id = ?",
                    (ontology_id,),
                ).fetchone()[0]
            results[ontology_id] = {
                "status": "current" if was_current and not force else "indexed",
                "terms": term_count,
                "lookups": lookup_count,
            }
        return results

    def cache_all(
        self,
        frameworks: Iterable[str] | None = None,
        *,
        force: bool = False,
        force_frameworks: Iterable[str] = (),
        fail_on_error: bool = True,
    ) -> dict[str, Any]:
        """Materialize and index every selected active ontology framework."""
        names = list(self.ontology_frameworks if frameworks is None else frameworks)
        results: dict[str, Any] = {
            "sqlite_path": str(self.sqlite_path),
            "frameworks": {},
            "successful": [],
            "failed": [],
        }

        selectively_forced = set(force_frameworks)
        unknown = selectively_forced.difference(names)
        if unknown:
            raise KeyError(f"Unknown selected ontology frameworks: {sorted(unknown)}")

        LOGGER.info("Ontology cache started frameworks=%s force=%s.", len(names), force)
        for position, name in enumerate(names, start=1):
            started = time.monotonic()
            framework_result: dict[str, Any] = {"framework": name}
            LOGGER.info(
                "Ontology cache progress framework=%s position=%s total=%s.",
                name,
                position,
                len(names),
            )
            try:
                owl_path = self._target_path(name)
                json_path = self._json_target_path(name)
                had_owl = owl_path.exists()
                had_json = json_path.exists()
                force_this = force or name in selectively_forced
                if had_json and not force_this:
                    self.index_framework(name)
                    source_kind = "json"
                else:
                    self.index_owl_framework(name, force=force_this)
                    source_kind = "owl"
                status = (
                    "force_rebuilt"
                    if force_this
                    else "cached_indexed"
                    if had_json
                    else "stream_indexed"
                    if had_owl
                    else "downloaded_stream_indexed"
                )
                framework_result.update(
                    {
                        "status": status,
                        "owl_path": str(owl_path),
                        "json_path": str(json_path) if json_path.exists() else None,
                        "owl_size": owl_path.stat().st_size if owl_path.exists() else None,
                        "json_size": json_path.stat().st_size if json_path.exists() else None,
                        "source_kind": source_kind,
                        "indexed": True,
                    }
                )
                results["successful"].append(name)
            except Exception as error:  # Continue so callers get a complete manifest.
                framework_result.update(
                    {
                        "status": "failed",
                        "indexed": False,
                        "error": repr(error),
                    }
                )
                results["failed"].append(name)
            framework_result["elapsed_seconds"] = round(
                time.monotonic() - started, 3
            )
            results["frameworks"][name] = framework_result
            LOGGER.info(
                "Ontology cache framework completed framework=%s status=%s elapsed_seconds=%s.",
                name,
                framework_result["status"],
                framework_result["elapsed_seconds"],
            )

        if results["failed"] and fail_on_error:
            raise OntologyCacheError(results)
        LOGGER.info(
            "Ontology cache completed successful=%s failed=%s.",
            len(results["successful"]),
            len(results["failed"]),
        )
        return results

    @staticmethod
    def _load_ontology_json(json_path: Path) -> dict[str, Any]:
        return json.loads(json_path.read_text(encoding="utf-8"))

    @contextmanager
    def _sqlite_connection(self) -> Iterator[sqlite3.Connection]:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.sqlite_path, timeout=30)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS frameworks (
                    ontology_id TEXT PRIMARY KEY,
                    json_path TEXT NOT NULL,
                    json_size INTEGER NOT NULL,
                    json_mtime_ns INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    source_kind TEXT NOT NULL DEFAULT 'json'
                );
                CREATE TABLE IF NOT EXISTS terms (
                    ontology_id TEXT NOT NULL,
                    term_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (ontology_id, term_key),
                    FOREIGN KEY (ontology_id) REFERENCES frameworks(ontology_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS lookup_entries (
                    ontology_id TEXT NOT NULL,
                    index_name TEXT NOT NULL,
                    index_rank INTEGER NOT NULL,
                    lookup_key TEXT NOT NULL,
                    term_key TEXT NOT NULL,
                    source_order INTEGER NOT NULL,
                    PRIMARY KEY (ontology_id, index_name, lookup_key, term_key),
                    FOREIGN KEY (ontology_id, term_key)
                        REFERENCES terms(ontology_id, term_key) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS lookup_entries_lookup
                    ON lookup_entries(
                        ontology_id, lookup_key, index_rank, source_order
                    );
                CREATE VIRTUAL TABLE IF NOT EXISTS term_search USING fts5(
                    ontology_id UNINDEXED,
                    term_key UNINDEXED,
                    title,
                    synonyms,
                    description,
                    identifiers,
                    tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TABLE IF NOT EXISTS field_registry (
                    field_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS field_aliases (
                    alias TEXT PRIMARY KEY,
                    field_id TEXT NOT NULL,
                    FOREIGN KEY (field_id) REFERENCES field_registry(field_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS external_response_cache (
                    provider TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (provider, operation, cache_key)
                );
                """
            )
            framework_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(frameworks)")
            }
            if "source_kind" not in framework_columns:
                connection.execute(
                    "ALTER TABLE frameworks ADD COLUMN "
                    "source_kind TEXT NOT NULL DEFAULT 'json'"
                )
            connection.execute(
                "INSERT OR REPLACE INTO schema_metadata(key, value) VALUES (?, ?)",
                ("schema_version", self.SQLITE_SCHEMA_VERSION),
            )
            connection.commit()
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _sqlite_framework_is_current(
        connection: sqlite3.Connection,
        ontology_id: str,
        source_path: Path,
        stat: Any,
        source_kind: str = "json",
    ) -> bool:
        row = connection.execute(
            """
            SELECT json_path, json_size, json_mtime_ns, source_kind
            FROM frameworks WHERE ontology_id = ?
            """,
            (ontology_id,),
        ).fetchone()
        return row == (
            str(source_path.resolve()), stat.st_size, stat.st_mtime_ns, source_kind
        )

    def _insert_streamed_terms(
        self,
        connection: sqlite3.Connection,
        ontology_id: str,
        terms: Iterable[dict[str, Any]],
        *,
        batch_size: int,
    ) -> None:
        term_rows: list[tuple[str, str, str]] = []
        lookup_rows: list[tuple[str, str, int, str, str, int]] = []
        fts_rows: list[tuple[str, str, str, str, str, str]] = []

        def flush() -> None:
            connection.executemany(
                "INSERT INTO terms VALUES (?, ?, ?)", term_rows
            )
            connection.executemany(
                "INSERT INTO lookup_entries VALUES (?, ?, ?, ?, ?, ?)", lookup_rows
            )
            connection.executemany(
                "INSERT INTO term_search VALUES (?, ?, ?, ?, ?, ?)", fts_rows
            )
            term_rows.clear()
            lookup_rows.clear()
            fts_rows.clear()

        for source_order, term in enumerate(terms):
            payload = json.dumps(
                term, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            term_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            term_rows.append((ontology_id, term_key, payload))
            fts_rows.append(self._fts_row(ontology_id, term_key, term))
            values = {
                "label": term.get("title"),
                "id": term.get("accession"),
                "accession": term.get("accession"),
                "iri": term.get("iri"),
            }
            for index_rank, index_name in enumerate(self.LOOKUP_INDEXES):
                value = values[index_name]
                if value is None:
                    continue
                lookup_rows.append(
                    (
                        ontology_id,
                        index_name,
                        index_rank,
                        self.harmonize_key(value),
                        term_key,
                        source_order,
                    )
                )
            if len(term_rows) >= batch_size:
                flush()
        if term_rows:
            flush()

    def _insert_lookup_terms(
        self,
        connection: sqlite3.Connection,
        ontology_id: str,
        indexes: dict[str, Any],
    ) -> None:
        term_rows: list[tuple[str, str, str]] = []
        lookup_rows: list[tuple[str, str, int, str, str, int]] = []
        fts_rows: list[tuple[str, str, str, str, str, str]] = []
        indexed_terms: set[str] = set()

        def flush() -> None:
            connection.executemany(
                """
                INSERT OR IGNORE INTO terms(ontology_id, term_key, payload)
                VALUES (?, ?, ?)
                """,
                term_rows,
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO lookup_entries(
                    ontology_id, index_name, index_rank, lookup_key,
                    term_key, source_order
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                lookup_rows,
            )
            connection.executemany(
                """
                INSERT INTO term_search(
                    ontology_id, term_key, title, synonyms, description, identifiers
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                fts_rows,
            )
            term_rows.clear()
            lookup_rows.clear()
            fts_rows.clear()

        for index_rank, index_name in enumerate(self.LOOKUP_INDEXES):
            index = indexes.get(index_name, {})
            if not isinstance(index, dict):
                continue
            for lookup_key, raw_hits in index.items():
                for source_order, hit in enumerate(self._lookup_value_hits(raw_hits)):
                    if not isinstance(hit, dict):
                        continue
                    payload = json.dumps(
                        hit, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    )
                    term_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                    term_rows.append((ontology_id, term_key, payload))
                    if term_key not in indexed_terms:
                        indexed_terms.add(term_key)
                        fts_rows.append(self._fts_row(ontology_id, term_key, hit))
                    lookup_rows.append(
                        (
                            ontology_id,
                            index_name,
                            index_rank,
                            str(lookup_key),
                            term_key,
                            source_order,
                        )
                    )
                    if len(lookup_rows) >= 5_000:
                        flush()
        if lookup_rows:
            flush()

    def _ensure_fts_framework(self, ontology_id: str) -> None:
        with self._sqlite_connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM term_search WHERE ontology_id = ? LIMIT 1",
                (ontology_id,),
            ).fetchone()
            if exists:
                return
            rows = connection.execute(
                "SELECT term_key, payload FROM terms WHERE ontology_id = ?",
                (ontology_id,),
            )
            batch = []
            for term_key, payload in rows:
                hit = json.loads(payload)
                batch.append(self._fts_row(ontology_id, term_key, hit))
                if len(batch) >= 5_000:
                    connection.executemany(
                        "INSERT INTO term_search VALUES (?, ?, ?, ?, ?, ?)", batch
                    )
                    batch.clear()
            if batch:
                connection.executemany(
                    "INSERT INTO term_search VALUES (?, ?, ?, ?, ?, ?)", batch
                )
            connection.commit()

    @staticmethod
    def _fts_row(
        ontology_id: str,
        term_key: str,
        hit: dict[str, Any],
    ) -> tuple[str, str, str, str, str, str]:
        synonyms = hit.get("synonyms", {})
        if isinstance(synonyms, dict):
            synonym_values = [
                str(value)
                for values in synonyms.values()
                if isinstance(values, list)
                for value in values
            ]
        elif isinstance(synonyms, list):
            synonym_values = [str(value) for value in synonyms]
        else:
            synonym_values = [str(synonyms)] if synonyms else []
        description = hit.get("description", [])
        if isinstance(description, list):
            description_text = " ".join(str(value) for value in description)
        else:
            description_text = str(description or "")
        identifiers = " ".join(
            str(hit.get(key) or "") for key in ("id", "accession", "iri")
        )
        return (
            ontology_id,
            term_key,
            str(hit.get("title") or ""),
            " ".join(synonym_values),
            description_text,
            identifiers,
        )

    @staticmethod
    def _fts_query(value: Any) -> str:
        tokens = re.findall(r"[\w]+", str(value).lower(), flags=re.UNICODE)
        return " OR ".join(f'"{token}"*' for token in tokens if token)

    def lookup_fields(self, field: Any) -> Any:
        LOGGER.info("Looking up ontology field.")
        lookup_field = self.harmonize_key(field)
        for field_key, metadata in self.fields.items():
            candidates = [field_key]
            label = metadata.get("label")
            if label is not None:
                candidates.append(label)
            aliases = metadata.get("aliases", [])
            if isinstance(aliases, list):
                candidates.extend(aliases)

            if lookup_field in {
                self.harmonize_key(candidate) for candidate in candidates
            }:
                LOGGER.info("Ontology field lookup matched %s.", field_key)
                return {"field": field_key, **metadata}

        LOGGER.info("Ontology field lookup missed.")
        return False

    def _load_persisted_fields(self) -> dict[str, dict[str, Any]]:
        with self._sqlite_connection() as connection:
            rows = connection.execute(
                "SELECT field_id, payload, review_status FROM field_registry"
            ).fetchall()
        fields = {}
        for field_id, payload, review_status in rows:
            metadata = json.loads(payload)
            metadata["review_status"] = review_status
            fields[field_id] = metadata
        return fields

    def list_fields(self, review_status: str | None = None) -> list[dict[str, Any]]:
        values = []
        for field_id in sorted(self.fields):
            item = {"field": field_id, **self.fields[field_id]}
            if review_status is None or item.get("review_status") == review_status:
                values.append(item)
        return values

    def get_field(self, field_id: str) -> dict[str, Any] | None:
        key = self.harmonize_key(field_id)
        metadata = self.fields.get(key)
        return None if metadata is None else {"field": key, **metadata}

    def add_field(
        self,
        field_id: str,
        metadata: dict[str, Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        key = self.harmonize_key(field_id)
        if not key:
            raise ValueError("field_id cannot be empty.")
        if key in self.fields and not replace:
            raise ValueError(f"Field {key!r} already exists.")
        normalized = dict(metadata)
        aliases = [str(alias) for alias in normalized.pop("aliases", []) if str(alias)]
        alias_keys = [self.harmonize_key(alias) for alias in aliases]
        status = str(normalized.pop("review_status", "unreviewed"))
        self._validate_field_metadata(normalized, status)
        now = time.time()
        with self._sqlite_connection() as connection:
            for alias in alias_keys:
                owner = connection.execute(
                    "SELECT field_id FROM field_aliases WHERE alias = ?", (alias,)
                ).fetchone()
                if owner and owner[0] != key:
                    raise ValueError(f"Field alias {alias!r} already belongs to {owner[0]!r}.")
            created = connection.execute(
                "SELECT created_at FROM field_registry WHERE field_id = ?", (key,)
            ).fetchone()
            connection.execute(
                """
                INSERT OR REPLACE INTO field_registry(
                    field_id, payload, review_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    key,
                    json.dumps({**normalized, "aliases": aliases}, sort_keys=True),
                    status,
                    created[0] if created else now,
                    now,
                ),
            )
            connection.execute("DELETE FROM field_aliases WHERE field_id = ?", (key,))
            connection.executemany(
                "INSERT INTO field_aliases(alias, field_id) VALUES (?, ?)",
                [(alias, key) for alias in alias_keys],
            )
            connection.commit()
        self.fields[key] = {**normalized, "aliases": aliases, "review_status": status}
        return {"field": key, **self.fields[key]}

    def update_field(self, field_id: str, **changes: Any) -> dict[str, Any]:
        current = self.get_field(field_id)
        if current is None:
            raise KeyError(field_id)
        current.pop("field")
        current.update(changes)
        return self.add_field(field_id, current, replace=True)

    def remove_field(self, field_id: str) -> bool:
        key = self.harmonize_key(field_id)
        with self._sqlite_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM field_registry WHERE field_id = ?", (key,)
            )
            connection.commit()
        self.fields.pop(key, None)
        return cursor.rowcount > 0

    def set_field_review_status(self, field_id: str, status: str) -> dict[str, Any]:
        return self.update_field(field_id, review_status=status)

    @staticmethod
    def _validate_field_metadata(metadata: dict[str, Any], status: str) -> None:
        if status not in {"unreviewed", "approved", "rejected"}:
            raise ValueError("review_status must be unreviewed, approved, or rejected.")
        for key in ("expected_ontologies", "allowed_modes"):
            value = metadata.get(key, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{key} must be a list of strings.")

    @staticmethod
    def _cache_key(parameters: Any) -> str:
        payload = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get_cached_response(
        self,
        provider: str,
        operation: str,
        parameters: Any,
        *,
        ttl_seconds: int,
        now: float | None = None,
        force_refresh: bool = False,
    ) -> Any:
        if force_refresh:
            return None
        current = time.time() if now is None else now
        with self._sqlite_connection() as connection:
            row = connection.execute(
                """
                SELECT response_json, created_at FROM external_response_cache
                WHERE provider = ? AND operation = ? AND cache_key = ?
                """,
                (provider, operation, self._cache_key(parameters)),
            ).fetchone()
        if row is None or current - row[1] > ttl_seconds:
            return None
        return json.loads(row[0])

    def set_cached_response(
        self,
        provider: str,
        operation: str,
        parameters: Any,
        response: Any,
        *,
        now: float | None = None,
    ) -> None:
        with self._sqlite_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO external_response_cache(
                    provider, operation, cache_key, response_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    operation,
                    self._cache_key(parameters),
                    json.dumps(response, ensure_ascii=False, default=str),
                    time.time() if now is None else now,
                ),
            )
            connection.commit()

    def clear_cached_responses(
        self,
        *,
        provider: str | None = None,
        operation: str | None = None,
    ) -> int:
        clauses = []
        values = []
        if provider is not None:
            clauses.append("provider = ?")
            values.append(provider)
        if operation is not None:
            clauses.append("operation = ?")
            values.append(operation)
        sql = "DELETE FROM external_response_cache"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._sqlite_connection() as connection:
            cursor = connection.execute(sql, values)
            connection.commit()
        return cursor.rowcount

    @staticmethod
    def harmonize_key(value: Any) -> str:
        return normalize_key(value)

    def _ensure_json_ontology_id(self, json_path: Path, ontology_id: str) -> Path:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        ontology = payload.get("ontology")
        if not isinstance(ontology, dict):
            payload["ontology"] = {"id": ontology_id}
        elif ontology.get("id") == ontology_id:
            return json_path
        else:
            ontology["id"] = ontology_id

        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return json_path

    def _metadata_with_ontology_id(self, metadata: Any, ontology_id: str) -> Any:
        if isinstance(metadata, list):
            return [
                self._metadata_with_ontology_id(item, ontology_id)
                for item in metadata
            ]
        if isinstance(metadata, dict):
            return {**metadata, "ontology_id": ontology_id}
        return metadata

    def _lookup_index(self, index: dict[str, Any], lookup_label: str) -> list[Any]:
        if lookup_label in index:
            return self._lookup_value_hits(index[lookup_label])

        return []

    def _lookup_value_hits(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return [value]

    def _dedupe_lookup_hits(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            key = self._lookup_hit_key(hit)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(hit)
        return deduped

    def _lookup_hit_key(self, hit: dict[str, Any]) -> str:
        for field in ("id", "accession", "iri"):
            value = hit.get(field)
            if value is not None:
                return f"{field}:{self.harmonize_key(value)}"
        return json.dumps(hit, sort_keys=True, default=str)

    def download(self, name: str) -> Path:
        LOGGER.info("Downloading ontology framework %s if needed.", name)
        target = self._target_path(name)
        if self._is_path_framework(name):
            if not target.exists():
                raise FileNotFoundError(target)
            LOGGER.debug("Using configured local ontology path %s.", target)
            return target

        if target.exists():
            LOGGER.debug("Using cached ontology OWL %s.", target)
            return target

        return self._download_to_path(name, target)

    def _download_to_path(self, name: str, target: Path) -> Path:
        LOGGER.info("Downloading ontology framework %s to %s.", name, target)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        url = self._framework_url(name)
        def operation():
            response = requests.get(url, timeout=self.request_policy.timeout_seconds)
            response.raise_for_status()
            return response

        response, _trace = request_with_retry(operation, self.request_policy)
        target.write_bytes(response.content)
        LOGGER.info("Downloaded ontology framework %s.", name)
        return target

    def _json_target_path(self, name: str) -> Path:
        framework = self.ontology_frameworks[name]
        json_path = framework["json_path"]
        if isinstance(json_path, Path):
            return json_path
        if isinstance(json_path, str) and json_path:
            return Path(json_path)
        raise ValueError(
            f"Ontology framework {name!r} requires a string or Path json_path."
        )

    def _target_path(self, name: str) -> Path:
        framework = self.ontology_frameworks[name]
        owl_path = framework["owl_path"]
        if isinstance(owl_path, Path):
            return owl_path
        if isinstance(owl_path, str) and owl_path:
            return Path(owl_path)
        raise ValueError(
            f"Ontology framework {name!r} requires a string or Path owl_path."
        )

    def _framework_url(self, name: str) -> str:
        framework = self.ontology_frameworks[name]
        url = framework.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError(f"Ontology framework {name!r} requires a string URL.")

        return url

    def _is_path_framework(self, name: str) -> bool:
        return "url" not in self.ontology_frameworks[name]

    def _is_url_framework(self, name: str) -> bool:
        return "url" in self.ontology_frameworks[name]

    @staticmethod
    def _path_value(*, value: Any, name: str, field: str) -> Path:
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value:
            return Path(value)
        raise ValueError(
            f"Ontology framework {name!r} requires a string or Path {field}."
        )

    def _json_path_value(
        self,
        *,
        value: Any,
        owl_path: Path,
        name: str,
    ) -> Path:
        if value is None:
            return self.storage_dir / "jsons" / f"{owl_path.stem}.json"
        return self._path_value(value=value, name=name, field="json_path")

    @staticmethod
    def _filename_from_url(*, name: str, url: str) -> str:
        filename = Path(urlparse(url).path).name
        if not filename:
            raise ValueError(
                f"Ontology framework {name!r} URL does not include a filename."
            )

        return filename
