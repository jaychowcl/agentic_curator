# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import sqlite3
from typing import Any

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF
from rdflib.parser import create_input_source
from rdflib.plugins.parsers.rdfxml import RDFXMLParser


class SQLiteTripleSink:
    """Bounded-memory RDFLib parser sink backed by a staging SQLite file."""

    def __init__(self, path: Path, batch_size: int = 5000):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.executescript(
            """
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            CREATE TABLE triples (
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_value TEXT NOT NULL,
                language TEXT NOT NULL,
                datatype TEXT NOT NULL
            );
            """
        )
        self.batch_size = batch_size
        self.rows: list[tuple[str, str, str, str, str, str]] = []

    def bind(self, prefix, namespace, override=False) -> None:
        del prefix, namespace, override

    def add(self, triple) -> None:
        subject, predicate, obj = triple
        if not isinstance(subject, URIRef):
            return
        if isinstance(obj, URIRef):
            object_type, value, language, datatype = "uri", str(obj), "", ""
        elif isinstance(obj, BNode):
            object_type, value, language, datatype = "bnode", str(obj), "", ""
        elif isinstance(obj, Literal):
            object_type = "literal"
            value = str(obj)
            language = str(obj.language or "")
            datatype = str(obj.datatype or "")
        else:
            return
        self.rows.append(
            (str(subject), str(predicate), object_type, value, language, datatype)
        )
        if len(self.rows) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.rows:
            return
        self.connection.executemany(
            "INSERT INTO triples VALUES (?, ?, ?, ?, ?, ?)", self.rows
        )
        self.connection.commit()
        self.rows.clear()

    def finish(self) -> None:
        self.flush()
        self.connection.executescript(
            """
            CREATE INDEX triples_subject ON triples(subject);
            CREATE INDEX triples_class ON triples(predicate, object_type, object_value);
            """
        )
        self.connection.commit()
        self.connection.close()


class Owl2SqliteTerms:
    """Parse RDF/XML to disk and stream URI-backed OWL class records."""

    def __init__(self, owl_path: str | Path, staging_path: str | Path):
        self.owl_path = Path(owl_path)
        self.staging_path = Path(staging_path)

    def stage(self, batch_size: int = 5000) -> None:
        self._remove_staging_files()
        sink = SQLiteTripleSink(self.staging_path, batch_size=batch_size)
        try:
            source = create_input_source(location=str(self.owl_path))
            RDFXMLParser().parse(source, sink)
            sink.finish()
        except Exception:
            sink.connection.close()
            self._remove_staging_files()
            raise

    def iter_terms(self) -> Iterator[dict[str, Any]]:
        connection = sqlite3.connect(self.staging_path)
        class_predicate = str(RDF.type)
        class_object = str(OWL.Class)
        rows = connection.execute(
            """
            SELECT t.subject, t.predicate, t.object_type, t.object_value
            FROM triples AS t
            JOIN (
                SELECT DISTINCT subject
                FROM triples
                WHERE predicate = ? AND object_type = 'uri' AND object_value = ?
            ) AS classes ON classes.subject = t.subject
            ORDER BY t.subject, t.predicate, t.object_value
            """,
            (class_predicate, class_object),
        )
        subject = None
        triples: list[tuple[str, str, str]] = []
        try:
            for row_subject, predicate, object_type, value in rows:
                if subject is not None and row_subject != subject:
                    yield self._term(subject, triples)
                    triples = []
                subject = row_subject
                triples.append((predicate, object_type, value))
            if subject is not None:
                yield self._term(subject, triples)
        finally:
            connection.close()

    def cleanup(self) -> None:
        self._remove_staging_files()

    def _remove_staging_files(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.staging_path}{suffix}")
            if path.exists():
                path.unlink()

    @staticmethod
    def _term(subject: str, triples: list[tuple[str, str, str]]) -> dict[str, Any]:
        from agentic_curator.curators.ontology_harmonizer.owl2json import Owl2json

        by_predicate: dict[str, list[tuple[str, str]]] = {}
        for predicate, object_type, value in triples:
            by_predicate.setdefault(predicate, []).append((object_type, value))

        def literals(predicate) -> list[str]:
            return sorted(
                {value for kind, value in by_predicate.get(str(predicate), []) if kind == "literal"}
            )

        def resources(predicate) -> list[str]:
            return sorted(
                {value for kind, value in by_predicate.get(str(predicate), []) if kind == "uri"}
            )

        from rdflib.namespace import DC, DCTERMS, RDFS
        from agentic_curator.curators.ontology_harmonizer.owl2json import OBO, OBO_IN_OWL

        accession_values = literals(OBO_IN_OWL.id)
        accession = accession_values[0] if accession_values else Owl2json._accession_from_iri(subject)
        parent_iris = resources(RDFS.subClassOf)
        replaced_values = resources(OBO.IAO_0100001) or literals(OBO.IAO_0100001)
        replaced_by = replaced_values[0] if replaced_values else None
        if replaced_by:
            replaced_by = Owl2json._accession_from_iri(replaced_by) or replaced_by
        mapped = {
            str(RDF.type), str(RDFS.label), str(RDFS.subClassOf), str(OWL.deprecated),
            str(OBO.IAO_0000115), str(OBO.IAO_0100001),
            str(OBO_IN_OWL.hasBroadSynonym), str(OBO_IN_OWL.hasDbXref),
            str(OBO_IN_OWL.hasExactSynonym), str(OBO_IN_OWL.hasNarrowSynonym),
            str(OBO_IN_OWL.hasRelatedSynonym), str(OBO_IN_OWL.id),
            str(OBO_IN_OWL.inSubset),
        }
        properties = {
            predicate: sorted({value for kind, value in values if kind == "literal"})
            for predicate, values in sorted(by_predicate.items())
            if predicate not in mapped and any(kind == "literal" for kind, _ in values)
        }
        labels = literals(RDFS.label)
        descriptions = literals(OBO.IAO_0000115)
        deprecated = {value.lower() for value in literals(OWL.deprecated)}
        return {
            "iri": subject,
            "accession": accession,
            "title": labels[0] if labels else None,
            "description": descriptions[0] if descriptions else None,
            "parents": [Owl2json._accession_from_iri(value) or value for value in parent_iris],
            "parent_iris": parent_iris,
            "synonyms": {
                "exact": literals(OBO_IN_OWL.hasExactSynonym),
                "related": literals(OBO_IN_OWL.hasRelatedSynonym),
                "broad": literals(OBO_IN_OWL.hasBroadSynonym),
                "narrow": literals(OBO_IN_OWL.hasNarrowSynonym),
            },
            "xrefs": literals(OBO_IN_OWL.hasDbXref),
            "subsets": resources(OBO_IN_OWL.inSubset) + literals(OBO_IN_OWL.inSubset),
            "deprecated": bool(deprecated.intersection({"true", "1"})),
            "replaced_by": replaced_by,
            "properties": properties,
        }
