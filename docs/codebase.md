<!--
=============================================================================
Authors
=============================================================================
Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
https://github.com/jaychowcl
https://saezlab.org
https://www.gsk.com/
=============================================================================
-->

# agentic-curator Codebase Handoff

This document summarizes the live `agentic_curator` package. It is intended as
a compact handoff for humans and agents working in this repository.

<a id="project-purpose-and-layout"></a>
## Project Purpose And Layout

`agentic-curator` provides LLM-assisted curation utilities for life science
publications. The current package focuses on publication evidence extraction,
final relevance judging, ontology harmonizer scaffolding, and provider
adapters for Gemini and Claude on Vertex AI.

Tracked project layout:

```text
pyproject.toml
requirements.txt
README.md
LICENSE
docs/
  codebase.md
  index.md
src/agentic_curator/
  __init__.py
  cli/
    __init__.py
    cli_ontology_harmonizer.py
    cli_thematic_reviewer.py
    common.py
  curators/
    __init__.py
    json_response.py
    ontology_harmonizer/
      __init__.py
      harmonization_target_extractor.py
      harmonizer.py
      normalization.py
      ontology_store.py
      owl2json.py
      strategy_handlers.py
      prompts/
        assign_field.md
        assign_onto_framework.md
        judge_lookup.md
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
  test_cli_ontology_harmonizer.py
  test_cli_thematic_reviewer.py
  test_curator_llm_wrappers.py
  test_ontology_harmonizer.py
  test_owl2json.py
  test_repository_metadata.py
  test_thematic_reviewer.py
  test_workflow_logging.py
```

Ignored local development artifacts include `.dev/`, `.env/`, `.vscode/`,
Python caches, pytest caches, build outputs, and editable-install metadata.

Tracked comment-capable project files carry a distinctive authors header at the
top of the file. Python, TOML, and `.gitignore` use `#` comments; non-prompt
Markdown docs use a leading HTML comment. `README.md` keeps authorship in its
`## Authors` section and includes a citation subsection. `LICENSE` and packaged
prompt Markdown files under `curators/*/prompts/` are intentionally left
without author comment headers.

<a id="runtime-and-packaging"></a>
## Runtime And Packaging

The package uses a `src/` layout with setuptools:

- project name: `agentic-curator`
- import package: `agentic_curator`
- Python requirement: `>=3.10`
- runtime dependencies: `anthropic[vertex]>=0.107,<1`, `google-genai>=1.72,<2`, `rdflib>=7,<8`, and `requests>=2,<3`
- dev extra: `pytest>=8`
- `requirements.txt` mirrors the direct runtime/dev dependencies for pip-based
  environment bootstrap and includes `-e .`
- console scripts:
  - `cli_thematic_reviewer = "agentic_curator.cli.cli_thematic_reviewer:main"`
  - `cli_ontology_harmonizer = "agentic_curator.cli.cli_ontology_harmonizer:main"`
- package data: `agentic_curator/curators/*/prompts/*.md`

The local development convention is to use `.env/bin/python`. A typical setup
command is:

```bash
.env/bin/python -m pip install -e ".[dev]"
```

Equivalent requirements bootstrap:

```bash
.env/bin/python -m pip install -r requirements.txt
```

`pyproject.toml` remains the canonical packaging source.

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

`agentic_curator.curators.ontology_harmonizer` exports ontology-specific helper
classes including `OntoStore`, `Owl2json`, `OlsClient`,
`NullSearchClient`, `GeminiGroundedSearchClient`, `WebsearchStrategyHandler`,
and `RagStrategyHandler`.

`ThematicReviewer(llm=None)` accepts an optional LLM-like object. If no object is
provided, the reviewer lazily creates `agentic_curator.wrappers.LLM()` on the
first generation call.

Main methods:

- `review_relevancy(publication_text=None, theme=None, metadata=None, title=None) -> dict`
- `extract_evidence(publication_text=None, theme=None, metadata=None, title=None) -> dict | list`
- `judge_evidence(evidences, theme=None, title=None) -> dict | list`

`metadata` may be a string, dictionary, list, or `None` when used by reviewer
prompt helpers. The reviewer asks providers for JSON output, passes dict/list
responses through, parses JSON text with `json.loads(...)`, and raises
`ValueError` for invalid JSON text.

<a id="ontology-harmonizer"></a>
## Ontology Harmonizer

`agentic_curator.curators.ontology_harmonizer.OntologyHarmonizer` is the
metadata harmonization curator. It uses `OntoStore` for exact ontology lookup
and an injected or lazy `LLM` for framework assignment when lookup fails.

Public methods:

- `apply_targets(miniml_json, harmonization_targets) -> dict | list | None`
- `assign_field(target, *, publication_context, ontostore) -> dict`
- `assign_onto_framework(target, *, publication_context, ontostore) -> dict`
- `harmonize_miniml_json(publication_context=None, miniml_json=None, ontostore=None, target_paths=None, strategy="websearch", lookup_llm_judge=False, lookup_llm_threshold=2, llm=True) -> dict`
- `harmonize(publication_context=None, harmonization_targets=None, target=None, strategy="websearch", ontostore=None, target_paths=None, lookup_llm_judge=False, lookup_llm_threshold=2, llm=True) -> dict`
- `harmonize_field(target, *, publication_context, ontostore) -> Any`
- `harmonize_label(target, *, publication_context, ontostore, strategy) -> dict`
- `judge_lookup(target, *, publication_context, hits) -> dict`
- `lookup_label(target, *, publication_context, ontostore, strategy) -> Any`

`harmonize_miniml_json(...)` extracts targets from MINiML-style JSON with
`HarmonizationTargetExtractor`, then calls `harmonize(...)`. When `target_paths`
is omitted, it builds paths for every `sample[*].channel[*]`, extracts
meaningful sample metadata (`source`, `molecule`, `organism`, and
`characteristics`), and dedupes targets by exact
`pre_hz_field:pre_hz_label` while preserving every source path in
`occurrences`. Supplying `target_paths` keeps explicit path extraction behavior.
After harmonization, `harmonize_miniml_json(...)` calls `apply_targets(...)`,
mutates the supplied MINiML JSON in place, and includes that same object in the
return wrapper under `miniml_json`.

The lower-level `harmonize(...)` returns a target wrapper:

```python
{
    "publication_context": publication_context,
    "harmonization_targets": normalized_targets,
    "strategy": "websearch",
    "target_paths": target_paths,
}
```

`apply_targets(miniml_json, harmonization_targets)` applies target-level
`hz_field` and `hz_label` to each occurrence path. Scalar `field_value` and
`scalar` occurrences keep the original scalar and add a sibling
`<field>_hz_alternatives` list containing `{hz_field, hz_label, target_id}`.
Object-shaped `tag_value` and `container_value` occurrences add `hz_field`,
`hz_label`, and `hz_alternatives` to the occurrence parent object. Multiple
hits for the same field are appended as alternatives, exact duplicate
alternatives are ignored, and malformed or unresolved occurrence paths are
skipped.

