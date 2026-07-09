# agentic-curator

LLM-assisted thematic relevance review and ontology metadata harmonization for life science publications.

## Description

`agentic-curator` provides small curator workflows for publication metadata and
text. The current package includes:

- A thematic reviewer that extracts evidence from publication text and judges
  relevance to a curation theme.
- Ontology utilities that download OWL frameworks, convert them to JSON lookup
  indexes, and harmonize metadata labels against configured ontology terms.
- An LLM facade for Gemini Enterprise and Claude on Vertex AI, including a
  metadata-returning generation API for tool/citation-aware workflows.

## Installation

Install the package from this repository:

```bash
python -m pip install -e .
```

Install development tools as well:

```bash
python -m pip install -e ".[dev]"
```

### Requirements

- Python `>=3.10`
- Runtime dependencies:
  - `anthropic[vertex]>=0.107,<1`
  - `google-genai>=1.72,<2`
  - `rdflib>=7,<8`
  - `requests>=2,<3`
- Development dependency:
  - `pytest>=8`
- Live LLM calls require provider credentials and project configuration for
  Gemini Enterprise or Claude on Vertex AI.

## Quickstart

### Python Thematic Review

Use `ThematicReviewer` for the evidence extraction and judgement workflow. See
the [thematic reviewer guide](#thematic-reviewer) for all options.

```python
from agentic_curator import ThematicReviewer

reviewer = ThematicReviewer()
result = reviewer.review_relevancy(
    publication_text="Full publication text",
    theme="fibrosis",
    metadata={"organism": "human", "tissue": "lung"},
    title="Publication title",
)

print(result["evidences"])
print(result["judgement"])
```

### CLI Thematic Review

Use the installed console script for the same reviewer workflow. See the
[CLI guide](#cli-guide) for all arguments.

```bash
cli_thematic_reviewer \
  --publication-text-file publication.txt \
  --theme-file theme.txt \
  --metadata-file metadata.json \
  --title "Publication title" \
  --out decision.json
```

### Python Ontology Utilities

Use `OntoStore` to download and parse a configured ontology framework. See the
[ontology guide](#ontology-guide) for lookup and harmonization options.

```python
from agentic_curator.curators.ontology_harmonizer import OntoStore

store = OntoStore()
json_path = store.get("efo")
hits = store.lookup("lung", "efo")

print(json_path)
print(hits[:1])
```

### Python LLM Facade

Use `LLM` directly when you need provider-routed text or metadata responses.
See the [LLM guide](#llm-facade) for platform options.

```python
from agentic_curator.wrappers import LLM

llm = LLM(platform="gemini_enterprise", project="my-project", location="global")
text = llm.generate_response("Summarize this publication.")
metadata = llm.generate_response_with_metadata(
    "Find supporting ontology pages for lung.",
    tools=[{"type": "google_search"}],
)
```

### Docker

This repository does not currently provide a Dockerfile or Docker Compose
interface.

### Inputs & Outputs

The thematic reviewer accepts publication text, a curation theme, optional
metadata, and an optional title. Python callers may pass metadata as a string,
dictionary, list, or `None`; the CLI reads metadata as text.

The reviewer returns parsed JSON:

```python
{
    "evidences": {"evidences": [...]},
    "judgement": {
        "judgement": "relevant",
        "reasoning": "...",
        "confidence": "high",
    },
}
```

Ontology harmonization accepts one target, many targets, or MINiML-style JSON.
It returns the publication context, harmonized targets, selected strategy, and
target paths. `harmonize_miniml_json(...)` also returns the mutated
`miniml_json` with harmonized alternatives applied at each occurrence.

```python
{
    "publication_context": "...",
    "harmonization_targets": [...],
    "strategy": "websearch",
    "target_paths": [...],
    "miniml_json": {...},
}
```

## Guide

### Thematic Reviewer

Import the reviewer from either `agentic_curator` or `agentic_curator.curators`:

```python
from agentic_curator import ThematicReviewer
```

`ThematicReviewer(llm=None)` accepts an optional LLM-like object with a
`generate_response(...)` method. If none is supplied, it lazily creates
`agentic_curator.wrappers.LLM()` when the first generation call is made.

Public methods:

| Method | Purpose | Output |
| --- | --- | --- |
| `review_relevancy(publication_text=None, theme=None, metadata=None, title=None)` | Runs evidence extraction, then evidence judgement. | `{"evidences": ..., "judgement": ...}` |
| `extract_evidence(publication_text=None, theme=None, metadata=None, title=None)` | Builds the evidence prompt and requests JSON evidence. | Parsed dict or list |
| `judge_evidence(evidences, theme=None, title=None)` | Builds the judgement prompt from evidence and requests JSON judgement. | Parsed dict or list |

The reviewer loads packaged Markdown prompts from
`curators/thematic_reviewer/prompts/`. Dict and list values are rendered into
prompts as sorted, indented JSON. Invalid JSON text returned by the LLM raises
`ValueError`.

### CLI Guide

The installed command is `cli_thematic_reviewer`.

```bash
cli_thematic_reviewer --help
```

Arguments:

| Argument | Description |
| --- | --- |
| `--publication-text` | Publication text supplied directly. |
| `--publication-text-file` | UTF-8 file containing publication text. Takes precedence over `--publication-text`. |
| `--theme` | Theme supplied directly. |
| `--theme-file` | UTF-8 file containing the theme. Takes precedence over `--theme`. |
| `--metadata` | Metadata supplied directly as text. |
| `--metadata-file` | UTF-8 file containing metadata text. Takes precedence over `--metadata`. |
| `--title` | Title supplied directly. |
| `--title-file` | UTF-8 file containing the title. Takes precedence over `--title`. |
| `--out` | Output JSON file. If omitted, JSON is written to stdout. |

The CLI passes all inputs to `ThematicReviewer.review_relevancy(...)` and writes
pretty-printed JSON.

### Ontology Guide

Import ontology helpers from the ontology harmonizer package:

```python
from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore, Owl2json
```

`OntoStore(ontology_frameworks=None, fields=None, storage_dir=None)` stores
ontology framework configuration and normalized field metadata. It ships with
configured frameworks such as EFO, MONDO, UBERON, HP, CL, ChEBI, PATO, OBI,
SNOMED, NCIT, and NCBITaxon.

Common `OntoStore` methods:

| Method | Purpose |
| --- | --- |
| `configure_framework(name, ..., remove=False)` | Add, replace, or remove one framework configuration. |
| `add_url(name, url, ..., title=None, description=None)` | Add one URL-backed framework. |
| `add_urls(ontology_frameworks)` | Add many framework configs. |
| `download(name)` | Return an existing OWL path, or download URL-backed OWL to its configured path. |
| `get(name, force=False)` | Ensure the ontology JSON exists and return its path. |
| `lookup(label, ontology_id)` | Return all matching term metadata hits from label, id, accession, and IRI indexes. |
| `lookup_fields(field)` | Match a field name against configured field labels and aliases. |
| `harmonize_key(value)` | Lowercase, strip, and normalize lookup keys. |

`OntologyHarmonizer(ontostore=None, llm=None)` uses an `OntoStore` for exact
lookup and an injected or lazy `LLM` for assignment fallbacks.

Common `OntologyHarmonizer` methods:

| Method | Purpose |
| --- | --- |
| `harmonize(...)` | Harmonize one or more target dictionaries. |
| `harmonize_miniml_json(...)` | Extract targets from MINiML-style JSON, harmonize them, then apply alternatives back to the JSON object. |
| `lookup_label(...)` | Lookup `hz_label` against candidate ontology JSON indexes and mutate the target on match. |
| `assign_onto_framework(...)` | Ask the LLM which configured framework should be used when lookup fails. |
| `harmonize_field(...)` | Lookup or assign the harmonized metadata field. |
| `harmonize_label(...)` | Route label harmonization to the selected strategy handler. |
| `apply_targets(...)` | Add `hz_field`, `hz_label`, and alternatives back to MINiML occurrences. |

Supported harmonization strategies are `websearch` and `rag`; the default is
`websearch`. `rag` is currently a placeholder. The websearch handler searches
OLS4 first with the assigned ontology restriction, then falls back to
unrestricted OLS and an injected search client. The default search client is
`NullSearchClient`, which performs no network search.

Example:

```python
from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore

store = OntoStore(fields={"organism": {"label": "organism"}})
harmonizer = OntologyHarmonizer(ontostore=store)

result = harmonizer.harmonize(
    publication_context="Mouse lung fibrosis study.",
    target={
        "id": "target-1",
        "pre_hz_field": "Organism",
        "pre_hz_label": "Mus musculus",
        "ontology_ids": ["ncbitaxon"],
    },
    llm=False,
)
```

### LLM Facade

Import the facade and provider adapters from `agentic_curator.wrappers`:

```python
from agentic_curator.wrappers import (
    ClaudeVertexPlatform,
    GeminiEnterprisePlatform,
    LLM,
)
```

`LLM(platform="gemini_enterprise", **platform_options)` supports:

- `gemini_enterprise`
- `claude_vertex`

Methods:

| Method | Output |
| --- | --- |
| `generate_response(prompt, model=None, config=None, tools=None, **extra_options)` | Text string |
| `generate_response_with_metadata(prompt, model=None, config=None, tools=None, **extra_options)` | Dict with `text`, `raw_response`, `citations`, `tool_calls`, and `provider` |

If a call-level model starts with `claude-` while the default platform is
Gemini, the facade lazily creates and caches a Claude Vertex route.

Provider adapters:

- `GeminiEnterprisePlatform(...)` calls
  `google.genai.Client(...).models.generate_content(...)`.
- `ClaudeVertexPlatform(...)` calls
  `anthropic.AnthropicVertex(...).messages.create(...)`.

Both adapters support injected clients for tests and return parsed text through
the compatibility `generate_response(...)` method.

### Code flow

Thematic reviewer orchestration:

```python
def review_relevancy(publication_text, theme, metadata, title):
    evidences = extract_evidence(publication_text, theme, metadata, title)
    judgement = judge_evidence(evidences, theme, title)
    return {"evidences": evidences, "judgement": judgement}

def extract_evidence(...):
    prompt = evidence_prompt + labeled_inputs
    response = llm.generate_response(prompt, config=json_schema_config)
    return parse_json_response(response)

def judge_evidence(...):
    prompt = judge_prompt + labeled_evidences
    response = llm.generate_response(prompt, config=json_schema_config)
    return parse_json_response(response)
```

CLI orchestration:

```python
def main(argv):
    args = argparse.parse_args(argv)
    result = ThematicReviewer().review_relevancy(
        publication_text=input_or_file(args.publication_text),
        theme=input_or_file(args.theme),
        metadata=input_or_file(args.metadata),
        title=input_or_file(args.title),
    )
    write_json_to_outfile_or_stdout(result)
```

Ontology harmonizer orchestration:

```python
def harmonize_miniml_json(publication_context, miniml_json, target_paths=None):
    paths = target_paths or target_extractor.build_miniml_sample_target_paths(miniml_json)
    targets = target_extractor.extract(miniml_json, start_paths=paths)
    if target_paths is None:
        targets = target_extractor.dedupe_targets(targets)
    result = harmonize(publication_context, harmonization_targets=targets)
    result["miniml_json"] = apply_targets(miniml_json, result["harmonization_targets"])
    return result

def harmonize(publication_context, harmonization_targets, strategy="websearch"):
    targets = normalize_targets(harmonization_targets)
    for target in targets:
        harmonize target hz_field and hz_label keys
        lookup = lookup_label(target)
        if lookup fails:
            assign ontology framework with LLM when enabled
            harmonize field by store lookup or LLM assignment
            harmonize label with selected strategy handler
    return wrapper with publication_context, targets, strategy, target_paths
```

Ontology store flow:

```python
def get(ontology_id, force=False):
    if configured JSON exists and not force:
        ensure ontology.id is present
        return json_path
    if OWL is missing or force requires redownload:
        download configured URL to owl_path
    return Owl2json(owl_path).write_json(json_path, ontology_id=ontology_id)

def lookup(label, ontology_id):
    json_path = get(ontology_id)
    ontology = read JSON
    key = harmonize_key(label)
    hits = search label, id, accession, and iri indexes
    return deduped hits with ontology_id added
```

LLM and provider flow:

```python
def LLM.generate_response(prompt, **options):
    response = generate_response_with_metadata(prompt, **options)
    return response["text"]

def LLM.generate_response_with_metadata(prompt, model=None, **options):
    platform = claude_route_if_model_startswith_claude(model) or default_platform
    return platform.generate_response_with_metadata(prompt, model=model, **options)

def GeminiEnterprisePlatform.generate_response_with_metadata(...):
    raw = client.models.generate_content(model=..., contents=prompt, config=..., tools=...)
    return {"text": parsed_text, "raw_response": raw, "citations": ..., "tool_calls": ..., "provider": "gemini_enterprise"}

def ClaudeVertexPlatform.generate_response_with_metadata(...):
    raw = client.messages.create(model=..., messages=[...], tools=..., **config)
    return {"text": parsed_text, "raw_response": raw, "citations": [], "tool_calls": [], "provider": "claude_vertex"}
```

## Docs

- [Documentation index](docs/index.md)
- [Codebase handoff](docs/codebase.md)

## Authors

Created by [jaychowcl](https://github.com/jaychowcl) on June 2026
