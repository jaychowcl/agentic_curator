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
            "url": "http://www.ebi.ac.uk/efo/efo.owl",
            "version": "v3.91.0",
        }
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