`publication_context` may be a string or `None`, `miniml_json` may be a
dictionary, list, or `None`, `harmonization_targets` may be a list of extracted
target dictionaries, a single target dictionary, or `None`, and `target` may be
a single target dictionary. Passing both `target` and `harmonization_targets`
raises `ValueError`. Supported strategies are `websearch` and `rag`; the
default strategy is `websearch`. A per-call `ontostore` override must be an
`OntoStore`.
`harmonize(...)` calls `lookup_label(...)` once for each normalized target. On a
match, `lookup_label(...)` mutates the target with `ontology_match=True`,
`ontology_id`, selected `ontology_lookup`, and all `ontology_lookup_hits`.
Before lookup, the harmonizer normalizes working `hz_field` and `hz_label`
values from existing `hz_*` fields or from `pre_hz_field` and `pre_hz_label`:
lowercase, trim, strip edge punctuation, and collapse whitespace to underscores.
The same normalization is applied to occurrence-level values when a target has
`occurrences`. By default lookup selects the first hit without an LLM. When
`lookup_llm_judge=True` and at least `lookup_llm_threshold` hits exist
(default `2`), the LLM receives the hits, publication context, and target
context and returns `decision`, `confidence`, and `reason`; the judgement is
stored at `ontology_lookup_judgement`. When `lookup_label(...)` returns
`False`, `harmonize(...)` marks the target unmatched and, when `llm=True`, calls
`assign_onto_framework(...)` as the fallback assignment step. The fallback
prompts the LLM with the target, publication context, and sanitized candidate
ontology framework metadata. Framework prompt metadata includes only `id`,
`title`, `description`, and `version`; download URLs and configured file paths
remain internal to `OntoStore`. It parses JSON with `decision`, `confidence`,
and `reason`, stores it at `ontology_framework_assignment`, and sets
`ontology_id` when `decision` is a configured framework ID.
`harmonize(...)` then calls `harmonize_field(...)` for every target, whether
the first ontology lookup matched or missed. Field harmonization uses
`OntoStore.lookup_fields(...)` and falls back to LLM-backed
`assign_field(...)` only when `llm=True`. When the first lookup missed,
`harmonize(...)` calls `harmonize_label(...)` only for `websearch` and `rag`.
After a strategy handler returns, the harmonizer performs a post-strategy
`OntoStore.lookup(...)` for the current `hz_label`, preferring the target's
stored `ontology_id` when that framework exists in `OntoStore`. If that lookup
finds hits, it refreshes `ontology_id`, `ontology_lookup`,
`ontology_lookup_hits`, and `ontology_match=True`; if it misses, the existing
strategy result remains unchanged. This second lookup uses normal
`OntoStore.lookup(...)` behavior, including download/parse for URL-backed
configured frameworks. The websearch handler uses OLS4 restricted to the
assigned `ontology_id`, then falls back to
unrestricted OLS plus an injected web search client. `NullSearchClient` is the
default and performs no network work. `GeminiGroundedSearchClient` is an
opt-in Google Search grounding client backed by the LLM facade; it calls
`generate_response_with_metadata(..., tools=[{"type": "google_search"}])`,
normalizes returned citation annotations into `web_hits`, stores the grounded
response at `last_response`, and records quota or provider failures at
`last_error`. Its per-process `request_budget` defaults to `100` to avoid
unbounded requests against Gemini project-level RPM/TPM/RPD quotas. Strategy
results always include `strategy`, `status`, `decision`, `confidence`, and
`reason`, and include `web_search_error` when the search client reports one.
The `rag` strategy currently routes to a placeholder handler.

`OntologyHarmonizer(ontostore=None, llm=None)` creates a default `OntoStore`
when no store is supplied and lazily creates `LLM()` only when framework
assignment needs generation. Custom ontology framework dictionaries should be
passed to `OntoStore(ontology_frameworks=...)`, then injected into the
harmonizer. A per-call `ontostore` can override the constructor value for
harmonization. The effective store is validated before lookup and assignment.
Targets may constrain
lookup by setting `ontology_frameworks` or `ontology_ids` to a string or
sequence of framework IDs. Without an explicit constraint, `lookup_label(...)`
searches only path-backed frameworks with existing local OWL or JSON files,
avoiding implicit downloads of every built-in URL-backed framework.

`OntoStore`, `Owl2json`, and `Owl2jsonParseError` are exported from
`agentic_curator.curators.ontology_harmonizer`. `OntoStore` stores ontology
framework config, downloads named frameworks, parses OWL into JSON, and looks up
terms. `Owl2json` parses RDF/XML `.owl` files into a term-centric JSON
dictionary.

`OntoStore(fields=...)` also stores a normalized field dictionary used before
strategy routing. `lookup_fields(field)` normalizes the incoming field and
matches it against field keys plus each metadata dict's `label` and `aliases`.
It returns matched metadata with a `field` key for the canonical field ID, or
`False` when no configured field matches.

Framework config uses a nested dictionary:

```python
{
    "efo": {
        "title": "Experimental Factor Ontology",
        "url": "http://www.ebi.ac.uk/efo/efo.owl",
        "version": None,
        "description": "...",
    },
    "mondo": {
        "title": "Mondo Disease Ontology",
        "url": "http://purl.obolibrary.org/obo/mondo/releases/2026-06-02/mondo-international.owl",
        "version": "2026-06-02",
        "description": "...",
    },
    "CL": {"url": "https://example.org/cl.owl"},
    "UBERON": {"url": "https://example.org/uberon.owl", "version": "v2"},
}
```

Every `OntoStore` starts with built-in framework configs for EFO, MONDO,
UBERON, HP, CL, ChEBI, PATO, OBI, SNOMED CT, NCIT, and NCBITaxon unless a
caller overrides those entries in the constructor. Each built-in config
includes OLS4-sourced `title`, `description`, `version`, and `url` metadata.
Most default `url` values use OLS4 `versionIri` values; EFO and UBERON use
stable current URLs. Framework configs are normalized at construction time with
concrete `owl_path` and `json_path` fields. `OntoStore.add_url(...)` adds or
replaces one URL-backed framework and accepts optional `owl_path`, `json_path`,
`title`, `description`, and `version` metadata. `OntoStore.add_urls(...)` merges
a framework mapping with the same supported fields. `configure_framework(...)`
is the lower-level add/replace/remove API. Removal deletes the framework entry.
`OntoStore.get(name, force=False)` is the ontology-serving entrypoint. It
returns the parsed JSON `Path` stored in `ontology_frameworks[name]["json_path"]`,
reusing existing JSON unless `force=True`. Existing JSON is repaired in place
when `ontology["id"]` is missing or does not match the requested framework name.
When JSON is missing for a URL-backed framework, it parses the configured
`owl_path` if present or downloads the `.owl` there first. With `force=True`,
URL-backed frameworks redownload the `.owl` before reparsing, and path-backed
frameworks reparse the configured local `owl_path` without network I/O.
`OntoStore.lookup(label, ontology_id)` calls `get(ontology_id)`, loads the JSON
from the configured `json_path`, normalizes the query with
`harmonize_key(...)`, and searches `terms["label"]`, `terms["id"]`,
`terms["accession"]`, and `terms["iri"]` in that order. It returns a list of all
matched term dicts with `ontology_id` added, flattening list-valued index
entries and deduping hits while preserving search order. Existing cached JSON
with raw keys remains usable because lookup normalizes stored index keys when a
direct normalized-key lookup misses. It returns `[]` when no index contains the
normalized label.
`OntoStore.download(name)` downloads only URL-backed frameworks with
`requests.get(url, timeout=30)`, calls `raise_for_status()`, and returns the
configured `owl_path`. Path-backed frameworks validate and return the configured
local `owl_path` without calling `requests`.

