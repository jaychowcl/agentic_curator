from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


OntologyFrameworkConfig = dict[str, dict[str, Any]]


class OntoStore:
    """Store for downloading, parsing, and serving ontologies."""

    DEFAULT_ONTOLOGY_FRAMEWORKS: OntologyFrameworkConfig = {
        "efo": {
            "title": "Experimental Factor Ontology",
            "url": "http://www.ebi.ac.uk/efo/releases/v3.91.0/efo.owl",
            "version": "3.91.0",
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
            "url": "http://purl.obolibrary.org/obo/uberon/releases/2026-06-19/uberon.owl",
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

    def __init__(
        self,
        ontology_frameworks: OntologyFrameworkConfig | None = None,
        storage_dir: str | Path | None = None,
    ) -> None:
        self.ontology_frameworks = dict(self.DEFAULT_ONTOLOGY_FRAMEWORKS)
        if ontology_frameworks:
            self.ontology_frameworks.update(ontology_frameworks)
        self.storage_dir = (
            self.DEFAULT_STORAGE_DIR if storage_dir is None else Path(storage_dir)
        )

    def add_url(self, name: str, url: str, version: str | None = None) -> None:
        framework: dict[str, Any] = {"url": url}
        if version is not None:
            framework["version"] = version
        self.ontology_frameworks[name] = framework

    def add_urls(self, ontology_frameworks: OntologyFrameworkConfig) -> None:
        self.ontology_frameworks.update(ontology_frameworks)

    def download(self, name: str) -> Path:
        url = self._framework_url(name)
        target = self.storage_dir / self._filename_from_url(name=name, url=url)
        if target.exists():
            return target

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        target.write_bytes(response.content)
        return target

    def _framework_url(self, name: str) -> str:
        framework = self.ontology_frameworks[name]
        url = framework.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError(f"Ontology framework {name!r} requires a string URL.")

        return url

    @staticmethod
    def _filename_from_url(*, name: str, url: str) -> str:
        filename = Path(urlparse(url).path).name
        if not filename:
            raise ValueError(
                f"Ontology framework {name!r} URL does not include a filename."
            )

        return filename
