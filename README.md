# agentic-curator

LLM-assisted thematic relevance review and ontology metadata utilities for life science publications.

## Description

`agentic-curator` helps review publication text against a thematic curation
target. Its main reviewer extracts evidence statements from publication content,
then judges whether those evidences satisfy the requested theme.

The package also includes ontology metadata utilities:

- `OntologyHarmonizer` is a metadata harmonization API scaffold that currently
  returns metadata unchanged.
- `OntoStore` stores OLS4-sourced ontology framework metadata and downloads
  configured ontology URLs.
- `LLM` routes generation calls to Gemini Enterprise or Claude on Vertex AI.

The reviewer asks model providers for JSON-formatted responses, but returns raw
generated text strings. Callers are responsible for JSON parsing, validation,
storage, and error handling.

## Installation

Install from the repository in editable mode:

```bash
python -m pip install -e ".[dev]"
```

For normal package use without test tools:

```bash
python -m pip install -e .
```

### Requirements

- Python `>=3.10`
- Runtime dependencies:
  - `google-genai>=1.72,<2`
  - `anthropic[vertex]>=0.107,<1`
  - `requests>=2,<3`
- Development dependency:
  - `pytest>=8`
- Provider credentials and project configuration for live Gemini or Claude
  Vertex AI calls.

## Quickstart

### Python

