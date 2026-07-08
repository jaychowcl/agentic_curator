from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS
from rdflib.term import BNode, Identifier


DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
OBO = Namespace("http://purl.obolibrary.org/obo/")
OBO_IN_OWL = Namespace("http://www.geneontology.org/formats/oboInOwl#")


class Owl2jsonParseError(ValueError):
    """Raised when an OWL file cannot be parsed as RDF/XML."""


class Owl2json:
    """Convert an RDF/XML OWL ontology into term-centric JSON."""

    def __init__(self, owl_path: str | Path) -> None:
        self.owl_path = Path(owl_path)

    def parse(self) -> dict[str, Any]:
        self._validate_rdf_xml_candidate()
        graph = self._parse_graph()
        return {
            "ontology": self._extract_ontology_metadata(graph),
            "terms": self._extract_terms(graph),
        }

    def write_json(self, output_path: str | Path) -> Path:
        target = Path(output_path)
        target.write_text(
            json.dumps(self.parse(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return target

    def _validate_rdf_xml_candidate(self) -> None:
        prefix = self.owl_path.read_bytes()[:4096].lstrip()
        sniffed = prefix.decode("ascii", errors="ignore").lstrip().lower()
        if sniffed.startswith("<?xml"):
            _, _, sniffed = sniffed.partition("?>")
            sniffed = sniffed.lstrip()
        if sniffed.startswith("<!doctype html") or sniffed.startswith("<html"):
            raise Owl2jsonParseError(
                f"{self.owl_path} does not look like RDF/XML; found HTML content."
            )

    def _parse_graph(self) -> Graph:
        graph = Graph()
        try:
            graph.parse(self.owl_path, format="xml")
        except Exception as exc:
            raise Owl2jsonParseError(
                f"Could not parse {self.owl_path} as RDF/XML OWL."
            ) from exc
        return graph

    def _extract_ontology_metadata(self, graph: Graph) -> dict[str, str | None]:
        ontology = self._first_subject(graph, RDF.type, OWL.Ontology)
        if ontology is None:
            return {
                "iri": None,
                "version_iri": None,
                "title": None,
                "description": None,
                "version": None,
                "license": None,
            }

        return {
            "iri": str(ontology),
            "version_iri": self._first_resource(graph, ontology, OWL.versionIRI),
            "title": self._first_literal(graph, ontology, DC.title)
            or self._first_literal(graph, ontology, DCTERMS.title),
            "description": self._first_literal(graph, ontology, DC.description)
            or self._first_literal(graph, ontology, DCTERMS.description),
            "version": self._first_literal(graph, ontology, OWL.versionInfo),
            "license": self._first_value(graph, ontology, DCTERMS.license)
            or self._first_value(graph, ontology, DC.license),
        }

    def _extract_terms(self, graph: Graph) -> dict[str, Any]:
        subjects = sorted(
            subject
            for subject in graph.subjects(RDF.type, OWL.Class)
            if not isinstance(subject, BNode)
        )
        terms = [self._extract_term(graph, subject) for subject in subjects]
        by_accession = {
            term["accession"]: term for term in terms if term["accession"] is not None
        }
        by_iri = {term["iri"]: term for term in terms}
        by_label: dict[str, list[dict[str, Any]]] = {}
        for term in terms:
            if term["title"] is None:
                continue
            by_label.setdefault(term["title"], []).append(term)

        return {
            "accession": by_accession,
            "iri": by_iri,
            "label": by_label,
        }

    def _extract_term(self, graph: Graph, subject: Identifier) -> dict[str, Any]:
        iri = str(subject)
        accession = self._term_accession(graph, subject)
        parent_iris = self._resource_values(graph, subject, RDFS.subClassOf)
        replaced_by = self._first_value(graph, subject, OBO.IAO_0100001)
        if replaced_by:
            replaced_by = self._accession_from_iri(replaced_by) or replaced_by

        return {
            "iri": iri,
            "accession": accession,
            "title": self._first_literal(graph, subject, RDFS.label),
            "description": self._first_literal(graph, subject, OBO.IAO_0000115),
            "parents": [
                self._accession_from_iri(parent_iri) or parent_iri
                for parent_iri in parent_iris
            ],
            "parent_iris": parent_iris,
            "synonyms": {
                "exact": self._literal_values(
                    graph, subject, OBO_IN_OWL.hasExactSynonym
                ),
                "related": self._literal_values(
                    graph, subject, OBO_IN_OWL.hasRelatedSynonym
                ),
                "broad": self._literal_values(
                    graph, subject, OBO_IN_OWL.hasBroadSynonym
                ),
                "narrow": self._literal_values(
                    graph, subject, OBO_IN_OWL.hasNarrowSynonym
                ),
            },
            "xrefs": self._literal_values(graph, subject, OBO_IN_OWL.hasDbXref),
            "subsets": self._value_strings(graph, subject, OBO_IN_OWL.inSubset),
            "deprecated": self._is_deprecated(graph, subject),
            "replaced_by": replaced_by,
            "properties": self._unmapped_literal_properties(graph, subject),
        }

    def _term_accession(self, graph: Graph, subject: Identifier) -> str | None:
        explicit_id = self._first_literal(graph, subject, OBO_IN_OWL.id)
        if explicit_id:
            return explicit_id
        return self._accession_from_iri(str(subject))

    def _unmapped_literal_properties(
        self, graph: Graph, subject: Identifier
    ) -> dict[str, list[str]]:
        mapped_predicates = {
            RDF.type,
            RDFS.label,
            RDFS.subClassOf,
            OWL.deprecated,
            OBO.IAO_0000115,
            OBO.IAO_0100001,
            OBO_IN_OWL.hasBroadSynonym,
            OBO_IN_OWL.hasDbXref,
            OBO_IN_OWL.hasExactSynonym,
            OBO_IN_OWL.hasNarrowSynonym,
            OBO_IN_OWL.hasRelatedSynonym,
            OBO_IN_OWL.id,
            OBO_IN_OWL.inSubset,
        }
        properties: dict[str, list[str]] = {}
        for predicate, obj in graph.predicate_objects(subject):
            if predicate in mapped_predicates or not isinstance(obj, Literal):
                continue
            properties.setdefault(str(predicate), []).append(str(obj))

        return {
            predicate: sorted(values)
            for predicate, values in sorted(properties.items(), key=lambda item: item[0])
        }

    @staticmethod
    def _first_subject(
        graph: Graph, predicate: URIRef, obj: URIRef
    ) -> Identifier | None:
        return next(graph.subjects(predicate, obj), None)

    @staticmethod
    def _first_literal(
        graph: Graph, subject: Identifier, predicate: URIRef
    ) -> str | None:
        for obj in graph.objects(subject, predicate):
            if isinstance(obj, Literal):
                return str(obj)
        return None

    @staticmethod
    def _first_resource(
        graph: Graph, subject: Identifier, predicate: URIRef
    ) -> str | None:
        for obj in graph.objects(subject, predicate):
            if isinstance(obj, URIRef):
                return str(obj)
        return None

    @staticmethod
    def _first_value(
        graph: Graph, subject: Identifier, predicate: URIRef
    ) -> str | None:
        for obj in graph.objects(subject, predicate):
            return str(obj)
        return None

    @staticmethod
    def _literal_values(
        graph: Graph, subject: Identifier, predicate: URIRef
    ) -> list[str]:
        return sorted(str(obj) for obj in graph.objects(subject, predicate))

    @staticmethod
    def _resource_values(
        graph: Graph, subject: Identifier, predicate: URIRef
    ) -> list[str]:
        return sorted(
            str(obj)
            for obj in graph.objects(subject, predicate)
            if isinstance(obj, URIRef)
        )

    @staticmethod
    def _value_strings(
        graph: Graph, subject: Identifier, predicate: URIRef
    ) -> list[str]:
        return sorted(str(obj) for obj in graph.objects(subject, predicate))

    @staticmethod
    def _is_deprecated(graph: Graph, subject: Identifier) -> bool:
        for obj in graph.objects(subject, OWL.deprecated):
            value = str(obj).strip().lower()
            if value in {"true", "1"}:
                return True
        return False

    @staticmethod
    def _accession_from_iri(iri: str) -> str | None:
        local_id = (
            iri.rstrip("/").rsplit("/", maxsplit=1)[-1].rsplit("#", maxsplit=1)[-1]
        )
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)_(.+)", local_id)
        if not match:
            return None
        return f"{match.group(1)}:{match.group(2)}"
