# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

import builtins
from types import SimpleNamespace

import pytest

from agentic_curator.wrappers import (
    ClaudeModelAdapter,
    ClaudeVertexPlatform,
    GeminiEnterprisePlatform,
    GeminiModelAdapter,
    LLM,
)


class FakeModels:
    def __init__(self) -> None:
        self.calls = []

    def generate_content(self, **request):
        self.calls.append(request)
        return {"response": "ok", "request": request}


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


class FakeClaudeMessages:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **request):
        self.calls.append(request)
        return SimpleNamespace(content=[SimpleNamespace(text="ok")])


class FakeClaudeClient:
    def __init__(self) -> None:
        self.messages = FakeClaudeMessages()


def test_curator_wrappers_import() -> None:
    assert LLM.DEFAULT_PLATFORM == "gemini_enterprise"
    assert GeminiEnterprisePlatform.DEFAULT_MODEL == "gemini-2.5-flash"
    assert ClaudeVertexPlatform.DEFAULT_MODEL == "claude-opus-4-8"


def test_llm_defaults_to_gemini_enterprise_platform() -> None:
    llm = LLM()

    assert llm.platform_name == "gemini_enterprise"
    assert isinstance(llm.platform, GeminiEnterprisePlatform)


def test_llm_can_use_claude_vertex_platform() -> None:
    llm = LLM(platform="claude_vertex", client=FakeClaudeClient())

    assert llm.platform_name == "claude_vertex"
    assert isinstance(llm.platform, ClaudeVertexPlatform)


def test_llm_unknown_platform_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown LLM platform"):
        LLM(platform="missing_platform")


def test_llm_generate_response_delegates_to_platform() -> None:
    client = FakeClient()
    llm = LLM(client=client)

    response = llm.generate_response(
        "review this publication",
        model="gemini-test",
        config={"temperature": 0.0, "response_mime_type": "application/json"},
        request_id="abc",
    )

    assert response == "ok"
    assert client.models.calls == [
        {
            "model": "gemini-test",
            "contents": "review this publication",
            "config": {
                "temperature": 0.0,
                "max_output_tokens": 8192,
                "candidate_count": 1,
                "response_mime_type": "application/json",
            },
            "request_id": "abc",
        }
    ]


def test_llm_generate_response_with_metadata_delegates_to_platform() -> None:
    client = FakeClient()
    llm = LLM(client=client)

    response = llm.generate_response_with_metadata(
        "search this",
        model="gemini-test",
        tools=[{"type": "google_search"}],
    )

    assert response["text"] == "ok"
    assert response["provider"] == "gemini_enterprise"
    assert response["raw_response"] == {"response": "ok", "request": client.models.calls[0]}
    assert client.models.calls == [
        {
            "model": "gemini-test",
            "contents": "search this",
            "config": {
                "temperature": 0.2,
                "max_output_tokens": 8192,
                "candidate_count": 1,
                "tools": [{"type": "google_search"}],
            },
        }
    ]


def test_model_adapter_parses_text_attribute() -> None:
    response = SimpleNamespace(text="generated text")

    assert GeminiModelAdapter().parse_response(response) == "generated text"


def test_model_adapter_parses_dict_text() -> None:
    assert GeminiModelAdapter().parse_response({"text": "generated text"}) == (
        "generated text"
    )


def test_model_adapter_parses_dict_response() -> None:
    assert GeminiModelAdapter().parse_response({"response": "generated text"}) == (
        "generated text"
    )


def test_claude_model_adapter_parses_content_blocks() -> None:
    response = SimpleNamespace(
        content=[
            SimpleNamespace(text="first "),
            SimpleNamespace(text="second"),
        ]
    )

    assert ClaudeModelAdapter().parse_response(response) == "first second"


def test_model_adapter_parses_candidate_part_text() -> None:
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "generated text",
                        }
                    ],
                }
            }
        ]
    }

    assert GeminiModelAdapter().parse_response(response) == "generated text"


def test_gemini_model_adapter_prefers_candidate_part_text() -> None:
    response = SimpleNamespace(
        text="convenience text",
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(text="candidate content text"),
                    ],
                ),
            )
        ],
    )

    assert GeminiModelAdapter().parse_response(response) == "candidate content text"


def test_model_adapter_falls_back_to_string() -> None:
    assert GeminiModelAdapter().parse_response(["unexpected"]) == "['unexpected']"


