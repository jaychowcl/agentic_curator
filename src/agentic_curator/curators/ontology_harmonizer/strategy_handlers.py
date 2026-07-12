# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

import re
from typing import Any

import requests

from agentic_curator.curators.ontology_harmonizer.ontology_store import OntoStore
from agentic_curator.curators.ontology_harmonizer.request_policy import RequestPolicy, request_with_retry
from agentic_curator.wrappers import LLM


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

    def __init__(self, *, base_url: str = BASE_URL, timeout: int | None = None, request_policy: RequestPolicy | None = None, cache_store: OntoStore | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_policy = request_policy or RequestPolicy(timeout_seconds=timeout or 30)
        self.timeout = self.request_policy.timeout_seconds
        self.cache_store = cache_store
        self.last_request_trace: dict[str, Any] | None = None

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
        key = {"base_url": self.base_url, **params}
        cached = self._cached("search", key)
        if cached is not None:
            return cached
        def operation():
            response = requests.get(f"{self.base_url}/search", params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        payload, self.last_request_trace = request_with_retry(operation, self.request_policy)
        docs = payload.get("response", {}).get("docs", [])
        result = docs if isinstance(docs, list) else []
        self._store("search", key, result)
        return result

    def ontology(self, ontology_id: str) -> dict[str, Any]:
        key = {"base_url": self.base_url, "ontology_id": ontology_id}
        cached = self._cached("ontology", key)
        if cached is not None:
            return cached
        def operation():
            response = requests.get(f"{self.base_url}/ontologies/{ontology_id}", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        payload, self.last_request_trace = request_with_retry(operation, self.request_policy)
        result = payload if isinstance(payload, dict) else {}
        self._store("ontology", key, result)
        return result

    def _cached(self, operation: str, key: dict[str, Any]) -> Any:
        if self.cache_store is None:
            return None
        result = self.cache_store.get_cached_response("ols", operation, key, ttl_seconds=self.request_policy.cache_ttl_seconds, force_refresh=self.request_policy.force_refresh)
        if result is not None:
            self.last_request_trace = {"status": "cache_hit", "attempts": 0, "errors": [], "elapsed_seconds": 0}
        return result

    def _store(self, operation: str, key: dict[str, Any], result: Any) -> None:
        if self.cache_store is not None:
            self.cache_store.set_cached_response("ols", operation, key, result)


class NullSearchClient:
    """Deterministic no-op web search client used unless one is injected."""

    def search(self, query: str, *, max_results: int = 25) -> list[dict[str, Any]]:
        del query, max_results
        return []


class GeminiGroundedSearchClient:
    """Google Search grounding client backed by the LLM facade."""

    GOOGLE_SEARCH_TOOL = {"type": "google_search"}

    def __init__(
        self,
        *,
        llm: Any | None = None,
        model: str | None = None,
        request_budget: int | None = 100,
        request_policy: RequestPolicy | None = None,
        cache_store: OntoStore | None = None,
    ) -> None:
        self.llm = LLM() if llm is None else llm
        self.model = model
        self.request_budget = request_budget
        self.request_policy = request_policy or RequestPolicy()
        self.cache_store = cache_store
        self.requests_made = 0
        self.last_response: dict[str, Any] | None = None
        self.last_error: str | None = None
        self.last_request_trace: dict[str, Any] | None = None

    def search(self, query: str, *, max_results: int = 25) -> list[dict[str, Any]]:
        if self.request_budget is not None and self.requests_made >= self.request_budget:
            self.last_error = "Google search request budget exhausted."
            return []

        self.requests_made += 1
        self.last_error = None
        prompt = self._prompt(query)
        key = {"query": query, "model": self.model, "max_results": max_results}
        if self.cache_store is not None:
            cached = self.cache_store.get_cached_response("gemini_google_search", "search", key, ttl_seconds=self.request_policy.cache_ttl_seconds, force_refresh=self.request_policy.force_refresh)
            if cached is not None:
                self.last_response = cached
                self.last_request_trace = {"status": "cache_hit", "attempts": 0, "errors": [], "elapsed_seconds": 0}
                return self._hits(cached)[:max_results]
        try:
            response, self.last_request_trace = request_with_retry(
                lambda: self.llm.generate_response_with_metadata(prompt, model=self.model, tools=[self.GOOGLE_SEARCH_TOOL]),
                self.request_policy,
            )
        except Exception as exc:
            self.last_response = None
            self.last_error = str(exc)
            return []

        self.last_response = response
        if self.cache_store is not None:
            cacheable = {key: response.get(key) for key in ("text", "citations", "tool_calls", "provider")}
            self.cache_store.set_cached_response("gemini_google_search", "search", key, cacheable)
        return self._hits(response)[:max_results]

    def _prompt(self, query: str) -> str:
        return (
            "Search the web for ontology evidence related to this query:\n"
            f"{query}\n\n"
            "Return concise evidence for ontology term candidates, including "
            "term labels, IDs, IRIs, and ontology framework names when found."
        )

    def _hits(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        text = str(response.get("text", ""))
        provider = str(response.get("provider", "gemini_enterprise"))
        hits = []
        for citation in response.get("citations", []):
            if not isinstance(citation, dict):
                continue
            link = citation.get("url")
            if not link:
                continue
            hits.append(
                {
                    "title": citation.get("title") or link,
                    "link": link,
                    "snippet": text,
                    "source": "gemini_google_search",
                    "provider": provider,
                }
            )
        return hits


class WebsearchStrategyHandler:
    strategy = "websearch"
    max_results = 25
    judge_candidate_limit = 10

    def __init__(
        self,
        *,
        ols_client: OlsClient | None = None,
        search_client: Any | None = None,
        search_judge: Any | None = None,
    ) -> None:
        self.ols_client = OlsClient() if ols_client is None else ols_client
        self.search_client = (
            NullSearchClient() if search_client is None else search_client
        )
        self.search_judge = search_judge

    def handle(
        self,
        target: dict[str, Any],
        *,
        publication_context: str | None,
        ontostore: OntoStore,
    ) -> dict[str, Any]:
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
        judgements: list[dict[str, Any]] = []
        if restricted_hits:
            if self.search_judge is None:
                return self._accept_hit(
                    target,
                    ontostore=ontostore,
                    hit=restricted_hits[0],
                    hits=restricted_hits,
                    web_hits=[],
                    reason="Restricted OLS search returned a usable ontology hit.",
                )
            try:
                judgement = self._judge_search_hits(
                    target=target,
                    publication_context=publication_context,
                    stage="restricted",
                    restricted_hits=restricted_hits[: self.judge_candidate_limit],
                    unrestricted_hits=[],
                    web_hits=[],
                )
            except Exception as exc:  # noqa: BLE001 - preserve judge failure trace.
                return self._not_harmonized(
                    target,
                    reason="Search LLM judge failed.",
                    ols_hits=restricted_hits,
                    web_hits=[],
                    search_llm_judgements=judgements,
                    search_llm_judge_error=str(exc),
                )
            judgements.append({"stage": "restricted", **judgement})
            target["search_llm_judgements"] = judgements
            if str(judgement["decision"]).lower() != "false":
                hit = self._selected_hit(restricted_hits, judgement["decision"])
                return self._accept_hit(
                    target,
                    ontostore=ontostore,
                    hit=hit,
                    hits=restricted_hits,
                    web_hits=[],
                    reason=str(judgement["reason"]),
                    confidence=str(judgement["confidence"]),
                    search_llm_judgements=judgements,
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
        web_resolved_hits = self._resolve_web_candidates(web_hits)
        web_search_error = getattr(self.search_client, "last_error", None)
        expanded_hits = self._unique_hits([*unrestricted_hits, *web_resolved_hits])
        if expanded_hits:
            all_hits = [*restricted_hits, *expanded_hits]
            if self.search_judge is None:
                return self._accept_hit(
                    target,
                    ontostore=ontostore,
                    hit=expanded_hits[0],
                    hits=expanded_hits,
                    web_hits=web_hits,
                    reason="Unrestricted OLS search returned a usable ontology hit.",
                    web_search_error=web_search_error,
                )
            try:
                judgement = self._judge_search_hits(
                    target=target,
                    publication_context=publication_context,
                    stage="expanded",
                    restricted_hits=[],
                    unrestricted_hits=expanded_hits[
                        : self.judge_candidate_limit
                    ],
                    web_hits=web_hits,
                )
            except Exception as exc:  # noqa: BLE001 - preserve judge failure trace.
                return self._not_harmonized(
                    target,
                    reason="Search LLM judge failed.",
                    ols_hits=all_hits,
                    web_hits=web_hits,
                    web_search_error=web_search_error,
                    search_llm_judgements=judgements,
                    search_llm_judge_error=str(exc),
                )
            judgements.append({"stage": "expanded", **judgement})
            target["search_llm_judgements"] = judgements
            if str(judgement["decision"]).lower() != "false":
                hit = self._selected_hit(expanded_hits, judgement["decision"])
                return self._accept_hit(
                    target,
                    ontostore=ontostore,
                    hit=hit,
                    hits=all_hits,
                    web_hits=web_hits,
                    reason=str(judgement["reason"]),
                    confidence=str(judgement["confidence"]),
                    web_search_error=web_search_error,
                    search_llm_judgements=judgements,
                )
            return self._not_harmonized(
                target,
                reason=str(judgement["reason"]),
                ols_hits=all_hits,
                web_hits=web_hits,
                web_search_error=web_search_error,
                search_llm_judgements=judgements,
            )

        return self._not_harmonized(
            target,
            reason="No usable OLS ontology hit was found.",
            ols_hits=restricted_hits,
            web_hits=web_hits,
            web_search_error=web_search_error,
            search_llm_judgements=judgements,
        )

    def _resolve_web_candidates(self, web_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        identifiers: set[str] = set()
        pattern = re.compile(r"(?:https?://purl\.obolibrary\.org/obo/[A-Za-z][A-Za-z0-9]+_[0-9]+|\b[A-Za-z][A-Za-z0-9_]+[:_][0-9]{2,}\b)")
        for hit in web_hits:
            evidence = " ".join(str(hit.get(key, "")) for key in ("title", "snippet", "link"))
            identifiers.update(pattern.findall(evidence))

        resolved: list[dict[str, Any]] = []
        for identifier in sorted(identifiers):
            docs = self.ols_client.search(identifier, rows=10)
            for hit in self._hits_from_docs(docs):
                values = {str(hit.get(key, "")).lower() for key in ("id", "accession", "iri")}
                normalized = identifier.lower()
                iri_tail = normalized.rsplit("/", 1)[-1].replace("_", ":", 1)
                if normalized in values or iri_tail in values:
                    resolved.append(hit)
        return self._unique_hits(resolved)

    @staticmethod
    def _unique_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: dict[str, dict[str, Any]] = {}
        for hit in hits:
            key = str(hit.get("id") or hit.get("iri") or hit.get("accession"))
            unique.setdefault(key, hit)
        return list(unique.values())

    def _accept_hit(
        self,
        target: dict[str, Any],
        *,
        ontostore: OntoStore,
        hit: dict[str, Any],
        hits: list[dict[str, Any]],
        web_hits: list[dict[str, Any]],
        reason: str,
        confidence: str = "medium",
        web_search_error: str | None = None,
        search_llm_judgements: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
                web_search_error=web_search_error,
                search_llm_judgements=search_llm_judgements,
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
            "confidence": confidence,
            "reason": reason,
            "ols_hits": hits,
            "web_hits": web_hits,
            "ontology_framework_config": framework_config,
        }
        if web_search_error:
            result["web_search_error"] = web_search_error
        if search_llm_judgements:
            result["search_llm_judgements"] = search_llm_judgements
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
        web_search_error: str | None = None,
        search_llm_judgements: list[dict[str, Any]] | None = None,
        search_llm_judge_error: str | None = None,
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
        if web_search_error:
            result["web_search_error"] = web_search_error
        if search_llm_judgements:
            result["search_llm_judgements"] = search_llm_judgements
            target["search_llm_judgements"] = search_llm_judgements
        if search_llm_judge_error:
            result["search_llm_judge_error"] = search_llm_judge_error
        target["ontology_match"] = False
        target.pop("ontology_lookup", None)
        target.pop("ontology_lookup_hits", None)
        target["ontology_strategy_result"] = result
        return result

    def _judge_search_hits(
        self,
        *,
        target: dict[str, Any],
        publication_context: str | None,
        stage: str,
        restricted_hits: list[dict[str, Any]],
        unrestricted_hits: list[dict[str, Any]],
        web_hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        judgement = self.search_judge(
            target=target,
            publication_context=publication_context,
            stage=stage,
            restricted_hits=restricted_hits,
            unrestricted_hits=unrestricted_hits,
            web_hits=web_hits,
        )
        if not isinstance(judgement, dict):
            raise ValueError("Search LLM judgement must be a JSON object.")
        if not {"decision", "confidence", "reason"}.issubset(judgement):
            raise ValueError(
                "Search LLM judgement must include decision, confidence, and reason."
            )
        candidates = [*restricted_hits, *unrestricted_hits]
        if str(judgement["decision"]).lower() != "false":
            self._selected_hit(candidates, judgement["decision"])
        return judgement

    def _selected_hit(
        self,
        hits: list[dict[str, Any]],
        decision: Any,
    ) -> dict[str, Any]:
        value = str(decision)
        for hit in hits:
            if value in {
                str(hit.get("id")),
                str(hit.get("accession")),
                str(hit.get("iri")),
            }:
                return hit
        raise ValueError("Search LLM decision must match a supplied OLS candidate.")

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
        field = target.get("pre_hz_field", target.get("hz_field", "field"))
        label = target.get("pre_hz_label", target.get("hz_label", "label"))
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
