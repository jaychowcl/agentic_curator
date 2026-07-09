# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from copy import deepcopy
from typing import Any


class BaseModelAdapter:
    """Normalize generated text from model-specific response shapes."""

    def parse_response(self, response: Any) -> str:
        text = self._text(response)
        if text is not None:
            return text

        text = self._candidate_text(response)
        if text is not None:
            return text

        return str(response)

    def _text(self, response: Any) -> str | None:
        text = self._field(response, "text")
        if text is not None:
            return str(text)

        text = self._field(response, "response")
        if text is not None:
            return str(text)

        return None

    def _candidate_text(self, response: Any) -> str | None:
        candidates = self._field(response, "candidates")
        if not candidates:
            return None

        candidate = candidates[0]
        content = self._field(candidate, "content")
        parts = self._field(content, "parts")
        if not parts:
            return None

        return self._text(parts[0])

    @staticmethod
    def _field(value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)

        return getattr(value, name, None)


class GeminiModelAdapter(BaseModelAdapter):
    """Normalize Gemini model responses."""

    def parse_response(self, response: Any) -> str:
        text = self._candidate_text(response)
        if text is not None:
            return text

        return super().parse_response(response)


class ClaudeModelAdapter(BaseModelAdapter):
    """Normalize Claude partner model responses."""

    def parse_response(self, response: Any) -> str:
        text = self._content_text(response)
        if text is not None:
            return text

        return super().parse_response(response)

    def _content_text(self, response: Any) -> str | None:
        content = self._field(response, "content")
        if not content:
            return None

        parts = []
        for block in content:
            text = self._field(block, "text")
            if text is not None:
                parts.append(str(text))

        if parts:
            return "".join(parts)

        return None


class GeminiEnterprisePlatform:
    """Vertex AI Gemini adapter for curator LLM calls."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    DEFAULT_CONFIG_TEMPLATE = {
        "temperature": 0.2,
        "max_output_tokens": 8192,
        "candidate_count": 1,
        "response_mime_type": None,
        "response_schema": None,
        "safety_settings": None,
    }
    DEFAULT_TOOLS_TEMPLATE: list[Any] = []

    def __init__(
        self,
        *,
        project: str | None = None,
        location: str | None = None,
        model: str | None = None,
        config: dict[str, Any] | None = None,
        tools: list[Any] | None = None,
        enterprise: bool | None = None,
        client: Any | None = None,
        **client_options: Any,
    ) -> None:
        self.project = project
        self.location = location
        self.model = model or self.DEFAULT_MODEL
        self.config_template = self._merged_config(config)
        self.tools_template = list(
            self.DEFAULT_TOOLS_TEMPLATE if tools is None else tools
        )
        self.enterprise = enterprise
        self.client = client
        self.client_options = client_options

    def generate_response(
        self,
        prompt: str,
        *,
        model: str | None = None,
        config: dict[str, Any] | None = None,
        tools: list[Any] | None = None,
        **extra_options: Any,
    ) -> str:
        response = self.generate_response_with_metadata(
            prompt,
            model=model,
            config=config,
            tools=tools,
            **extra_options,
        )
        return str(response["text"])

    def generate_response_with_metadata(
        self,
        prompt: str,
        *,
        model: str | None = None,
        config: dict[str, Any] | None = None,
        tools: list[Any] | None = None,
        **extra_options: Any,
    ) -> dict[str, Any]:
        effective_model = model or self.model
        generation_config = self._clean_options(self._generation_config(config))
        generation_tools = self.tools_template if tools is None else tools
        request = {
            "model": effective_model,
            "contents": prompt,
            "config": generation_config,
            **extra_options,
        }
        if generation_tools:
            request["tools"] = generation_tools

        client = self._client()
        raw_response = client.models.generate_content(**request)
        text = self._model_adapter(effective_model).parse_response(raw_response)
        return {
            "text": text,
            "raw_response": raw_response,
            "citations": self._citations(raw_response),
            "tool_calls": self._tool_calls(raw_response),
            "provider": "gemini_enterprise",
        }

    def _client(self) -> Any:
        if self.client is None:
            self.client = self._create_client(
                project=self.project,
                location=self.location,
                enterprise=self.enterprise,
                client_options=self.client_options,
            )
        return self.client

    @classmethod
    def _merged_config(
        cls,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged = deepcopy(cls.DEFAULT_CONFIG_TEMPLATE)
        if config:
            merged.update(config)
        return merged

    def _generation_config(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        merged = deepcopy(self.config_template)
        if config:
            merged.update(config)
        return merged

    @staticmethod
    def _clean_options(options: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in options.items() if value is not None}

    @staticmethod
    def _model_adapter(model: str) -> BaseModelAdapter:
        if model.startswith("claude-"):
            return ClaudeModelAdapter()

        return GeminiModelAdapter()

    @classmethod
    def _citations(cls, response: Any) -> list[dict[str, Any]]:
        citations = []
        for part in cls._content_parts(response):
            annotations = BaseModelAdapter._field(part, "annotations")
            if not annotations:
                continue
            for annotation in annotations:
                normalized = cls._normalize_mapping(annotation)
                if normalized:
                    citations.append(normalized)
        return citations

    @classmethod
    def _tool_calls(cls, response: Any) -> list[dict[str, Any]]:
        steps = BaseModelAdapter._field(response, "steps")
        if not steps:
            return []
        return [
            normalized
            for step in steps
            if (normalized := cls._normalize_mapping(step)) is not None
        ]

    @classmethod
    def _content_parts(cls, response: Any) -> list[Any]:
        candidates = BaseModelAdapter._field(response, "candidates")
        if not candidates:
            return []
        parts = []
        for candidate in candidates:
            content = BaseModelAdapter._field(candidate, "content")
            candidate_parts = BaseModelAdapter._field(content, "parts")
            if candidate_parts:
                parts.extend(candidate_parts)
        return parts

    @classmethod
    def _normalize_mapping(cls, value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return {
                key: cls._normalize_value(item)
                for key, item in value.items()
            }
        if hasattr(value, "__dict__"):
            return {
                key: cls._normalize_value(item)
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        return None

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: cls._normalize_value(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._normalize_value(item) for item in value]
        if hasattr(value, "__dict__"):
            normalized = cls._normalize_mapping(value)
            return {} if normalized is None else normalized
        return value

    @staticmethod
    def _create_client(
        *,
        project: str | None,
        location: str | None,
        enterprise: bool | None,
        client_options: dict[str, Any],
    ) -> Any:
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "Gemini Enterprise LLM support requires the Google Gen AI "
                "SDK. Install google-genai before creating a real "
                "GeminiEnterprisePlatform client."
            ) from exc

        mode_options = {"enterprise": True} if enterprise else {"vertexai": True}
        options = {
            key: value
            for key, value in {
                **mode_options,
                "project": project,
                "location": location,
                **client_options,
            }.items()
            if value is not None
        }
        return genai.Client(**options)