def test_gemini_enterprise_uses_claude_adapter_for_claude_model() -> None:
    adapter = GeminiEnterprisePlatform._model_adapter("claude-opus-4-8")

    assert isinstance(adapter, ClaudeModelAdapter)


def test_gemini_enterprise_uses_gemini_adapter_by_default() -> None:
    adapter = GeminiEnterprisePlatform._model_adapter("gemini-2.5-flash")

    assert isinstance(adapter, GeminiModelAdapter)


def test_gemini_enterprise_generate_response_uses_injected_client() -> None:
    client = FakeClient()
    platform = GeminiEnterprisePlatform(
        client=client,
        model="gemini-default",
        config={"temperature": 0.4},
        tools=["tool-a"],
    )

    response = platform.generate_response(
        "extract evidence",
        config={"max_output_tokens": 128},
        tools=["tool-b"],
    )

    assert response == "ok"
    assert client.models.calls == [
        {
            "model": "gemini-default",
            "contents": "extract evidence",
                "config": {
                    "temperature": 0.4,
                    "max_output_tokens": 128,
                    "candidate_count": 1,
                    "tools": ["tool-b"],
                },
        }
    ]


def test_gemini_enterprise_generate_response_with_metadata_extracts_citations() -> None:
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "Lung maps to UBERON:0002048.",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://example.org/lung",
                                    "title": "Lung ontology entry",
                                    "start_index": 0,
                                    "end_index": 4,
                                }
                            ],
                        }
                    ],
                }
            }
        ],
        "steps": [
            {"type": "google_search_call", "arguments": {"queries": ["lung ontology"]}},
            {"type": "google_search_result", "result": [{"search_suggestions": "<div />"}]},
        ],
    }

    class MetadataModels(FakeModels):
        def generate_content(self, **request):
            self.calls.append(request)
            return response

    client = FakeClient()
    client.models = MetadataModels()
    platform = GeminiEnterprisePlatform(client=client)

    result = platform.generate_response_with_metadata(
        "find ontology evidence",
        tools=[{"type": "google_search"}],
    )

    assert result == {
        "text": "Lung maps to UBERON:0002048.",
        "raw_response": response,
        "citations": [
            {
                "type": "url_citation",
                "url": "https://example.org/lung",
                "title": "Lung ontology entry",
                "start_index": 0,
                "end_index": 4,
            }
        ],
        "tool_calls": [
            {"type": "google_search_call", "arguments": {"queries": ["lung ontology"]}},
            {"type": "google_search_result", "result": [{"search_suggestions": "<div />"}]},
        ],
        "provider": "gemini_enterprise",
    }
    assert client.models.calls[0]["config"]["tools"] == [
        {"type": "google_search"}
    ]
    assert "tools" not in client.models.calls[0]


def test_claude_vertex_generate_response_uses_injected_client() -> None:
    client = FakeClaudeClient()
    platform = ClaudeVertexPlatform(
        client=client,
        model="claude-default",
        config={"temperature": 0.4},
        tools=["tool-a"],
    )

    response = platform.generate_response(
        "extract evidence",
        config={"max_output_tokens": 128},
        tools=["tool-b"],
    )

    assert response == "ok"
    assert client.messages.calls == [
        {
            "model": "claude-default",
            "messages": [{"role": "user", "content": "extract evidence"}],
            "max_tokens": 128,
            "temperature": 0.4,
            "tools": ["tool-b"],
        }
    ]


def test_claude_vertex_generate_response_with_metadata_preserves_text_contract() -> None:
    client = FakeClaudeClient()
    platform = ClaudeVertexPlatform(client=client)

    result = platform.generate_response_with_metadata(
        "extract evidence",
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
    )

    assert result["text"] == "ok"
    assert result["provider"] == "claude_vertex"
    assert result["citations"] == []
    assert result["tool_calls"] == []
    assert client.messages.calls[0]["tools"] == [
        {"type": "web_search_20260209", "name": "web_search"}
    ]