When no explicit path is supplied, URL-backed `.owl` files are saved under
`src/agentic_curator/curators/ontology_harmonizer/ontology_frameworks/` using
the URL basename, and parsed JSON files are saved under the sibling `jsons/`
directory within `storage_dir`. The default storage directory is ignored by
git. Existing downloaded files are skipped by `download()`, and existing JSON is
reused by `get()` after `ontology["id"]` repair unless `force=True`. Unknown
framework names raise `KeyError`; missing or invalid URLs or paths raise
`ValueError`, and missing local path files raise `FileNotFoundError`.

`Owl2json(owl_path)` accepts a local `.owl` path and uses RDFLib to parse it as
RDF/XML. `parse(ontology_id=None)` returns:

```python
{
    "ontology": {
        "id": "chebi",
        "iri": "...",
        "version_iri": "...",
        "title": "...",
        "description": "...",
        "version": "...",
        "license": "...",
    },
    "terms": {
        "accession": {
            "chebi:100": {
                "iri": "http://purl.obolibrary.org/obo/CHEBI_100",
                "accession": "CHEBI:100",
                "title": "...",
                "description": "...",
                "parents": ["CHEBI:16114"],
                "parent_iris": ["http://purl.obolibrary.org/obo/CHEBI_16114"],
                "synonyms": {"exact": [], "related": [], "broad": [], "narrow": []},
                "xrefs": [],
                "subsets": [],
                "deprecated": False,
                "replaced_by": None,
                "properties": {},
            }
        },
        "id": {"chebi:100": "..."},
        "iri": {"http://purl.obolibrary.org/obo/chebi_100": "..."},
        "label": {"term_label": ["..."]},
    },
}
```

Top-level terms are URI-backed `owl:Class` subjects; blank-node class
expressions are ignored as entries. Labels come from `rdfs:label`, descriptions
from `obo:IAO_0000115`, accessions from `oboInOwl:id` with an OBO IRI fallback,
parents from URI-valued `rdfs:subClassOf`, synonyms and xrefs from common
`oboInOwl` predicates, deprecation from `owl:deprecated`, and replacements from
`obo:IAO_0100001`. The `terms` object indexes the same normalized term records
by harmonized accession, ID, IRI, and label keys. Label values are lists because
labels are not guaranteed unique. Terms without accessions or labels are
omitted from those specific indexes but remain available by IRI. Unmapped
literal annotations are preserved in `properties` by predicate IRI.
`write_json(output_path, ontology_id=None)` writes deterministic pretty JSON and
returns the output path. HTML-like files, such as a bad `.owl` download that
starts with `<!DOCTYPE html>` or `<html`, and RDFLib parse failures raise
`Owl2jsonParseError`.

`HarmonizationTargetExtractor` lives in
`ontology_harmonizer/harmonization_target_extractor.py` and extracts editable
metadata targets for ontology harmonization. `OntologyHarmonizer` owns
`self.target_extractor`, keeps `_extract_harmonization_targets(...)` as a
private compatibility wrapper around `self.target_extractor.extract(...)`, and
returns harmonized targets from `harmonize(...)`. The extractor still supports
root-level default path specs:

```python
[
    {"path": "/organism", "mode": "container_value"},
    {"path": "/characteristics", "mode": "tag_value"},
]
```

`HarmonizationTargetExtractor.extract(metadata, start_paths=...)` traverses
dictionaries and lists, skips raw string metadata, skips `None`, and does not
create targets for scalar list items without an object key. Raw extracted targets
includes:

```python
{
    "id": "target-0",
    "source": "metadata",
    "pre_hz_field": "tissue",
    "pre_hz_label": "lung",
    "pre_hz_field_path": "/sample/tissue",
    "pre_hz_label_path": "/sample/tissue",
    "parent_path": "/sample",
    "hz_field": "tissue",
    "hz_label": "lung",
}
```

After `dedupe_targets(...)`, target-level paths are moved into `occurrences`:

```python
{
    "id": "target-0",
    "source": "metadata",
    "pre_hz_field": "tissue",
    "pre_hz_label": "lung",
    "hz_field": "tissue",
    "hz_label": "lung",
    "occurrences": [
        {
            "pre_hz_field_path": "/sample/tissue",
            "pre_hz_label_path": "/sample/tissue",
            "parent_path": "/sample",
            "hz_field": "tissue",
            "hz_label": "lung",
        }
    ],
}
```

`pre_hz_field_path`, `pre_hz_label_path`, and `parent_path` use JSON
Pointer-style paths with escaped path segments (`~` becomes `~0`, `/` becomes
`~1`). Deduped targets keep these paths only inside `occurrences`. These
coordinates drive `apply_targets(...)` after harmonization. `hz_field` and
`hz_label` are initialized from the extracted values, then mutated by lookup,
field assignment, and label strategy steps.

`HarmonizationTargetExtractor.extract(metadata, start_paths=None)` can also
receive a list of JSON Pointer start paths or path specs. When `start_paths` is
omitted, extraction starts at the metadata root. Plain string paths use the
default `scalar` mode and preserve the original behavior: only resolved
dictionaries or lists are traversed, output target paths remain absolute from
the metadata root, and missing, invalid, scalar, or unresolvable start paths are
skipped. The empty string `""` means the metadata root.

Path specs allow selected metadata subtrees to use domain-aware extraction
modes:

```python
start_paths=[
    "/sample",
    {"path": "/characteristics", "mode": "tag_value"},
    {"path": "/organism", "mode": "container_value"},
]
```

Supported modes:

- `scalar`: default mode; extracts each scalar dictionary field as a separate
  target.
- `tag_value`: for objects such as `{"tag": "tissue", "value": "lung"}`;
  emits one target with `pre_hz_field_path` pointing to `tag` and
  `pre_hz_label_path` pointing to `value`.
- `container_value`: for containers such as
  `"organism": [{"taxid": "9606", "value": "Homo sapiens"}]`; emits one target
  per nested object with a scalar `value`, using the selected container path as
  the pre-harmonization field path.

Invalid path specs, unsupported modes, missing `tag`/`value` fields, non-scalar
labels, and scalar start paths are skipped.

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

1. CLI users call `cli_thematic_reviewer` or `cli_ontology_harmonizer`. The
   CLI helpers read direct or UTF-8 file inputs, parse JSON inputs where the
   exposed curator method expects structured data, configure stderr logging
   from `--verbosity`, and write pretty JSON to stdout or `--out`.
