from __future__ import annotations

import re
from typing import Any

import requests

from agentic_curator.curators.ontology_harmonizer.ontology_store import OntoStore


class PlaceholderStrategyHandler:
    """Base placeholder handler for ontology harmonization strategies."""

    strategy = ""
    reason = ""

    def handle(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, str]:
        del publication_context, ontostore

        result = {
            "strategy": self.strategy,
            "status": "placeholder",
            "decision": "false",
            "confidence": "none",
            "reason": self.reason,
        }
        target["ontology_strategy_result"] = result
        return result


class OlsClient:
    """Small client for the OLS4 search and ontology metadata API."""

    BASE_URL = "https://www.ebi.ac.uk/ols4/api"

    def __init__(self, *, base_url: str = BASE_URL, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(
        self,
        label: str,
        *,
        ontology_id: str | None = None,
        rows: int = 25,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"q": label, "rows": rows}
        if ontology_id:
            params["ontology"] = ontology_id

        response = requests.get(
            f"{self.base_url}/search",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        docs = payload.get("response", {}).get("docs", [])
        return docs if isinstance(docs, list) else []

    def ontology(self, ontology_id: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/ontologies/{ontology_id}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}


class NullSearchClient:
    """Deterministic no-op web search client used unless one is injected."""

    def search(self, query: str, *, max_results: int = 25) -> list[dict[str, Any]]:
        del query, max_results
        return []


class WebsearchStrategyHandler:
    strategy = "websearch"
    max_results = 25

    def __init__(
        self,
        *,
        ols_client: OlsClient | None = None,
        search_client: Any | None = None,
    ) -> None:
        self.ols_client = OlsClient() if ols_client is None else ols_client
        self.search_client = (
            NullSearchClient() if search_client is None else search_client
        )

    def handle(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
        del publication_context

        ontology_id = target.get("ontology_id")
        if not ontology_id:
            return self._not_harmonized(
                target,
                reason="No assigned ontology framework is available for websearch.",
                ols_hits=[],
                web_hits=[],
            )

        label = target.get("hz_label", target.get("pre_hz_label"))
        if not label:
            return self._not_harmonized(
                target,
                reason="No harmonized label is available for websearch.",
                ols_hits=[],
                web_hits=[],
            )

        restricted_docs = self.ols_client.search(
            str(label),
            ontology_id=str(ontology_id),
            rows=self.max_results,
        )
        restricted_hits = self._hits_from_docs(restricted_docs)
        if restricted_hits:
            return self._accept_first_hit(
                target,
                ontostore=ontostore,
                hits=restricted_hits,
                web_hits=[],
                reason="Restricted OLS search returned a usable ontology hit.",
            )

        unrestricted_docs = self.ols_client.search(
            str(label),
            ontology_id=None,
            rows=self.max_results,
        )
        unrestricted_hits = self._hits_from_docs(unrestricted_docs)
        web_hits = self.search_client.search(
            self._web_query(target),
            max_results=self.max_results,
        )[: self.max_results]
        if unrestricted_hits:
            return self._accept_first_hit(
                target,
                ontostore=ontostore,
                hits=unrestricted_hits,
                web_hits=web_hits,
                reason="Unrestricted OLS search returned a usable ontology hit.",
            )

        return self._not_harmonized(
            target,
            reason="No usable OLS ontology hit was found.",
            ols_hits=[],
            web_hits=web_hits,
        )

    def _accept_first_hit(
        self,
        target: dict[str, Any],
        *,
        ontostore: OntoStore,
        hits: list[dict[str, Any]],
        web_hits: list[dict[str, Any]],
        reason: str,
    ) -> dict[str, Any]:
        hit = hits[0]
        ontology_id = hit["ontology_id"]
        framework_config = self._framework_config(ontology_id)
        if framework_config is None:
            return self._not_harmonized(
                target,
                reason=(
                    "Could not resolve complete ontology framework metadata "
                    "for websearch."
                ),
                ols_hits=hits,
                web_hits=web_hits,
            )

        ontostore.configure_framework(
            framework_config["id"],
            url=framework_config["url"],
            title=framework_config["title"],
            description=framework_config["description"],
            version=framework_config["version"],
        )

        result = {
            "strategy": self.strategy,
            "status": "matched",
            "decision": self._hit_decision(hit),
            "confidence": "medium",
            "reason": reason,
            "ols_hits": hits,
            "web_hits": web_hits,
            "ontology_framework_config": framework_config,
        }
        target["ontology_id"] = ontology_id
        target["ontology_lookup"] = hit
        target["ontology_lookup_hits"] = hits
        target["ontology_match"] = True
        target["ontology_strategy_result"] = result
        return result

    def _not_harmonized(
        self,
        target: dict[str, Any],
        *,
        reason: str,
        ols_hits: list[dict[str, Any]],
        web_hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = {
            "strategy": self.strategy,
            "status": "not_harmonized",
            "decision": "false",
            "confidence": "none",
            "reason": reason,
            "ols_hits": ols_hits,
            "web_hits": web_hits,
        }
        target["ontology_match"] = False
        target.pop("ontology_lookup", None)
        target.pop("ontology_lookup_hits", None)
        target["ontology_strategy_result"] = result
        return result

    def _hits_from_docs(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            hit
            for doc in docs[: self.max_results]
            if (hit := self._hit_from_doc(doc)) is not None
        ]

    def _hit_from_doc(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(doc, dict):
            return None

        ontology_id = doc.get("ontology_name")
        iri = doc.get("iri")
        hit_id = doc.get("short_form") or doc.get("id") or doc.get("obo_id")
        label = doc.get("label")
        if not ontology_id or not iri or not hit_id or not label:
            return None

        return {
            "iri": iri,
            "id": hit_id,
            "accession": doc.get("obo_id"),
            "title": label,
            "description": doc.get("description"),
            "ontology_id": ontology_id,
            "ontology_prefix": doc.get("ontology_prefix"),
            "type": doc.get("type"),
        }

    def _framework_config(self, ontology_id: str) -> dict[str, str] | None:
        payload = self.ols_client.ontology(ontology_id)
        config = payload.get("config", {}) if isinstance(payload, dict) else {}
        if not isinstance(config, dict):
            return None

        framework_id = config.get("id") or payload.get("ontologyId") or ontology_id
        title = config.get("title")
        description = config.get("description")
        version_iri = config.get("versionIri")
        url = version_iri or config.get("fileLocation")
        version = config.get("version") or self._version_from_iri(version_iri)

        framework_config = {
            "id": framework_id,
            "title": title,
            "description": description,
            "version": version,
            "url": url,
        }
        if all(isinstance(value, str) and value for value in framework_config.values()):
            return framework_config
        return None

    def _version_from_iri(self, version_iri: Any) -> str | None:
        if not isinstance(version_iri, str):
            return None

        release_match = re.search(r"/releases/([^/]+)/", version_iri)
        if release_match:
            return release_match.group(1)

        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", version_iri)
        if date_match:
            return date_match.group(0)

        return None

    def _web_query(self, target: dict[str, Any]) -> str:
        field = target.get("hz_field", target.get("pre_hz_field", "field"))
        label = target.get("hz_label", target.get("pre_hz_label", "label"))
        return f"{field}: {label} ontology"

    def _hit_decision(self, hit: dict[str, Any]) -> str:
        for field in ("id", "accession", "iri"):
            value = hit.get(field)
            if value:
                return str(value)
        return "false"


class RagStrategyHandler(PlaceholderStrategyHandler):
    strategy = "rag"
    reason = "RAG ontology harmonization is not implemented yet."
