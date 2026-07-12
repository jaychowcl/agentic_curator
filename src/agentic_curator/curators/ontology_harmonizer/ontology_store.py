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
import sqlite3
from typing import Any, Iterable, Iterator
from urllib.parse import urlparse

import requests

from agentic_curator.curators.ontology_harmonizer.normalization import (
    harmonize_key as normalize_key,
)
from agentic_curator.curators.ontology_harmonizer.owl2json import Owl2json


OntologyFrameworkConfig = dict[str, dict[str, Any]]
LOGGER = logging.getLogger(__name__)


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
    SQLITE_SCHEMA_VERSION = "1"
    LOOKUP_INDEXES = ("label", "id", "accession", "iri")

    def __init__(
        self,
        ontology_frameworks: OntologyFrameworkConfig | None = None,
        fields: dict[str, dict[str, Any]] | None = None,
        storage_dir: str | Path | None = None,
        sqlite_path: str | Path | None = None,
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
        self.fields = self._normalize_fields(fields or {})
        self.sqlite_path = (
            self.storage_dir / "sqlite" / "ontologies.sqlite3"
            if sqlite_path is None
            else Path(sqlite_path)
        )

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
        LOGGER.info("Looking up ontology label.")
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
        LOGGER.info(
            "Ontology label lookup returned %d hits for %s.",
            len(result),
            ontology_id,
        )
        return result

    def index_framework(self, ontology_id: str, force: bool = False) -> Path:
        """Add or refresh one configured framework in the shared SQLite index."""
        json_path = self._json_target_path(ontology_id)
        if not json_path.exists():
            json_path = self.get(ontology_id)
        stat = json_path.stat()

        with self._sqlite_connection() as connection:
            if not force and self._sqlite_framework_is_current(
                connection, ontology_id, json_path, stat
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
                    """
                    INSERT INTO frameworks(
                        ontology_id, json_path, json_size, json_mtime_ns, indexed_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
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
        """Index configured frameworks that currently have JSON caches."""
        names = list(self.ontology_frameworks if frameworks is None else frameworks)
        results: dict[str, dict[str, Any]] = {}
        for ontology_id in names:
            json_path = self._json_target_path(ontology_id)
            if not json_path.exists():
                continue
            was_current = False
            with self._sqlite_connection() as connection:
                was_current = self._sqlite_framework_is_current(
                    connection, ontology_id, json_path, json_path.stat()
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
                    indexed_at TEXT NOT NULL
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
                """
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
        json_path: Path,
        stat: Any,
    ) -> bool:
        row = connection.execute(
            """
            SELECT json_path, json_size, json_mtime_ns
            FROM frameworks WHERE ontology_id = ?
            """,
            (ontology_id,),
        ).fetchone()
        return row == (str(json_path.resolve()), stat.st_size, stat.st_mtime_ns)

    def _insert_lookup_terms(
        self,
        connection: sqlite3.Connection,
        ontology_id: str,
        indexes: dict[str, Any],
    ) -> None:
        term_rows: list[tuple[str, str, str]] = []
        lookup_rows: list[tuple[str, str, int, str, str, int]] = []

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
            term_rows.clear()
            lookup_rows.clear()

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
        response = requests.get(url, timeout=30)
        response.raise_for_status()
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
