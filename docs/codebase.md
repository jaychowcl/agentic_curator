# agentic-curator Codebase Handoff

This document summarizes the live `agentic_curator` package. It is intended as
a compact handoff for humans and agents working in this repository.

<a id="project-purpose-and-layout"></a>
## Project Purpose And Layout

`agentic-curator` provides LLM-assisted curation utilities for life science
publications. The current package focuses on publication evidence extraction,
final relevance judging, a placeholder ontology harmonizer, and provider
adapters for Gemini and Claude on Vertex AI.

Tracked project layout:

```text
pyproject.toml
README.md
LICENSE
docs/
  codebase.md
  index.md
src/agentic_curator/
  __init__.py
  cli/
    __init__.py
    cli_thematic_reviewer.py
  curators/
    __init__.py
    ontology_harmonizer/
      __init__.py
      harmonizer.py
    thematic_reviewer/
      __init__.py
      reviewer.py
      prompts/
        evidence_extraction.md
        judge_evidence.md
        theme.md
  wrappers/
    __init__.py
    claude_vertex.py
    gemini_enterprise.py
    llm.py
tests/
  test_cli_thematic_reviewer.py
  test_curator_llm_wrappers.py
  test_ontology_harmonizer.py
  test_thematic_reviewer.py
```

Ignored local development artifacts include `.dev/`, `.env/`, `.vscode/`,
Python caches, pytest caches, build outputs, and editable-install metadata.

<a id="runtime-and-packaging"></a>
## Runtime And Packaging

The package uses a `src/` layout with setuptools:

- project name: `agentic-curator`
- import package: `agentic_curator`
- Python requirement: `>=3.10`
- runtime dependencies: `anthropic[vertex]>=0.107,<1` and `google-genai>=1.72,<2`
- dev extra: `pytest>=8`
- console script: `cli_thematic_reviewer = "agentic_curator.cli.cli_thematic_reviewer:main"`
- package data: `agentic_curator/curators/*/prompts/*.md`

The local development convention is to use `.env/bin/python`. A typical setup
command is:

```bash
.env/bin/python -m pip install -e ".[dev]"
```

<a id="public-api"></a>
## Public API

The canonical reviewer import is:

```python
from agentic_curator.curators import OntologyHarmonizer, ThematicReviewer
```

`agentic_curator.__init__` also exports both curator classes, so
`from agentic_curator import ThematicReviewer, OntologyHarmonizer` remains
supported. The old flat module import `agentic_curator.thematic_reviewer` is
intentionally absent after the curator subpackage refactor.

`ThematicReviewer(llm=None)` accepts an optional LLM-like object. If no object is
provided, the reviewer lazily creates `agentic_curator.wrappers.LLM()` on the
first generation call.

Main methods:

- `review_relevancy(publication_text=None, theme=None, metadata=None, title=None) -> dict`
- `extract_evidence(publication_text=None, theme=None, metadata=None, title=None) -> str`
- `judge_evidence(evidences, theme=None, title=None) -> str`

`metadata` may be a string, dictionary, list, or `None` when used by reviewer
prompt helpers. The reviewer asks providers for JSON output but returns raw
generated text. JSON parsing and validation are caller responsibilities in the
current implementation.

<a id="ontology-harmonizer"></a>
## Ontology Harmonizer

`agentic_curator.curators.ontology_harmonizer.OntologyHarmonizer` is a
placeholder curator for future ontology harmonization from publication text. It
has no LLM, prompt, provider, or CLI integration yet.

Public method:

- `harmonize(publication_text=None, metadata=None, title=None, ontology_frameworks=None) -> dict`

The method returns a stable placeholder envelope:

```python
{
    "status": "placeholder",
    "publication_text": publication_text,
    "metadata": metadata,
    "title": title,
    "ontology_frameworks": ontology_frameworks or {},
    "matches": [],
    "targets": [...],
}
```

`publication_text` and `title` may be strings or `None`, `metadata` may be a
string, dictionary, or `None`, and `ontology_frameworks` is a dictionary of
framework names or configuration. `matches` remains empty until real
harmonization behavior is implemented.

`harmonize()` calls the private helper `_extract_harmonization_targets(...)` to
walk structured metadata and expose editable scalar field-label targets. The
helper traverses dictionaries and lists, skips raw string metadata, skips
`None`, and does not create targets for scalar list items without an object key.
Each target includes:

```python
{
    "id": "target-0",
    "source": "metadata",
    "field": "tissue",
    "label": "lung",
    "field_path": "/sample/tissue",
    "label_path": "/sample/tissue",
    "parent_path": "/sample",
    "key": "tissue",
    "value": "lung",
}
```