2. `review_relevancy()` calls `extract_evidence(...)`, then passes that parsed
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
6. Curator methods that request JSON parse dict/list or JSON text responses
   before returning.

The CLI configures standard-library logging to stderr. Curator workflows emit
INFO logs for orchestration boundaries and DEBUG logs for detailed internal
choices. Provider exceptions are not wrapped; they propagate to callers.

`OntologyHarmonizer.harmonize(...)` normalizes single-target input, validates
the selected strategy, first assigns ontology metadata through
`OntoStore.lookup(...)`, then always calls `harmonize_field(...)`.
`assign_onto_framework(...)`, label strategy routing, and post-strategy
`OntoStore.lookup(...)` enrichment run only when the first exact lookup fails.

<a id="method-orchestrator-pseudocode"></a>
## Method Orchestrator Pseudocode

This section traces the main classes and methods by call flow. Names here match
the implementation so an agent can jump directly from a pseudocode step to the
corresponding method.

### `ThematicReviewer`

Role: high-level thematic curation orchestrator. It owns the two-step reviewer
workflow and delegates generation to an injected LLM-like object or a lazy
`LLM()`.

```python
class ThematicReviewer:
    def __init__(llm=None):
        self.llm = llm

    def review_relevancy(publication_text=None, theme=None, metadata=None, title=None):
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

Internal calls from `review_relevancy()`:

- `extract_evidence(...)`
- `judge_evidence(...)`

External API calls reached indirectly:

- `LLM.generate_response(...)`
- then either `google.genai.Client.models.generate_content(...)` or
  `anthropic.AnthropicVertex.messages.create(...)`, depending on platform/model.

```python
def extract_evidence(publication_text=None, theme=None, metadata=None, title=None):
    prompt = self._evidence_prompt(
        publication_text=publication_text,
        theme=theme,
        metadata=metadata,
        title=title,
    )
    response = self._llm().generate_response(
        prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": self._evidence_response_schema(),
        },
    )
    return parse_json_response(response)
```

Internal calls from `extract_evidence()`:

- `_evidence_prompt(...)`
- `_llm()`
- `_evidence_response_schema()`
- `parse_json_response(...)`

```python
def judge_evidence(evidences, theme=None, title=None):
    prompt = self._judge_evidence_prompt(
        evidences=evidences,
        theme=theme,
        title=title,
    )
    response = self._llm().generate_response(
        prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": self._judge_evidence_response_schema(),
        },
    )
    return parse_json_response(response)
```

Internal calls from `judge_evidence()`:

- `_judge_evidence_prompt(...)`
- `_llm()`
- `_judge_evidence_response_schema()`
- `parse_json_response(...)`

```python
def _llm():
    if self.llm is None:
        self.llm = LLM()
    return self.llm
```

```python
def _evidence_prompt(publication_text=None, theme=None, metadata=None, title=None):
    initial_prompt = read_package_text("prompts/evidence_extraction.md").strip()
    return "\n".join([
        initial_prompt,
        "Theme:", self._prompt_text(theme), "",
        "Title:", self._prompt_text(title), "",
        "Publication Text:", self._prompt_text(publication_text), "",
        "Metadata:", self._prompt_text(metadata),
    ]).lstrip("\n")

def _judge_evidence_prompt(evidences, theme=None, title=None):
    initial_prompt = read_package_text("prompts/judge_evidence.md").strip()
    return "\n".join([
        initial_prompt,
        "Theme:", self._prompt_text(theme), "",
        "Title:", self._prompt_text(title), "",
        "Evidences:", self._prompt_text(evidences),
    ]).lstrip("\n")

