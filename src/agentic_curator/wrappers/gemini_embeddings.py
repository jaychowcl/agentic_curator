# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from typing import Any

from agentic_curator.curators.ontology_harmonizer.request_policy import (
    RequestPolicy,
    request_with_retry,
)
from agentic_curator.wrappers.gemini_enterprise import GeminiEnterprisePlatform


class GeminiEmbeddingProvider:
    """Generate retrieval embeddings through Gemini Enterprise/Vertex AI."""

    DEFAULT_MODEL = "gemini-embedding-001"
    DEFAULT_DIMENSIONS = 768
    MAX_BATCH_SIZE = 250

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        request_policy: RequestPolicy | None = None,
        client: Any | None = None,
        project: str | None = None,
        location: str | None = None,
        enterprise: bool | None = None,
    ) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive.")
        self.model = model
        self.dimensions = dimensions
        self.request_policy = request_policy or RequestPolicy()
        self.platform = GeminiEnterprisePlatform(
            project=project,
            location=location,
            enterprise=enterprise,
            client=client,
        )
        self.last_request_traces: list[dict[str, Any]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.MAX_BATCH_SIZE):
            vectors.extend(
                self._embed(texts[offset : offset + self.MAX_BATCH_SIZE], "RETRIEVAL_DOCUMENT")
            )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([text], "RETRIEVAL_QUERY")
        return vectors[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        try:
            from google.genai.types import EmbedContentConfig
        except ImportError as exc:  # pragma: no cover - dependency error path.
            raise ImportError("Gemini embeddings require google-genai.") from exc

        def operation() -> Any:
            return self.platform._client().models.embed_content(
                model=self.model,
                contents=texts,
                config=EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimensions,
                ),
            )

        response, trace = request_with_retry(operation, self.request_policy)
        self.last_request_traces.append(trace)
        embeddings = getattr(response, "embeddings", None)
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError("Gemini embedding response count does not match input count.")
        vectors = []
        for embedding in embeddings:
            values = getattr(embedding, "values", None)
            if not isinstance(values, list) or len(values) != self.dimensions:
                raise ValueError("Gemini embedding response has an invalid dimension.")
            vectors.append([float(value) for value in values])
        return vectors