`field_path`, `label_path`, and `parent_path` use JSON Pointer-style paths with
escaped path segments (`~` becomes `~0`, `/` becomes `~1`). These coordinates
are intended to let future harmonization results edit both field names and
label values back into structured metadata.

<a id="reviewer-workflow"></a>
## Reviewer Workflow

`review_relevancy()` performs two model calls:

1. `extract_evidence()` reads `prompts/evidence_extraction.md`, then appends
   labeled `Theme`, `Title`, `Publication Text`, and `Metadata` blocks.
2. `judge_evidence()` reads `prompts/judge_evidence.md`, then appends labeled
   `Theme`, `Title`, and `Evidences` blocks.

`review_relevancy()` returns:

```python
{
    "evidences": evidence_result,
    "judgement": judgement_result,
}
```

Prompt values that are dictionaries or lists are serialized as sorted,
indented JSON. `None` prompt values become empty strings and all other values
are converted with `str(...)`.

Both model calls pass `response_mime_type="application/json"` and a response
schema. The evidence schema asks for an object with a required `evidences`
array. Each evidence item requires `evidence`, `judgement`, `confidence`, and
`reason` string fields. The judge schema asks for required `judgement`,
`reasoning`, and `confidence` string fields.

<a id="code-flow"></a>
## Code Flow

Major orchestration flow:

1. CLI users call `cli_thematic_reviewer`, which reads direct or UTF-8 file
   inputs and passes strings into `ThematicReviewer.review_relevancy(...)`.
2. `review_relevancy()` calls `extract_evidence(...)`, then passes that raw
   evidence result into `judge_evidence(...)`.
3. Each reviewer primitive loads its packaged Markdown prompt, appends labeled
   input blocks, then calls `self._llm().generate_response(...)` with a JSON
   response schema.
4. `LLM.generate_response(...)` delegates to the configured platform. Claude
   model names are routed to `ClaudeVertexPlatform` when the default platform is
   Gemini.
5. Provider adapters construct SDK-specific requests, call the injected or
   lazily created client, and normalize the provider response to a raw text
   string.

The current code does not parse model JSON responses, configure logging, or wrap
provider exceptions. Those responsibilities stay with callers.

`OntologyHarmonizer.harmonize(...)` is separate from this LLM flow. It returns a
placeholder dictionary directly and does not call `LLM`, provider adapters, or
prompt files.

<a id="prompts"></a>
## Prompts

Each curator owns its packaged prompt files inside its own subpackage. The
thematic reviewer prompts live under
`src/agentic_curator/curators/thematic_reviewer/prompts/`.

- `evidence_extraction.md` instructs the model to extract direct or indirect
  evidence statements verbatim and return an evidence list.
- `judge_evidence.md` instructs the model to judge whether extracted evidence
  satisfies the theme criteria and return relevance, reasoning, and confidence.
- `theme.md` is a fibrosis theme example used by local development fixtures and
  manual CLI runs. It is packaged but not loaded automatically by
  `ThematicReviewer`.

<a id="llm-wrapper"></a>
## LLM Wrapper

`agentic_curator.wrappers.LLM` is the provider routing facade.

```python
from agentic_curator.wrappers import LLM

llm = LLM()
text = llm.generate_response("prompt")
```

Defaults:

- default platform: `gemini_enterprise`
- default Gemini model: `gemini-2.5-flash`
- default Claude model: `claude-opus-4-8`

`LLM(platform="gemini_enterprise", **platform_options)` creates a Gemini
platform by default. `LLM(platform="claude_vertex", **platform_options)` creates
a Claude Vertex platform. Unknown platform names raise `ValueError`.

If a call-level `model` starts with `claude-` and the default platform is not
already `claude_vertex`, `LLM` lazily routes that call to a Claude Vertex
platform. The Claude-routed platform drops Gemini-only options such as
`enterprise`, `client`, and a default model when deriving platform options, but
keeps shared options such as `project` and `location`.

<a id="gemini-enterprise-platform"></a>
## Gemini Enterprise Platform

`GeminiEnterprisePlatform` adapts calls to the Google Gen AI SDK:

```python
from agentic_curator.wrappers import GeminiEnterprisePlatform
```

It lazily creates `google.genai.Client(...)` only when a real client is needed.
By default the client is created with `vertexai=True`. Passing `enterprise=True`
uses `enterprise=True` instead. Injecting `client=` avoids live SDK/client
creation and is how tests exercise request construction.