def _prompt_text(value):
    if value is None:
        return ""
    if value is dict or list:
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)
```

### `OntologyHarmonizer`

Role: metadata harmonization curator. It delegates structured edit target
discovery to `HarmonizationTargetExtractor` and ontology JSON lookup to an
injected `OntoStore`.

```python
class OntologyHarmonizer:
    DEFAULT_TARGET_PATHS = HarmonizationTargetExtractor.DEFAULT_TARGET_PATHS

    def __init__(ontostore=None, llm=None):
        self.ontostore = OntoStore() if ontostore is None else ontostore
        self.llm = llm
        self.target_extractor = HarmonizationTargetExtractor()

    def harmonize(
        publication_context=None,
        harmonization_targets=None,
        target=None,
        strategy="websearch",
        ontostore=None,
        target_paths=None,
        lookup_llm_judge=False,
        lookup_llm_threshold=2,
        llm=True,
    ):
        effective_ontostore = self._effective_ontostore(ontostore)
        strategy = self._normalize_strategy(strategy)
        targets = self._normalize_targets(
            harmonization_targets=harmonization_targets,
            target=target,
        )
        for target in targets:
            self._harmonize_target(target, effective_ontostore)
            lookup = self.lookup_label(
                target,
                publication_context=publication_context,
                ontostore=effective_ontostore,
                strategy=strategy,
                lookup_llm_judge=lookup_llm_judge,
                lookup_llm_threshold=lookup_llm_threshold,
            )
            if not lookup:
                self._mark_ontology_miss(target)
                if llm:
                    self.assign_onto_framework(
                        target,
                        publication_context=publication_context,
                        ontostore=effective_ontostore,
                    )
            self.harmonize_field(
                target,
                publication_context=publication_context,
                ontostore=effective_ontostore,
                llm=llm,
            )
            if not lookup:
                if strategy in self.STRATEGY_HANDLERS:
                    self.harmonize_label(
                        target,
                        publication_context=publication_context,
                        ontostore=effective_ontostore,
                        strategy=strategy,
                    )
                    self._lookup_harmonized_label(
                        target,
                        ontostore=effective_ontostore,
                    )
        return {
            "publication_context": publication_context,
            "harmonization_targets": targets,
            "strategy": strategy,
            "target_paths": target_paths,
        }

    def lookup_label(
        target,
        *,
        publication_context,
        ontostore,
        strategy,
        lookup_llm_judge=False,
        lookup_llm_threshold=2,
    ):
        self._harmonize_target(target, ontostore)
        label = target.get("hz_label")
        if label is None:
            return False

        hits = []
        for ontology_id in self._candidate_ontology_ids(target, ontostore):
            hits.extend(ontostore.lookup(str(label), ontology_id))
        if hits:
            selected = hits[0]
            if lookup_llm_judge and len(hits) >= lookup_llm_threshold:
                judgement = self.judge_lookup(target, publication_context, hits)
                selected = hit whose id equals judgement["decision"]
                target["ontology_lookup_judgement"] = judgement
            target["ontology_id"] = selected["ontology_id"]
            target["ontology_lookup"] = selected
            target["ontology_lookup_hits"] = hits
            target["ontology_match"] = True
            return selected

        return False

    def assign_onto_framework(
        target,
        *,
        publication_context,
        ontostore,
    ):
        self._mark_ontology_miss(target)
        framework_configs = self._assignment_candidate_frameworks(target, ontostore)
        framework_configs contains only id, title, description, and version
        prompt = self._assign_onto_framework_prompt(
            target=target,
            publication_context=publication_context,
            ontology_frameworks=framework_configs,
        )
        response = self._llm().generate_response(
            prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": self._assign_onto_framework_response_schema(),
            },
        )
        assignment = parse_json_response(response)
        require assignment contains decision, confidence, and reason
        target["ontology_framework_assignment"] = assignment
        if assignment["decision"] is a configured framework ID:
            target["ontology_id"] = assignment["decision"]
        return assignment

    def harmonize_field(
        target,
        *,
        publication_context,
        ontostore,
        llm=True,
    ):
        lookup = ontostore.lookup_fields(target["hz_field"])
        if lookup:
            target["hz_field"] = lookup["field"]
            target["field_lookup"] = lookup
            return lookup
        if not llm:
            return False
        return self.assign_field(
            target,
            publication_context=publication_context,
            ontostore=ontostore,
        )

    def assign_field(
        target,
        *,
        publication_context,
        ontostore,
    ):
        prompt = self._assign_field_prompt(
            target=target,
            publication_context=publication_context,
            fields=ontostore.fields,
        )
        response = self._llm().generate_response(
            prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": self._assign_field_response_schema(),
            },
        )
        assignment = parse_json_response(response)
        require assignment contains decision, confidence, reason, and new_field
        target["field_assignment"] = assignment
        target["hz_field"] = normalized assignment decision
        if assignment["new_field"]:
            ontostore.fields[target["hz_field"]] = assignment metadata
        return assignment

    def harmonize_label(
        target,
        *,
        publication_context,
        ontostore,
        strategy,
    ):
        handler_class = self.STRATEGY_HANDLERS[strategy]
        return handler_class().handle(
            target,
            publication_context=publication_context,
            ontostore=ontostore,
        )

    class WebsearchStrategyHandler:
        restricted_hits = OLS search(label, ontology=target["ontology_id"], rows=25)
        if restricted_hits:
            require OLS ontology metadata has id, title, description, version, url
            ontostore.configure_framework(...)
            set target ontology lookup fields
            return matched strategy result with decision, confidence, reason

        unrestricted_hits = OLS search(label, rows=25)
        web_hits = search_client.search(f"{hz_field}: {hz_label} ontology", max_results=25)
        web_search_error = search_client.last_error if available
        if unrestricted_hits and complete framework metadata is available:
            ontostore.configure_framework(...)
            set target ontology lookup fields
            return matched strategy result, including web_search_error when present
        return not_harmonized strategy result, including web_search_error when present

    class GeminiGroundedSearchClient:
        if request_budget is exhausted:
            set last_error and return []
        response = llm.generate_response_with_metadata(
            prompt_for_ontology_evidence(query),
            tools=[{"type": "google_search"}],
        )
        last_response = response
        return citation annotations as web_hits

    def _candidate_ontology_ids(target, ontostore):
        configured_ids = target.get("ontology_frameworks", target.get("ontology_ids"))
        if configured_ids is not None:
            return self._normalize_ontology_ids(configured_ids)
        return [
            ontology_id
            for ontology_id, framework in ontostore.ontology_frameworks.items()
            if framework is path-backed and has an existing local owl_path or json_path
        ]

    def _harmonize_target(target, ontostore):
        target["hz_field"] = ontostore.harmonize_key(target hz_field or pre_hz_field)
        target["hz_label"] = ontostore.harmonize_key(target hz_label or pre_hz_label)
        normalize each occurrence hz_field and hz_label the same way

    def _mark_ontology_miss(target):
        remove stale ontology_id and ontology_lookup
        target["ontology_match"] = False
        return False

    def harmonize_miniml_json(
        publication_context=None,
        miniml_json=None,
        ontostore=None,
        target_paths=None,
        strategy="websearch",
    ):
        should_dedupe_targets = target_paths is None
        effective_target_paths = target_paths
        if effective_target_paths is None:
            effective_target_paths = (
                self.target_extractor.build_miniml_sample_target_paths(miniml_json)
            )
        harmonization_targets = self.target_extractor.extract(
            miniml_json,
            start_paths=effective_target_paths,
        )
        if should_dedupe_targets:
            harmonization_targets = (
                self.target_extractor.dedupe_targets(harmonization_targets)
            )
        result = self.harmonize(
            publication_context=publication_context,
            harmonization_targets=harmonization_targets,
            target=None,
            strategy=strategy,
            ontostore=ontostore,
            target_paths=effective_target_paths,
        )
        result["miniml_json"] = self.apply_targets(
            miniml_json,
            result["harmonization_targets"],
        )
        return result

    def apply_targets(miniml_json, harmonization_targets):
        for target in harmonization_targets:
            for occurrence in target["occurrences"] or [target]:
                alternative = {
                    "hz_field": target["hz_field"],
                    "hz_label": target["hz_label"],
                    "target_id": target["id"],
                }
                parent = resolve_json_pointer(miniml_json, occurrence["parent_path"])
                if parent is not dict:
                    continue
                if occurrence field path equals label path:
                    key = unescaped final field path segment + "_hz_alternatives"
                    append alternative to parent[key] unless already present
                else:
                    append alternative to parent["hz_alternatives"] unless duplicate
                    set parent["hz_field"] and parent["hz_label"] if absent
        return miniml_json
```

`lookup_label()` calls `OntoStore.lookup(...)`, which calls
`OntoStore.get(...)`. For unconstrained targets it only considers path-backed
local frameworks, so no external API call is made. If a target explicitly
selects a URL-backed framework whose configured JSON/OWL files are missing,
lookup may reach `requests.get(...)` through `OntoStore.download(...)`.
When `lookup_label()` returns `False`, `harmonize(...)` marks the target
unmatched. With `llm=True`, it calls `assign_onto_framework()` with the packaged
`assign_onto_framework.md` prompt and returns the parsed assignment JSON.
`harmonize()` then runs `harmonize_field()` regardless of first lookup outcome.
When the first lookup missed, strategy handling may update the label and
`_lookup_harmonized_label()` tries to enrich the strategy-harmonized label from
`OntoStore`, preferring the current `target["ontology_id"]` and falling back to
configured candidate ontology IDs only when earlier IDs do not produce hits.

```python
def _extract_harmonization_targets(metadata, start_paths=None):
    return self.target_extractor.extract(metadata, start_paths=start_paths)
```

### `HarmonizationTargetExtractor`

Role: extract normalized metadata edit targets from dictionaries and lists.
Location: `ontology_harmonizer/harmonization_target_extractor.py`.

```python
class HarmonizationTargetExtractor:
    DEFAULT_TARGET_PATHS = [
        {"path": "/organism", "mode": "container_value"},
        {"path": "/characteristics", "mode": "tag_value"},
    ]

    def build_miniml_sample_target_paths(miniml_json):
        ...

    def extract(metadata, start_paths=None):
        ...

    def dedupe_targets(targets):
        ...
