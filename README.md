# agentic-curator

LLM-assisted thematic relevance review for life science publications.

## Description

`agentic-curator` reviews publication text against a thematic curation target.
The current package provides a thematic reviewer that first extracts relevant
evidence statements, then judges whether those evidences satisfy the theme. It
also exposes an ontology harmonizer placeholder so downstream callers can start
integrating against a stable harmonization API.

The reviewer requests JSON-formatted model responses but returns raw generated
text to callers. Parsing, validation, and downstream storage are left to the
calling application.

Runtime provider support currently includes Gemini through the Google Gen AI SDK
and Claude on Vertex AI through the Anthropic Vertex SDK.

## Installation

### Requirements

- Python `>=3.10`
- Runtime dependencies from `pyproject.toml`:
  - `google-genai>=1.72,<2`
  - `anthropic[vertex]>=0.107,<1`
- Development dependency:
  - `pytest>=8`
- Provider credentials and project configuration for live Gemini or Claude
  Vertex AI calls.

Install in editable mode:

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

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

`result["evidences"]` and `result["judgement"]` are raw provider-generated text
strings. The reviewer asks for JSON, but it does not parse or validate the JSON
before returning it.

## CLI

Run the installed console script:

```bash
cli_thematic_reviewer \
  --publication-text-file publication.txt \
  --theme-file theme.txt \
  --metadata-file metadata.json \
  --title "Publication title" \
  --out decision.json
```

Or run the module directly:

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

Logging: the CLI does not currently expose logging, verbosity, quiet, or debug
flags. Stdout is reserved for the JSON result unless `--out` is used. Provider
and runtime errors are not wrapped by the CLI.

## Python API

The main API is exported from both `agentic_curator` and
`agentic_curator.curators`.

```python
from agentic_curator import OntologyHarmonizer, ThematicReviewer
from agentic_curator.wrappers import LLM
```

### Orchestrator

| API | Inputs | Output | Notes |
| --- | --- | --- | --- |
| `ThematicReviewer(llm=None)` | Optional LLM-like object with `generate_response(...)`. | Reviewer instance. | Lazily creates `LLM()` if no object is supplied. |
| `review_relevancy(publication_text=None, theme=None, metadata=None, title=None)` | Publication text, theme, metadata, and title. | `{"evidences": str, "judgement": str}`. | Calls evidence extraction first, then evidence judging. |
| `OntologyHarmonizer()` | No constructor inputs. | Harmonizer instance. | Placeholder curator with no LLM or provider calls. |
| `harmonize(publication_text=None, metadata=None, title=None, ontology_frameworks=None)` | Publication text, metadata, title, and ontology framework dictionary. | `{"status": "placeholder", "publication_text": str | None, "metadata": str | dict | None, "title": str | None, "ontology_frameworks": dict, "matches": [], "targets": list}`. | Returns a stable placeholder envelope and editable metadata targets for integration work. |

### Reviewer Primitives

| API | Inputs | Output | Notes |
| --- | --- | --- | --- |
| `extract_evidence(publication_text=None, theme=None, metadata=None, title=None)` | Publication text, theme, metadata, and title. | Raw generated text string. | Uses the packaged evidence extraction prompt and requests JSON with an `evidences` array. |
| `judge_evidence(evidences, theme=None, title=None)` | Extracted evidences, theme, and title. | Raw generated text string. | Uses the packaged judge prompt and requests JSON with `judgement`, `reasoning`, and `confidence`. |

`metadata` may be a string, dictionary, list, or `None` in reviewer calls.
Dictionary and list values are inserted into prompts as sorted, indented JSON.

Ontology harmonization is currently a placeholder:

```python
from agentic_curator import OntologyHarmonizer

harmonizer = OntologyHarmonizer()
result = harmonizer.harmonize(
    publication_text="Full publication text",
    metadata={"organism": "human", "tissue": "lung"},
    title="Fibrosis atlas publication",
    ontology_frameworks={"anatomy": "UBERON", "cell_type": "CL"},
)
```

`result["matches"]` is an empty list until real harmonization behavior is added.
`result["targets"]` lists scalar metadata field-label pairs with JSON Pointer
paths so future harmonized field names and labels can be edited back into
structured metadata. Raw string metadata produces no targets.

### LLM Facade And Providers

| API | Inputs | Output | Notes |
| --- | --- | --- | --- |
| `LLM(platform="gemini_enterprise", **platform_options)` | Platform name plus provider options such as `project`, `location`, `model`, `config`, `tools`, or `client`. | Facade instance. | Supported platforms are `gemini_enterprise` and `claude_vertex`. |
| `LLM.generate_response(prompt, model=None, config=None, tools=None, **extra_options)` | Prompt text plus optional model, config, tools, and provider-specific request options. | Raw generated text string. | Claude model names route to Claude Vertex when the default platform is Gemini. |
| `GeminiEnterprisePlatform(...)` | Google Gen AI options, optional injected `client`, default config, and tools. | Provider adapter. | Calls `client.models.generate_content(...)`. |
| `ClaudeVertexPlatform(...)` | Anthropic Vertex options, optional injected `client`, default config, and tools. | Provider adapter. | Calls `client.messages.create(...)`. |

Provider config behavior:

- Gemini defaults include temperature `0.2`, max output tokens `8192`, candidate
  count `1`, and optional response schema/mime/safety fields.
- Claude maps `max_output_tokens` to `max_tokens`, preserves temperature, and
  translates response schemas to Anthropic `output_config` JSON schema format.
- Response adapters return text from provider-specific content blocks when
  possible, then fall back to `text`, `response`, candidate parts, or
  `str(response)`.

Logging: the Python API does not configure logging or expose logging options.
Provider SDK exceptions propagate to the caller.

## More Information

- [Codebase handoff](docs/codebase.md)
- [Code flow](docs/codebase.md#code-flow)
- [Reviewer workflow](docs/codebase.md#reviewer-workflow)
- [CLI behavior](docs/codebase.md#cli)
- [LLM wrapper](docs/codebase.md#llm-wrapper)
- [Gemini Enterprise platform](docs/codebase.md#gemini-enterprise-platform)
- [Claude Vertex platform](docs/codebase.md#claude-vertex-platform)
- [Documentation index](docs/index.md)

## Authors

Created by [jaychowcl](https://github.com/jaychowcl) @ [Saez-Rodriguez Group](https://saezlab.org) & [EMBL-EBI Functional Genomics Team](https://www.ebi.ac.uk/about/teams/functional-genomics/) on May 2026
