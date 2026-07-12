# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

import logging
import time
from typing import Any


LOGGER = logging.getLogger(__name__)


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
        platform = self._platform_for_model(model)
        platform_name = (
            "claude_vertex"
            if platform is self._routed_platforms.get("claude_vertex")
            else self.platform_name
        )
        effective_model = model or getattr(platform, "model", None)
        started = time.monotonic()
        LOGGER.debug(
            "LLM call started platform=%s model=%s prompt_characters=%s tools=%s structured=%s",
            platform_name,
            effective_model,
            len(prompt),
            len(tools or []),
            bool((config or {}).get("response_schema")),
        )
        try:
            response = platform.generate_response_with_metadata(
                prompt,
                model=model,
                config=config,
                tools=tools,
                **extra_options,
            )
        except Exception:
            LOGGER.exception(
                "LLM call failed platform=%s model=%s elapsed_seconds=%.3f",
                platform_name,
                effective_model,
                time.monotonic() - started,
            )
            raise
        text = str(response.get("text", ""))
        LOGGER.info(
            "LLM call completed platform=%s model=%s response_characters=%s citations=%s tool_calls=%s elapsed_seconds=%.3f",
            response.get("provider", platform_name),
            effective_model,
            len(text),
            len(response.get("citations") or []),
            len(response.get("tool_calls") or []),
            time.monotonic() - started,
        )
        return response

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