```

Target extraction flow:

```python
def extract(metadata, start_paths=None):
    targets = []
    if metadata is not dict or list:
        return targets

    if start_paths is None:
        self._collect_targets(value=metadata, path="", targets=targets)
        return targets

    for start_path_spec in start_paths:
        start_path, mode = self._path_spec(start_path_spec)
        if start_path is None:
            continue

        resolved = self._resolve_json_pointer(metadata, start_path)
        if resolved is dict or list:
            self._collect_targets_by_mode(
                value=resolved,
                path=start_path,
                mode=mode,
                targets=targets,
            )
        elif mode == "field_value" and resolved is scalar:
            create one target for the direct field value
    return targets
```

`build_miniml_sample_target_paths(...)` walks a MINiML package dict, or each
package in a top-level list, and returns path specs for every sample channel's
`source`, `molecule`, `organism`, and `characteristics`. It intentionally skips
channel `position` and long protocol fields.

`dedupe_targets(...)` preserves first-seen target order, removes top-level path
fields, adds `occurrences` with every matched path/value location, and reassigns
stable sequential ids. The dedupe identity is the exact
`pre_hz_field:pre_hz_label` pair.

Internal target extraction dispatch:

- `_path_spec(...)` validates a string path or dict path spec.
- `_resolve_json_pointer(...)` locates the configured subtree.
- `_collect_targets_by_mode(...)` dispatches to one of three subtree collectors;
  direct scalar fields use the `field_value` mode.

```python
def _collect_targets_by_mode(value, path, mode, targets):
    if mode == "scalar":
        self._collect_targets(value=value, path=path, targets=targets)
    elif mode == "tag_value":
        self._collect_tag_value_targets(value=value, path=path, targets=targets)
    elif mode == "container_value":
        self._collect_container_value_targets(
            value=value,
            path=path,
            field_path=path,
            field=self._field_from_path(path),
            targets=targets,
        )
```

Path specs support these modes:

- `scalar`: recursively collect scalar dictionary values under a subtree.
- `field_value`: collect a direct scalar field value.
- `tag_value`: collect `{tag, value}` entries where the tag is `pre_hz_field`.
- `container_value`: collect nested `{value}` entries using the selected
  container name as `pre_hz_field`.

Collector behavior:

- `_collect_targets(...)`: recursively walks dictionaries and lists; each scalar
  dictionary value becomes a target.
- `_collect_tag_value_targets(...)`: recognizes objects with scalar `tag` and
  `value`; emits one target whose `pre_hz_field` is the tag and `pre_hz_label`
  is the value.
- `_collect_container_value_targets(...)`: recognizes nested objects with scalar
  `value`; emits one target using the selected container path as the
  `pre_hz_field_path`.
- `_target(...)` constructs the normalized target dictionary.
- `_join_json_pointer(...)`, `_escape_json_pointer_segment(...)`,
  `_unescape_json_pointer_segment(...)`, and `_field_from_path(...)` maintain
  JSON Pointer coordinates.

### `OntoStore`

Role: ontology framework configuration store and download helper.

```python
class OntoStore:
    DEFAULT_ONTOLOGY_FRAMEWORKS = {...}
    DEFAULT_STORAGE_DIR = package_dir / "ontology_frameworks"

    def __init__(ontology_frameworks=None, storage_dir=None):
        self.storage_dir = DEFAULT_STORAGE_DIR if storage_dir is None else Path(storage_dir)
        self.ontology_frameworks = self._normalize_frameworks(
            DEFAULT_ONTOLOGY_FRAMEWORKS plus ontology_frameworks
        )

    def add_url(name, url, owl_path=None, json_path=None, version=None,
                title=None, description=None):
        self.configure_framework(
            name,
            url=url,
            owl_path=owl_path,
            json_path=json_path,
            version=version,
            title=title,
            description=description,
        )

    def add_urls(ontology_frameworks):
        self.ontology_frameworks.update(self._normalize_frameworks(ontology_frameworks))

    def configure_framework(
        name,
        *,
        url=None,
        path=None,
        owl_path=None,
        json_path=None,
        version=None,
        title=None,
        description=None,
        remove=False,
    ):
        if remove:
            reject any supplied url, path, owl_path, json_path, or metadata
            del self.ontology_frameworks[name]
            return

        normalize supplied url/path/owl_path/json_path and metadata
        self.ontology_frameworks[name] = normalized framework
```

```python
def get(name, force=False):
    owl_path = self._target_path(name)
    json_path = self._json_target_path(name)
    if json_path.exists() and not force:
        return self._ensure_json_ontology_id(json_path, name)

    if force and self._is_url_framework(name):
        self._download_to_path(name, owl_path)
    elif not owl_path.exists():
        owl_path = self.download(name)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    return Owl2json(owl_path).write_json(json_path, ontology_id=name)

def lookup(label, ontology_id):
    json_path = self.get(ontology_id)
    ontology = json.loads(json_path.read_text(encoding="utf-8"))
    terms = ontology.get("terms", {})
    lookup_label = self.harmonize_key(label)
    hits = []
    for index_name in ("label", "id", "accession", "iri"):
        index = terms.get(index_name, {})
        if index is dict and lookup_label in index:
            hits.extend(matched metadata values)
    return deduped hits with ontology_id added to each term dict

def harmonize_key(value):
    return lowercase, trimmed string with edge punctuation stripped and spaces collapsed to "_"

def download(name):
    target = self._target_path(name)
    if self._is_path_framework(name):
        if target does not exist:
            raise FileNotFoundError
        return target

    if target.exists():
        return target

    return self._download_to_path(name, target)

def _download_to_path(name, target):
    self.storage_dir.mkdir(parents=True, exist_ok=True)
    url = self._framework_url(name)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target

def _target_path(name):
    return ontology_frameworks[name]["owl_path"]

def _json_target_path(name):
    return ontology_frameworks[name]["json_path"]
```

Internal calls from `get()`:

- `_target_path(name)`: reads the configured `owl_path`.
- `_json_target_path(name)`: reads the configured `json_path`.
- `download(name)`: downloads a missing URL-backed `.owl` to `owl_path`, or
  validates a path-backed framework.
- `_download_to_path(name, owl_path)`: redownloads and overwrites the `.owl`
  when `force=True` for URL-backed frameworks.
- `_ensure_json_ontology_id(json_path, name)`: repairs cached JSON metadata.
- `Owl2json(owl_path).write_json(json_path, ontology_id=name)`: parses the
  `.owl` into JSON with `ontology["id"]`.

Internal calls from `download()`:

- `_target_path(name)`: reads the configured `owl_path`.
- `_download_to_path(name, target)`: writes response bytes to `owl_path`.
- `_framework_url(name)`: retrieves and validates `ontology_frameworks[name]["url"]`.
- `_filename_from_url(name=name, url=url)`: derives a non-empty basename from
  the URL path.

External API call:

- `requests.get(url, timeout=30)`

### `Owl2json`

Role: RDF/XML OWL to normalized term JSON converter.

```python
class Owl2json:
    def __init__(owl_path):
        self.owl_path = Path(owl_path)

    def parse(ontology_id=None):
        self._validate_rdf_xml_candidate()
        graph = self._parse_graph()
        return {
            "ontology": self._extract_ontology_metadata(graph) plus {"id": ontology_id},
            "terms": self._extract_terms(graph),
        }

    def write_json(output_path, ontology_id=None):
        output_path.write_text(
            json.dumps(self.parse(ontology_id=ontology_id), indent=2) + "\n"
        )
        return output_path
