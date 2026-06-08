from __future__ import annotations

from typing import Any


class LLM:
    """Unified curator interface for LLM generation platforms."""

    DEFAULT_PLATFORM = "gemini_enterprise"

    def __init__(self, platform: str = DEFAULT_PLATFORM, **platform_options: Any) -> None:
        self.platform_name = platform
        self.platform_options = dict(platform_options)
        self._routed_platforms: dict[str, Any] = {}
        self.platform = self._create_platform(platform, **platform_options)

    def generate_response(
        self,
        prompt: str,
        *,
        model: str | None = None,
        config: dict[str, Any] | None = None,
        tools: list[Any] | None = None,
        **extra_options: Any,
    ) -> str:
        platform = self._platform_for_model(model)
        return platform.generate_response(
            prompt,
            model=model,
            config=config,
            tools=tools,
            **extra_options,
        )

    def _platform_for_model(self, model: str | None) -> Any:
        if (
            model
            and model.startswith("claude-")
            and self.platform_name.strip().lower() != "claude_vertex"
        ):
            if "claude_vertex" not in self._routed_platforms:
                self._routed_platforms["claude_vertex"] = self._create_platform(
                    "claude_vertex",
                    **self._claude_platform_options(),
                )
            return self._routed_platforms["claude_vertex"]

        return self.platform

    def _claude_platform_options(self) -> dict[str, Any]:
        options = dict(self.platform_options)
        options.pop("client", None)
        options.pop("enterprise", None)
        options.pop("model", None)
        return options

    @classmethod
    def _create_platform(cls, platform: str, **platform_options: Any) -> Any:
        normalized_platform = platform.strip().lower()
        if normalized_platform == "gemini_enterprise":
            from agentic_curator.wrappers.gemini_enterprise import (
                GeminiEnterprisePlatform,
            )

            return GeminiEnterprisePlatform(**platform_options)

        if normalized_platform == "claude_vertex":
            from agentic_curator.wrappers.claude_vertex import (
                ClaudeVertexPlatform,
            )

            return ClaudeVertexPlatform(**platform_options)

        raise ValueError(
            f"Unknown LLM platform {platform!r}. "
            "Supported platforms: gemini_enterprise, claude_vertex."
        )