Generation requests call:

```python
client.models.generate_content(
    model=effective_model,
    contents=prompt,
    config=generation_config,
    ...
)
```

Default generation config includes temperature `0.2`, max output tokens `8192`,
candidate count `1`, and optional response schema/mime/safety fields. Instance
config is merged with defaults, call-level config overrides instance config for
that request, and `None` config values are removed before the provider call.
Template tools are used unless call-level `tools` are supplied.

Gemini responses prefer the first candidate content part text, then fall back to
`text`, `response`, and finally `str(response)`. If a Gemini platform is asked
to use a `claude-` model directly, it selects the Claude response adapter for
parsing.

<a id="claude-vertex-platform"></a>
## Claude Vertex Platform

`ClaudeVertexPlatform` adapts calls to Anthropic Claude on Vertex AI:

```python
from agentic_curator.wrappers import ClaudeVertexPlatform
```

It lazily creates `anthropic.AnthropicVertex(project_id=..., region=...)` only
when a real client is needed. The default location is `global`. Injecting
`client=` avoids live SDK/client creation.

Generation requests call:

```python
client.messages.create(
    model=effective_model,
    messages=[{"role": "user", "content": prompt}],
    ...
)
```

Claude config maps `max_output_tokens` to `max_tokens`, allows `max_tokens` to
override that mapping, preserves temperature, and translates `response_schema`
to an `output_config` JSON schema format. Gemini-specific options such as
`response_mime_type`, `candidate_count`, and `safety_settings` are not forwarded
by the Claude config mapper. Schema `type` values are normalized from
Vertex-style uppercase strings to lowercase JSON Schema strings.

Claude responses join text content blocks, then fall back through the shared
adapter behavior: `text`, `response`, candidate content part text, then
`str(response)`.

<a id="cli"></a>
## CLI

The installed console command is `cli_thematic_reviewer`. The module can also be
run directly:

```bash
.env/bin/python -m agentic_curator.cli.cli_thematic_reviewer --help
```

Inputs may be provided directly or from UTF-8 files:

- `--publication-text` or `--publication-text-file`
- `--theme` or `--theme-file`
- `--metadata` or `--metadata-file`
- `--title` or `--title-file`

For each input, the file option takes precedence over the direct value.
Metadata files are read as UTF-8 text and passed through as strings; they are
not parsed as JSON by the CLI.

By default the CLI writes pretty JSON to stdout. When `--out` is provided, it
writes pretty JSON to that file and keeps stdout quiet.

<a id="tests"></a>
## Tests

The test suite is pytest-based and avoids live provider calls by using fake
clients and fake LLM objects.

Test coverage includes:

- reviewer instantiation, public exports, missing legacy module, prompt
  construction, schema construction, and two-call ordering
- ontology harmonizer imports, root exports, and placeholder envelope behavior
- CLI direct inputs, UTF-8 file inputs, file precedence, stdout output, and
  `--out` writing
- provider facade selection, Claude model routing, request construction, config
  merging, schema normalization, tool overrides, and lazy import errors
- response adapter behavior for dicts, namespaces, candidate parts, Claude
  content blocks, and fallback string conversion

Run the suite with:

```bash
.env/bin/python -m pytest
```

<a id="local-development"></a>
## Local Development

Local files under `.dev/` are ignored and may contain large manual CLI fixtures
such as publication text, metadata, full prompts, and generated model responses.

Local VS Code workspace files under `.vscode/` are ignored. A local launch
configuration may point at:

```text
${workspaceFolder}/.env/bin/python
```

and set:

```text
PYTHONPATH=${workspaceFolder}/src
```

The repository currently keeps environment, editor, cache, and build artifacts
out of git. Check ignored files with:

```bash
git status --short --ignored
```

<a id="common-commands"></a>
## Common Commands

Install or refresh the local editable environment:

```bash
.env/bin/python -m pip install -e ".[dev]"
```

Run tests:

```bash
.env/bin/python -m pytest
```

Run CLI help:

```bash
.env/bin/python -m agentic_curator.cli.cli_thematic_reviewer --help
```

Run the CLI against local fixtures, if present:

```bash
.env/bin/python -m agentic_curator.cli.cli_thematic_reviewer \
  --publication-text-file .dev/thematic_reviewer_publication_text.txt \
  --theme-file src/agentic_curator/curators/thematic_reviewer/prompts/theme.md \
  --metadata-file .dev/thematic_reviewer_metadata.json \
  --title-file .dev/thematic_reviewer_title.txt \
  --out .dev/thematic_reviewer_decision.json
```