```

Internal behavior:

- `_validate_rdf_xml_candidate()`: reads the first bytes and rejects HTML
  content before invoking RDFLib.
- `_parse_graph()`: calls `rdflib.Graph().parse(path, format="xml")` and wraps
  parser exceptions in `Owl2jsonParseError`.
- `_extract_ontology_metadata(graph)`: reads the `owl:Ontology` subject and
  common title, description, version, version IRI, and license predicates.
- `_extract_terms(graph)`: sorts URI-backed `owl:Class` subjects, normalizes
  each term, and returns harmonized-key `accession`, `id`, `iri`, and `label`
  lookup dictionaries.
- `_unmapped_literal_properties(...)`: preserves ontology-specific literal
  annotations that are not part of the normalized fields.

### `LLM`

Role: platform routing facade for curator generation calls.

```python
class LLM:
    DEFAULT_PLATFORM = "gemini_enterprise"

    def __init__(platform=DEFAULT_PLATFORM, **platform_options):
        self.platform_name = platform
        self.platform_options = dict(platform_options)
        self._routed_platforms = {}
        self.platform = self._create_platform(platform, **platform_options)

    def generate_response(prompt, model=None, config=None, tools=None, **extra_options):
        response = self.generate_response_with_metadata(
            prompt,
            model=model,
            config=config,
            tools=tools,
            **extra_options,
        )
        return response["text"]

    def generate_response_with_metadata(
        prompt,
        model=None,
        config=None,
        tools=None,
        **extra_options,
    ):
        platform = self._platform_for_model(model)
        return platform.generate_response_with_metadata(
            prompt,
            model=model,
            config=config,
            tools=tools,
            **extra_options,
        )
```

```python
def _platform_for_model(model):
    if model starts with "claude-" and self.platform_name is not "claude_vertex":
        if "claude_vertex" not in self._routed_platforms:
            self._routed_platforms["claude_vertex"] = self._create_platform(
                "claude_vertex",
                **self._claude_platform_options(),
            )
        return self._routed_platforms["claude_vertex"]
    return self.platform

def _claude_platform_options():
    options = copy(self.platform_options)
    remove "client", "enterprise", and "model"
    return options

def _create_platform(platform, **platform_options):
    if normalized platform == "gemini_enterprise":
        return GeminiEnterprisePlatform(**platform_options)
    if normalized platform == "claude_vertex":
        return ClaudeVertexPlatform(**platform_options)
    raise ValueError
```

### `GeminiEnterprisePlatform`

Role: Google Gen AI / Vertex AI Gemini adapter.

```python
class GeminiEnterprisePlatform:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(project=None, location=None, model=None, config=None,
                 tools=None, enterprise=None, client=None, **client_options):
        self.project = project
        self.location = location
        self.model = model or DEFAULT_MODEL
        self.config_template = self._merged_config(config)
        self.tools_template = [] if tools is None else list(tools)
        self.enterprise = enterprise
        self.client = client
        self.client_options = client_options

    def generate_response_with_metadata(
        prompt,
        model=None,
        config=None,
        tools=None,
        **extra_options,
    ):
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

        raw_response = self._client().models.generate_content(**request)
        return {
            "text": self._model_adapter(effective_model).parse_response(raw_response),
            "raw_response": raw_response,
            "citations": self._citations(raw_response),
            "tool_calls": self._tool_calls(raw_response),
            "provider": "gemini_enterprise",
        }

    def generate_response(...):
        return self.generate_response_with_metadata(...)["text"]
```

Internal calls from `generate_response_with_metadata()`:

- `_generation_config(...)`
- `_clean_options(...)`
- `_client()`
- `_model_adapter(...)`
- `parse_response(...)` on `GeminiModelAdapter` or `ClaudeModelAdapter`
- `_citations(...)`
- `_tool_calls(...)`

External API call:

- `google.genai.Client(...).models.generate_content(**request)`

```python
def _client():
    if self.client is None:
        self.client = self._create_client(...)
    return self.client

def _create_client(project, location, enterprise, client_options):
    from google import genai
    mode_options = {"enterprise": True} if enterprise else {"vertexai": True}
    return genai.Client(**non_null_options)
```

### `ClaudeVertexPlatform`

Role: Anthropic Claude-on-Vertex adapter.

```python
class ClaudeVertexPlatform:
    DEFAULT_MODEL = "claude-opus-4-8"

    def __init__(project=None, location=None, model=None, config=None,
                 tools=None, client=None, **client_options):
        self.project = project
        self.location = location or "global"
        self.model = model or DEFAULT_MODEL
        self.config_template = self._merged_config(config)
        self.tools_template = [] if tools is None else list(tools)
        self.client = client
        self.client_options = client_options

    def generate_response_with_metadata(
        prompt,
        model=None,
        config=None,
        tools=None,
        **extra_options,
    ):
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
        return {
            "text": ClaudeModelAdapter().parse_response(raw_response),
            "raw_response": raw_response,
            "citations": [],
            "tool_calls": [],
            "provider": "claude_vertex",
        }

    def generate_response(...):
        return self.generate_response_with_metadata(...)["text"]
```

Internal calls from `generate_response_with_metadata()`:

- `_claude_config(...)`
- `_client()`
- `ClaudeModelAdapter().parse_response(...)`

External API call:

- `anthropic.AnthropicVertex(...).messages.create(**request)`

```python
def _claude_config(config=None):
    generation_config = self._clean_options(self._generation_config(config))
    claude_config = {}
    if "max_output_tokens" in generation_config:
        claude_config["max_tokens"] = generation_config["max_output_tokens"]
    if "max_tokens" in generation_config:
        claude_config["max_tokens"] = generation_config["max_tokens"]
    if "temperature" in generation_config:
        claude_config["temperature"] = generation_config["temperature"]
    if generation_config has response_schema:
        claude_config["output_config"] = {
            "format": {
                "type": "json_schema",
                "schema": self._normalize_schema(response_schema),
            }
        }
    return claude_config
```

### Response Adapters

Role: normalize provider-specific response shapes to a raw string.

```python
class BaseModelAdapter:
    def parse_response(response):
        if response.text exists:
            return str(response.text)
        if response.response exists:
            return str(response.response)
        if response.candidates[0].content.parts[0].text exists:
            return str(that_text)
        return str(response)

class GeminiModelAdapter(BaseModelAdapter):
    def parse_response(response):
        if candidate part text exists:
            return candidate part text
        return super().parse_response(response)

class ClaudeModelAdapter(BaseModelAdapter):
    def parse_response(response):
        if response.content contains text blocks:
            return concatenated block text
        return super().parse_response(response)
