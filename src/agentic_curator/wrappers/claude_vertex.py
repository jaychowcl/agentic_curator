from __future__ import annotations

from copy import deepcopy
from typing import Any

from agentic_curator.wrappers.gemini_enterprise import ClaudeModelAdapter


class ClaudeVertexPlatform:
    """Anthropic Claude adapter for Vertex AI curator LLM calls."""

    DEFAULT_MODEL = "claude-opus-4-8"
    DEFAULT_CONFIG_TEMPLATE = {
        "temperature": 0.2,
        "max_output_tokens": 8192,
        "response_schema": None,
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
        client: Any | None = None,
        **client_options: Any,
    ) -> None:
        self.project = project
        self.location = location or "global"
        self.model = model or self.DEFAULT_MODEL
        self.config_template = self._merged_config(config)
        self.tools_template = list(
            self.DEFAULT_TOOLS_TEMPLATE if tools is None else tools
        )
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
        effective_model = model or self.model
        request = {
            "model": effective_model,
            "messages": [{"role": "user", "content": prompt}],
            **self._claude_config(config),
            **extra_options,
        }
        generation_tools = self.tools_template if tools is None else tools
        if generation_tools:
            request["tools"] = generation_tools

        raw_response = self._client().messages.create(**request)
        return ClaudeModelAdapter().parse_response(raw_response)

    def _client(self) -> Any:
        if self.client is None:
            self.client = self._create_client(
                project=self.project,
                location=self.location,
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

    def _claude_config(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        generation_config = self._clean_options(self._generation_config(config))
        claude_config: dict[str, Any] = {}

        if "max_output_tokens" in generation_config:
            claude_config["max_tokens"] = generation_config["max_output_tokens"]
        if "max_tokens" in generation_config:
            claude_config["max_tokens"] = generation_config["max_tokens"]
        if "temperature" in generation_config:
            claude_config["temperature"] = generation_config["temperature"]

        response_schema = generation_config.get("response_schema")
        if response_schema:
            claude_config["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": self._normalize_schema(response_schema),
                }
            }

        return claude_config

    @classmethod
    def _normalize_schema(cls, schema: Any) -> Any:
        if isinstance(schema, dict):
            return {
                key: cls._normalize_schema_value(key, value)
                for key, value in schema.items()
            }
        if isinstance(schema, list):
            return [cls._normalize_schema(item) for item in schema]

        return schema

    @classmethod
    def _normalize_schema_value(cls, key: str, value: Any) -> Any:
        if key == "type" and isinstance(value, str):
            return value.lower()

        return cls._normalize_schema(value)

    @staticmethod
    def _clean_options(options: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in options.items() if value is not None}

    @staticmethod
    def _create_client(
        *,
        project: str | None,
        location: str,
        client_options: dict[str, Any],
    ) -> Any:
        try:
            from anthropic import AnthropicVertex
        except ImportError as exc:
            raise ImportError(
                "Claude Vertex LLM support requires the Anthropic SDK with "
                "Vertex support. Install anthropic[vertex] before creating a "
                "real ClaudeVertexPlatform client."
            ) from exc

        options = {
            key: value
            for key, value in {
                "project_id": project,
                "region": location,
                **client_options,
            }.items()
            if value is not None
        }
        return AnthropicVertex(**options)