Use `ThematicReviewer` for the two-step evidence and judgement workflow. See
the [Python API guide](#python-api-guide) for all options.

```python
from agentic_curator import ThematicReviewer

reviewer = ThematicReviewer()
result = reviewer.review_relevancy(
    publication_text="Full publication text",
    theme="fibrosis",
    metadata={"organism": "human", "tissue": "lung"},
    title="Fibrosis atlas publication",
)

print(result["evidences"])
print(result["judgement"])
```

### CLI

Run the installed console script. See the [CLI guide](#cli-guide) for all
arguments.

```bash
cli_thematic_reviewer \
  --publication-text-file publication.txt \
  --theme-file theme.txt \
  --metadata-file metadata.json \
  --title "Publication title" \
  --out decision.json
```

### Ontology Utilities

Use `OntoStore` to inspect or download configured ontology frameworks. See the
[ontology guide](#ontology-guide) for defaults and download behavior.

```python
from agentic_curator.curators.ontology_harmonizer import OntoStore

store = OntoStore()
path = store.download("efo")
print(path)
```

### Docker

This repository does not currently provide a Dockerfile or Docker Compose
interface.

### Inputs & Outputs

Reviewer inputs:

- `publication_text`: full text or extracted publication content.
- `theme`: curation target or criteria.
- `metadata`: optional string, dictionary, list, or `None`.
- `title`: optional publication title.

Reviewer output:

```python
{
    "evidences": "raw provider-generated text",
    "judgement": "raw provider-generated text",
}
```

CLI output is the same reviewer result serialized as pretty-printed JSON. If
`--out` is supplied, JSON is written to that file; otherwise it is written to
stdout.

Ontology harmonizer output currently wraps extracted harmonization targets:

```python
{
    "publication_context": publication_context,
    "harmonization_targets": harmonization_targets,
    "target_paths": target_paths,
}
```

## Guide

### Python API Guide

The main APIs are exported from both `agentic_curator` and
`agentic_curator.curators`.

```python
from agentic_curator import OntologyHarmonizer, ThematicReviewer
from agentic_curator.curators.ontology_harmonizer import OntoStore
from agentic_curator.wrappers import LLM
```

#### Thematic Reviewer

`ThematicReviewer(llm=None)` accepts an optional LLM-like object with a
`generate_response(...)` method. If no object is provided, the reviewer lazily
creates `LLM()` on the first generation call.

| Method | Inputs | Output | Notes |
| --- | --- | --- | --- |
| `review_relevancy(publication_text=None, theme=None, metadata=None, title=None)` | Publication text, theme, metadata, title. | `{"evidences": str, "judgement": str}` | Runs evidence extraction, then final judging. |
| `extract_evidence(publication_text=None, theme=None, metadata=None, title=None)` | Publication text, theme, metadata, title. | Raw generated text string. | Loads `evidence_extraction.md` and requests JSON with an `evidences` array. |
| `judge_evidence(evidences, theme=None, title=None)` | Evidence text/object, theme, title. | Raw generated text string. | Loads `judge_evidence.md` and requests JSON with `judgement`, `reasoning`, and `confidence`. |

Dictionary and list metadata are inserted into prompts as sorted, indented JSON.
`None` values become empty prompt blocks.

#### LLM Facade

`LLM(platform="gemini_enterprise", **platform_options)` creates a provider
facade. Supported platforms are:

- `gemini_enterprise`
- `claude_vertex`

```python
from agentic_curator.wrappers import LLM

llm = LLM(
    platform="gemini_enterprise",
    project="my-gcp-project",
    location="global",
)

text = llm.generate_response(
    "Summarize this publication.",
    model="gemini-2.5-flash",
    config={"temperature": 0.2},
)
```

`LLM.generate_response(prompt, model=None, config=None, tools=None,
**extra_options)` delegates to the configured platform. If the model name starts
with `claude-` and the current platform is not `claude_vertex`, the facade
creates and caches a `ClaudeVertexPlatform` route using compatible platform
options.

#### Provider Adapters

Gemini Enterprise:

```python
from agentic_curator.wrappers import GeminiEnterprisePlatform

platform = GeminiEnterprisePlatform(
    project="my-gcp-project",
    location="global",
    model="gemini-2.5-flash",
    config={"temperature": 0.2},
)
text = platform.generate_response("Prompt text")
```

The Gemini adapter calls:

```python
client.models.generate_content(
    model=effective_model,
    contents=prompt,
    config=generation_config,
    tools=tools_if_any,
    **extra_options,
)
```

Claude Vertex:

```python
from agentic_curator.wrappers import ClaudeVertexPlatform

platform = ClaudeVertexPlatform(
    project="my-gcp-project",
    location="global",
    model="claude-opus-4-8",
)
text = platform.generate_response("Prompt text")
```

The Claude adapter calls:

```python
client.messages.create(
    model=effective_model,
    messages=[{"role": "user", "content": prompt}],
    max_tokens=max_output_tokens,
    temperature=temperature,
    output_config=json_schema_config_if_any,
    tools=tools_if_any,
    **extra_options,
)
```

Response adapters normalize provider-specific response shapes to a string. They
look for Claude content blocks, Gemini candidate parts, `text`, `response`, and
finally fall back to `str(response)`.

### CLI Guide

The console script is installed from `pyproject.toml`:

```bash
cli_thematic_reviewer --help
```

Equivalent module form:

```bash
python -m agentic_curator.cli.cli_thematic_reviewer --help
```

Options:

| Option | Description |
| --- | --- |
| `--publication-text` | Publication text supplied directly as a string. |
| `--publication-text-file` | UTF-8 file containing publication text. Overrides `--publication-text`. |
| `--theme` | Theme or curation criteria supplied directly as a string. |
| `--theme-file` | UTF-8 file containing the theme. Overrides `--theme`. |
| `--metadata` | Publication metadata supplied directly as a string. |
| `--metadata-file` | UTF-8 file containing metadata text. Overrides `--metadata`; the CLI does not parse it as JSON. |
| `--title` | Publication title supplied directly as a string. |
| `--title-file` | UTF-8 file containing the title. Overrides `--title`. |
| `--out` | Output file for pretty-printed JSON. If omitted, JSON is written to stdout. |

File arguments take precedence over direct string arguments. Provider and
runtime exceptions are not wrapped by the CLI. Stdout is reserved for JSON
unless `--out` is used.

### Ontology Guide

`OntologyHarmonizer(ontology_frameworks=None)` accepts either an ontology
framework dictionary or an `OntoStore`. If omitted, it creates a default
`OntoStore`.

```python
from agentic_curator import OntologyHarmonizer

harmonizer = OntologyHarmonizer()
result = harmonizer.harmonize_miniml_json(
    publication_context="Full publication text",
    miniml_json={
        "sample": [
            {
                "channel": [
                    {
                        "source": "Oral buccal mucosa",
                        "organism": [{"taxid": "9606", "value": "Homo sapiens"}],
                        "characteristics": [{"tag": "tissue", "value": "lung"}],
                        "molecule": "total RNA",
                    }
                ]
            }
        ]
    },
)
print(result)
```

`harmonize_miniml_json(publication_context=None, miniml_json=None,
ontostore=None, target_paths=None)` extracts targets from MINiML-style JSON,
then calls the lower-level target-based `harmonize(...)`. When `target_paths`
is omitted it builds paths for every `sample[*].channel[*]`, extracts
meaningful sample metadata (`source`, `molecule`, `organism`, and
`characteristics`), and dedupes by `pre_hz_field:pre_hz_label` while
preserving every source path only in an `occurrences` list.

`harmonize(publication_context=None, harmonization_targets=None,
ontostore=None, target_paths=None)` currently returns:

```python
{
    "publication_context": publication_context,
    "harmonization_targets": harmonization_targets or [],
    "target_paths": target_paths,
}
```

It does not call `LLM`, prompt files, provider SDKs, or ontology parsers yet.

`OntoStore` manages ontology framework URL configuration and downloads.

```python
from agentic_curator.curators.ontology_harmonizer import OntoStore

store = OntoStore(
    ontology_frameworks={
        "custom": {"url": "https://example.org/custom.owl", "version": "v1"},
    }
)
store.add_url("extra", "https://example.org/extra.owl", version="v2")
json_path = store.get("efo")
owl_path = store.downloaded_paths["efo"]
```

Default frameworks include EFO, MONDO, UBERON, HP, CL, ChEBI, PATO, OBI,
SNOMED CT, NCIT, and NCBITaxon. Built-in `title`, `description`, `version`, and
`url` metadata are sourced from OLS4 where available. Most default `url` values
use OLS4 `versionIri` values; EFO and UBERON use stable current URLs.

`download(name)` resolves `store.ontology_frameworks[name]["url"]`, skips
existing files, calls `requests.get(url, timeout=30)`, calls
`raise_for_status()`, writes bytes under the local `ontology_frameworks`
directory, records `store.downloaded_paths[name] = path`, and returns a `Path`.
`downloaded_paths` is an in-memory `dict[str, Path]` keyed by the ontology id
passed to `download()`.

`get(name, force=False)` is the ontology-serving entrypoint. It returns a JSON
`Path` under `storage_dir / "jsons"` after parsing the local `.owl` with
`Owl2json`. If the JSON already exists, `get()` returns it without reparsing. If
the `.owl` is missing, `get()` downloads it first. Use `get(name, force=True)`
to redownload the `.owl` and overwrite the parsed JSON.

### Code flow

#### Reviewer Orchestrator

```python
class ThematicReviewer:
    def review_relevancy(publication_text, theme, metadata, title):
        evidences = self.extract_evidence(
            publication_text=publication_text,
            theme=theme,
            metadata=metadata,
            title=title,
        )
        judgement = self.judge_evidence(
            evidences=evidences,
            theme=theme,
            title=title,
        )
        return {"evidences": evidences, "judgement": judgement}
```

#### Evidence Extraction

```python
def extract_evidence(publication_text, theme, metadata, title):
    prompt = _evidence_prompt(publication_text, theme, metadata, title)
    return _llm().generate_response(
        prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": _evidence_response_schema(),
        },
    )

def _evidence_prompt(...):
    initial_prompt = read_package_text("prompts/evidence_extraction.md")
    return join_blocks(
        initial_prompt,
        "Theme:", prompt_text(theme),
        "Title:", prompt_text(title),
        "Publication Text:", prompt_text(publication_text),
        "Metadata:", prompt_text(metadata),
    )
```

Internal calls:

- `_evidence_prompt(...)`
- `_prompt_text(...)`
- `_llm()`
- `LLM.generate_response(...)`
- provider adapter `generate_response(...)`
- Gemini `client.models.generate_content(...)` or Claude
  `client.messages.create(...)`

#### Evidence Judging

```python
def judge_evidence(evidences, theme, title):
    prompt = _judge_evidence_prompt(evidences, theme, title)
    return _llm().generate_response(
        prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": _judge_evidence_response_schema(),
        },
    )

def _judge_evidence_prompt(...):
    initial_prompt = read_package_text("prompts/judge_evidence.md")
    return join_blocks(
        initial_prompt,
        "Theme:", prompt_text(theme),
        "Title:", prompt_text(title),
        "Evidences:", prompt_text(evidences),
    )
```

#### LLM Routing

```python
class LLM:
    def generate_response(prompt, model=None, config=None, tools=None, **extra):
        platform = _platform_for_model(model)
        return platform.generate_response(
            prompt,
            model=model,
            config=config,
            tools=tools,
            **extra,
        )

    def _platform_for_model(model):
        if model startswith "claude-" and default platform is not claude_vertex:
            create cached ClaudeVertexPlatform
            return cached ClaudeVertexPlatform
        return configured platform
```

#### Provider Requests

```python
class GeminiEnterprisePlatform:
    def generate_response(prompt, model=None, config=None, tools=None, **extra):
        request = {
            "model": model or default_model,
            "contents": prompt,
            "config": merged_config_without_none,
            **extra,
        }
        if tools:
            request["tools"] = tools
        raw = client.models.generate_content(**request)
        return model_adapter.parse_response(raw)
```

```python
class ClaudeVertexPlatform:
    def generate_response(prompt, model=None, config=None, tools=None, **extra):
        request = {
            "model": model or default_model,
            "messages": [{"role": "user", "content": prompt}],
            **claude_config,
            **extra,
        }
        if tools:
            request["tools"] = tools
        raw = client.messages.create(**request)
        return ClaudeModelAdapter().parse_response(raw)
```

#### CLI Orchestrator

```python
def main(argv=None):
    args = parser.parse_args(argv)
    result = ThematicReviewer().review_relevancy(
        publication_text=input_value(args.publication_text, args.publication_text_file),
        theme=input_value(args.theme, args.theme_file),
        metadata=input_value(args.metadata, args.metadata_file),
        title=input_value(args.title, args.title_file),
    )
    write result as JSON to args.out or stdout
    return 0
```

#### Ontology Utilities

```python
class OntologyHarmonizer:
    def harmonize_miniml_json(publication_context, miniml_json, ontostore, target_paths):
        effective_paths = target_paths or target_extractor.build_miniml_sample_target_paths(miniml_json)
        targets = self.target_extractor.extract(miniml_json, start_paths=effective_paths)
        if target_paths is None:
            targets = self.target_extractor.dedupe_targets(targets)
        return self.harmonize(publication_context, targets, ontostore, effective_paths)

    def harmonize(publication_context, harmonization_targets, ontostore, target_paths):
        effective_store = ontostore or self.ontology_frameworks
        return {
            "publication_context": publication_context,
            "harmonization_targets": harmonization_targets or [],
            "target_paths": target_paths,
        }
```

Target extraction is handled by
`ontology_harmonizer.harmonization_target_extractor.HarmonizationTargetExtractor`;
the harmonizer keeps a private delegation wrapper for future harmonization work:

```python
class HarmonizationTargetExtractor:
    def build_miniml_sample_target_paths(miniml_json):
        walk every sample[*].channel[*]
        return paths for source, molecule, organism, and characteristics

    def extract(metadata, start_paths=None):
        if metadata is not dict/list:
            return []
        if start_paths is None:
            collect scalar targets from whole metadata tree
        for each start path or path spec:
            resolve JSON Pointer
            collect targets by mode: scalar, field_value, tag_value, or container_value
        return targets

    def dedupe_targets(targets):
        return one target per pre_hz_field:pre_hz_label with paths only in occurrences

def _extract_harmonization_targets(metadata, start_paths=None):
    return self.target_extractor.extract(metadata, start_paths=start_paths)
```

```python
class OntoStore:
    def get(name, force=False):
        owl_path = target_path(name)
        json_path = json_target_path(owl_path)
        if json_path.exists() and not force:
            return json_path
        if force:
            download_to_path(name, owl_path)
        elif owl_path.exists():
            downloaded_paths[name] = owl_path
        else:
            owl_path = download(name)
        return Owl2json(owl_path).write_json(json_path)

    def download(name):
        target = target_path(name)
        if target.exists():
            downloaded_paths[name] = target
            return target
        url = _framework_url(name)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        target.write_bytes(response.content)
        downloaded_paths[name] = target
        return target
```

## Docs

- [Documentation index](docs/index.md)
- [Codebase handoff](docs/codebase.md)
- [Code flow](docs/codebase.md#code-flow)
- [Reviewer workflow](docs/codebase.md#reviewer-workflow)
- [Ontology harmonizer](docs/codebase.md#ontology-harmonizer)
- [CLI behavior](docs/codebase.md#cli)
- [LLM wrapper](docs/codebase.md#llm-wrapper)