```

### CLI Entry Point

Role: parse command-line input, call the thematic reviewer, and write JSON.

```python
def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    result = ThematicReviewer().review_relevancy(
        publication_text=_input_value(args.publication_text, args.publication_text_file),
        theme=_input_value(args.theme, args.theme_file),
        metadata=_input_value(args.metadata, args.metadata_file),
        title=_input_value(args.title, args.title_file),
    )

    if args.out is not None:
        open(args.out, "w").json_dump(result, indent=2)
    else:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0
```

Internal calls:

- `_build_parser()`
- `_input_value(value, file)` for each input
- `ThematicReviewer.review_relevancy(...)`

File-system calls:

- `Path(file).read_text(encoding="utf-8")` for input file options.
- `open(args.out, "w", encoding="utf-8")` when writing to an output file.

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

The ontology harmonizer prompt files are:

- `assign_onto_framework.md` instructs the model to choose a configured
  ontology framework ID, `"false"`, or `"unsure"` and return `decision`,
  `confidence`, and `reason`.
- `assign_field.md` instructs the model to choose or create a normalized field
  key and return `decision`, `confidence`, `reason`, and `new_field`.
- `judge_lookup.md` instructs the model to choose the best lookup hit ID and
  return `decision`, `confidence`, and `reason`.

<a id="llm-wrapper"></a>
## LLM Wrapper

`agentic_curator.wrappers.LLM` is the provider routing facade.

```python
from agentic_curator.wrappers import LLM

llm = LLM()
text = llm.generate_response("prompt")
metadata = llm.generate_response_with_metadata(
    "prompt",
    tools=[{"type": "google_search"}],
)
```

Defaults:

- default platform: `gemini_enterprise`
- default Gemini model: `gemini-2.5-flash`
- default Claude model: `claude-opus-4-8`

`LLM(platform="gemini_enterprise", **platform_options)` creates a Gemini
platform by default. `LLM(platform="claude_vertex", **platform_options)` creates
a Claude Vertex platform. Unknown platform names raise `ValueError`.
`generate_response(...)` remains the text-only compatibility API.
`generate_response_with_metadata(...)` returns a provider-normalized dictionary
with `text`, `raw_response`, `citations`, `tool_calls`, and `provider`.

If a call-level `model` starts with `claude-` and the default platform is not
already `claude_vertex`, `LLM` lazily routes that call to a Claude Vertex
platform. The Claude-routed platform drops Gemini-only options such as
`enterprise`, `client`, and a default model when deriving platform options, but
keeps shared options such as `project` and `location`.

LLM troubleshooting note: the local `.env` can have all dependencies installed
and Google ADC present while sandboxed calls still fail. In this environment,
`google.auth.default(...)` found ADC for project `prj-int-dev-saez-ai-thema`,
but sandboxed token refresh failed resolving `oauth2.googleapis.com`. The same
refresh succeeded with network access. This indicates a restricted network/DNS
failure during OAuth token refresh, not missing dependencies or absent ADC.

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
parsing. `generate_response_with_metadata(...)` wraps the same text with the raw
response, citation annotations from candidate content parts, response `steps`
such as `google_search_call` and `google_search_result`, and provider
`gemini_enterprise`.

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

The installed console commands are `cli_thematic_reviewer` and
`cli_ontology_harmonizer`. The modules can also be run directly:

```bash
.env/bin/python -m agentic_curator.cli.cli_thematic_reviewer --help
.env/bin/python -m agentic_curator.cli.cli_ontology_harmonizer --help
```

Both commands accept `--verbosity {quiet,error,warning,info,debug}`. Logs are
written to stderr and JSON results stay on stdout unless `--out` is supplied.

`cli_thematic_reviewer` exposes `ThematicReviewer` methods:

- no subcommand or `review`: `review_relevancy(...)`
- `extract-evidence`: `extract_evidence(...)`
- `judge-evidence`: `judge_evidence(...)`

Thematic reviewer inputs may be provided directly or from UTF-8 files:

- `--publication-text` or `--publication-text-file`
- `--theme` or `--theme-file`
- `--metadata` or `--metadata-file`
- `--title` or `--title-file`
- `--evidences` or `--evidences-file` for `judge-evidence`

For each input, the file option takes precedence over the direct value.
Metadata files are read as UTF-8 text and passed through as strings; they are
not parsed as JSON by the thematic review and extraction commands. Evidence
inputs for `judge-evidence` are parsed as JSON.

`cli_ontology_harmonizer` exposes `OntologyHarmonizer` methods:

- `harmonize`: `harmonize(...)`
- `harmonize-miniml-json`: `harmonize_miniml_json(...)`

Ontology inputs include:

- `--publication-context` or `--publication-context-file`
- `--target` or `--target-file`
- `--harmonization-targets` or `--harmonization-targets-file`
- `--miniml-json` or `--miniml-json-file`
- `--target-paths` or `--target-paths-file`
- `--strategy websearch|rag`
- `--lookup-llm-judge`
- `--lookup-llm-threshold`
- `--llm` or `--no-llm`
- `--ontology-frameworks` or `--ontology-frameworks-file`
- `--fields` or `--fields-file`
- `--storage-dir`

By default the CLI writes pretty JSON to stdout. When `--out` is provided, it
writes pretty JSON to that file and keeps stdout quiet.

<a id="tests"></a>
## Tests

The test suite is pytest-based and avoids live provider calls by using fake
clients and fake LLM objects.

Test coverage includes:

- reviewer instantiation, public exports, missing legacy module, prompt
  construction, schema construction, and two-call ordering
- ontology harmonizer imports, root exports, target wrapper behavior,
  `lookup_label()` lookup mutation, fallback assignment, MINiML target
  application, Gemini grounded search client citation/error handling,
  websearch strategy fallback behavior, and `OntoStore`
  defaults/overrides/download/get/lookup behavior
- Owl2json imports, ontology metadata extraction, normalized term JSON,
  accession fallback, deprecated/replaced terms, HTML rejection, and JSON file
  writing
- thematic and ontology CLI direct inputs, UTF-8 file inputs, JSON inputs,
  subcommand routing, verbosity logging, file precedence, stdout output, and
  `--out` writing
- workflow logging for `ThematicReviewer`, `OntologyHarmonizer`, and `OntoStore`
- repository metadata policy checks for authors headers and skipped prompt
  Markdown / license files
- provider facade selection, metadata responses, Claude model routing, request
  construction, config merging, schema normalization, tool overrides, and lazy
  import errors
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

Install from `requirements.txt`:

```bash
.env/bin/python -m pip install -r requirements.txt
```

Run tests:

```bash
.env/bin/python -m pytest
```

Run CLI help:

```bash
.env/bin/python -m agentic_curator.cli.cli_thematic_reviewer --help
.env/bin/python -m agentic_curator.cli.cli_ontology_harmonizer --help
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

Run ontology harmonization against a JSON target:

```bash
.env/bin/python -m agentic_curator.cli.cli_ontology_harmonizer harmonize \
  --publication-context-file .dev/thematic_reviewer_publication_text.txt \
  --target '{"id": "target-1", "pre_hz_field": "organism", "pre_hz_label": "mouse"}' \
  --fields '{"organism": {"label": "organism"}}' \
  --no-llm
```