def test_claude_vertex_translates_response_schema_to_output_config() -> None:
    client = FakeClaudeClient()
    platform = ClaudeVertexPlatform(client=client)
    schema = {
        "type": "OBJECT",
        "properties": {
            "evidences": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "evidence": {"type": "STRING"},
                    },
                    "required": ["evidence"],
                },
            }
        },
        "required": ["evidences"],
    }

    platform.generate_response(
        "extract evidence",
        model="claude-opus-4-8",
        config={
            "response_mime_type": "application/json",
            "response_schema": schema,
            "candidate_count": 1,
            "safety_settings": [],
        },
    )

    assert client.messages.calls[0]["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "evidences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence": {"type": "string"},
                            },
                            "required": ["evidence"],
                        },
                    }
                },
                "required": ["evidences"],
            },
        }
    }
    assert "response_mime_type" not in client.messages.calls[0]
    assert "response_schema" not in client.messages.calls[0]
    assert "candidate_count" not in client.messages.calls[0]
    assert "safety_settings" not in client.messages.calls[0]


def test_llm_routes_claude_models_to_claude_vertex(monkeypatch) -> None:
    gemini_client = FakeClient()
    claude_clients = []

    class FakeAnthropicVertex:
        def __init__(self, **options):
            self.options = options
            self.messages = FakeClaudeMessages()
            claude_clients.append(self)

    fake_anthropic = SimpleNamespace(AnthropicVertex=FakeAnthropicVertex)
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "anthropic" and "AnthropicVertex" in fromlist:
            return fake_anthropic
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    llm = LLM(client=gemini_client, project="project-a", location="global")
    response = llm.generate_response(
        "extract evidence",
        model="claude-opus-4-8",
        config={"max_output_tokens": 128},
    )

    assert response == "ok"
    assert gemini_client.models.calls == []
    assert claude_clients[0].options == {
        "project_id": "project-a",
        "region": "global",
    }
    assert claude_clients[0].messages.calls == [
        {
            "model": "claude-opus-4-8",
            "messages": [{"role": "user", "content": "extract evidence"}],
            "max_tokens": 128,
            "temperature": 0.2,
        }
    ]


def test_gemini_enterprise_creates_vertex_genai_client_by_default(monkeypatch) -> None:
    calls = []

    class FakeGenAIClient:
        def __init__(self, **options):
            calls.append(options)
            self.models = FakeModels()

    fake_google = SimpleNamespace(genai=SimpleNamespace(Client=FakeGenAIClient))
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google" and "genai" in fromlist:
            return fake_google
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    platform = GeminiEnterprisePlatform(project="project-a", location="global")
    platform.generate_response("review this publication")

    assert calls == [
        {
            "vertexai": True,
            "project": "project-a",
            "location": "global",
        }
    ]


def test_gemini_enterprise_creates_enterprise_genai_client(monkeypatch) -> None:
    calls = []

    class FakeGenAIClient:
        def __init__(self, **options):
            calls.append(options)
            self.models = FakeModels()

    fake_google = SimpleNamespace(genai=SimpleNamespace(Client=FakeGenAIClient))
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google" and "genai" in fromlist:
            return fake_google
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    platform = GeminiEnterprisePlatform(
        project="project-a",
        location="global",
        enterprise=True,
    )
    platform.generate_response("review this publication")

    assert calls == [
        {
            "enterprise": True,
            "project": "project-a",
            "location": "global",
        }
    ]


def test_claude_vertex_creates_anthropic_vertex_client(monkeypatch) -> None:
    calls = []

    class FakeAnthropicVertex:
        def __init__(self, **options):
            calls.append(options)
            self.messages = FakeClaudeMessages()

    fake_anthropic = SimpleNamespace(AnthropicVertex=FakeAnthropicVertex)
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "anthropic" and "AnthropicVertex" in fromlist:
            return fake_anthropic
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    platform = ClaudeVertexPlatform(project="project-a")
    platform.generate_response("review this publication")

    assert calls == [
        {
            "project_id": "project-a",
            "region": "global",
        }
    ]


def test_gemini_enterprise_missing_genai_dependency_raises_import_error(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        fromlist = args[2] if len(args) > 2 else kwargs.get("fromlist", ())
        if name == "google" and "genai" in fromlist:
            raise ImportError("cannot import name genai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    platform = GeminiEnterprisePlatform()
    with pytest.raises(ImportError, match="google-genai"):
        platform.generate_response("review this publication")


def test_claude_vertex_missing_anthropic_dependency_raises_import_error(
    monkeypatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        fromlist = args[2] if len(args) > 2 else kwargs.get("fromlist", ())
        if name == "anthropic" and "AnthropicVertex" in fromlist:
            raise ImportError("cannot import name AnthropicVertex")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    platform = ClaudeVertexPlatform()
    with pytest.raises(ImportError, match=r"anthropic\[vertex\]"):
        platform.generate_response("review this publication")
