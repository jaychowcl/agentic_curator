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
      ontology_store.py
      owl2json.py
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
  test_owl2json.py
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
- runtime dependencies: `anthropic[vertex]>=0.107,<1`, `google-genai>=1.72,<2`, `rdflib>=7,<8`, and `requests>=2,<3`
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

`agentic_curator.curators.ontology_harmonizer.OntologyHarmonizer` is the
metadata harmonization curator. It has no LLM, prompt, provider, or CLI
integration yet.

Public methods:

- `harmonize_miniml_json(publication_context=None, miniml_json=None, ontostore=None, target_paths=None) -> dict`
- `harmonize(publication_context=None, harmonization_targets=None, ontostore=None, target_paths=None) -> dict`

`harmonize_miniml_json(...)` extracts targets from MINiML-style JSON with
`HarmonizationTargetExtractor`, then calls `harmonize(...)`. When `target_paths`
is omitted, it builds paths for every `sample[*].channel[*]`, extracts
meaningful sample metadata (`source`, `molecule`, `organism`, and
`characteristics`), and dedupes targets by exact
`pre_hz_field:pre_hz_label` while preserving every source path in
`occurrences`. Supplying `target_paths` keeps explicit path extraction behavior.

The lower-level `harmonize(...)` currently returns only a target wrapper:

```python
{
    "publication_context": publication_context,
    "harmonization_targets": harmonization_targets or [],
    "target_paths": target_paths,
}
```

`publication_context` may be a string or `None`, `miniml_json` may be a
dictionary, list, or `None`, `harmonization_targets` may be a list of extracted
target dictionaries or `None`, and a per-call `ontostore` override must be an
`OntoStore`.

`OntologyHarmonizer(ontology_frameworks=None)` creates a default `OntoStore`
when no framework object is supplied. A per-call `ontostore` can override the
constructor value for future harmonization behavior. The effective store is
validated but not used for matching yet.

`OntoStore`, `Owl2json`, and `Owl2jsonParseError` are exported from
`agentic_curator.curators.ontology_harmonizer`. `OntoStore` stores ontology
framework URL config, downloads named frameworks, and is reserved for future
parsing and serving methods. `Owl2json` parses RDF/XML `.owl` files into a
term-centric JSON dictionary.

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
stable current URLs. `OntoStore.add_url(name, url, version=None)` adds or replaces
one framework URL with optional version metadata, and
`OntoStore.add_urls(ontology_frameworks)` merges a framework dictionary into
the store, including any nested `version` fields. `OntoStore.get(name,
force=False)` is the ontology-serving entrypoint. It returns a parsed JSON
`Path` under `storage_dir / "jsons"`, reusing existing JSON unless
`force=True`. When the JSON is missing, it parses an existing local `.owl` or
downloads the `.owl` first. With `force=True`, it redownloads the `.owl` and
overwrites the JSON.
`OntoStore.download(name)` looks up
`self.ontology_frameworks[name]["url"]`, downloads only that named framework
with `requests.get(url, timeout=30)`, calls `raise_for_status()`, and returns
the saved `Path`. Successful downloads and existing-file hits are recorded in
`self.downloaded_paths` as an in-memory `{ontology_id: Path}` mapping.

Downloaded files are saved under
`src/agentic_curator/curators/ontology_harmonizer/ontology_frameworks/` using
the URL basename. Parsed JSON files are saved under the sibling `jsons/`
directory within `storage_dir`. The default storage directory is ignored by
git. Existing downloaded files are skipped by `download()` and existing JSON is
skipped by `get()` unless `force=True`. Unknown framework names raise
`KeyError`; missing or invalid URLs raise `ValueError`.

`Owl2json(owl_path)` accepts a local `.owl` path and uses RDFLib to parse it as
RDF/XML. `parse()` returns:

```python
{
    "ontology": {
        "iri": "...",
        "version_iri": "...",
        "title": "...",
        "description": "...",
        "version": "...",
        "license": "...",
    },
    "terms": {
        "accession": {
            "CHEBI:100": {
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
        "iri": {"http://purl.obolibrary.org/obo/CHEBI_100": "..."},
        "label": {"term label": ["..."]},
    },
}
```

Top-level terms are URI-backed `owl:Class` subjects; blank-node class
expressions are ignored as entries. Labels come from `rdfs:label`, descriptions
from `obo:IAO_0000115`, accessions from `oboInOwl:id` with an OBO IRI fallback,
parents from URI-valued `rdfs:subClassOf`, synonyms and xrefs from common
`oboInOwl` predicates, deprecation from `owl:deprecated`, and replacements from
`obo:IAO_0100001`. The `terms` object indexes the same normalized term records
by accession, IRI, and label. Label values are lists because labels are not
guaranteed unique. Terms without accessions or labels are omitted from those
specific indexes but remain available by IRI. Unmapped literal annotations are
preserved in `properties` by predicate IRI. `write_json(output_path)` writes
deterministic pretty JSON and returns the output path. HTML-like files, such as
a bad `.owl` download that starts with `<!DOCTYPE html>` or `<html`, and RDFLib
parse failures raise `Owl2jsonParseError`.

`HarmonizationTargetExtractor` performs target extraction for future metadata
edit planning. `OntologyHarmonizer` owns `self.target_extractor` and keeps
`_extract_harmonization_targets(...)` as a private compatibility wrapper around
`self.target_extractor.extract(...)`. Targets are not returned by `harmonize()`.
The extractor still supports root-level default path specs:

```python
[
    {"path": "/organism", "mode": "container_value"},
    {"path": "/characteristics", "mode": "tag_value"},
]
```

`HarmonizationTargetExtractor.extract(metadata, start_paths=...)` traverses
dictionaries and lists, skips raw string metadata, skips `None`, and does not
create targets for scalar list items without an object key. Each target
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

`pre_hz_field_path`, `pre_hz_label_path`, and `parent_path` use JSON
Pointer-style paths with escaped path segments (`~` becomes `~0`, `/` becomes
`~1`). These coordinates are intended to let future harmonization results edit
both field names and label values back into structured metadata. `hz_field` and
`hz_label` are initialized from the extracted values until actual ontology
harmonization is implemented.

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
target wrapper directly and does not call `LLM`, provider adapters, or prompt
files.

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
    return self._llm().generate_response(
        prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": self._evidence_response_schema(),
        },
    )
```

Internal calls from `extract_evidence()`:

- `_evidence_prompt(...)`
- `_llm()`
- `_evidence_response_schema()`

```python
def judge_evidence(evidences, theme=None, title=None):
    prompt = self._judge_evidence_prompt(
        evidences=evidences,
        theme=theme,
        title=title,
    )
    return self._llm().generate_response(
        prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": self._judge_evidence_response_schema(),
        },
    )
```

Internal calls from `judge_evidence()`:

- `_judge_evidence_prompt(...)`
- `_llm()`
- `_judge_evidence_response_schema()`

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

Role: metadata harmonization curator scaffold. The public method currently
preserves metadata unchanged. It delegates structured edit target discovery to
`HarmonizationTargetExtractor` for future harmonization.

```python
class OntologyHarmonizer:
    DEFAULT_TARGET_PATHS = HarmonizationTargetExtractor.DEFAULT_TARGET_PATHS

    def __init__(ontology_frameworks=None):
        if ontology_frameworks is None:
            self.ontology_frameworks = OntoStore()
        else:
            self.ontology_frameworks = ontology_frameworks
        self.target_extractor = HarmonizationTargetExtractor()

    def harmonize(
        publication_context=None,
        harmonization_targets=None,
        ontostore=None,
        target_paths=None,
    ):
        effective_ontostore = self._effective_ontostore(ontostore)
        # effective_ontostore is validated but not used yet.
        return {
            "publication_context": publication_context,
            "harmonization_targets": harmonization_targets or [],
            "target_paths": target_paths,
        }

    def harmonize_miniml_json(
        publication_context=None,
        miniml_json=None,
        ontostore=None,
        target_paths=None,
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
        return self.harmonize(
            publication_context=publication_context,
            harmonization_targets=harmonization_targets,
            ontostore=ontostore,
            target_paths=effective_target_paths,
        )
```

No external API calls are made by `harmonize()` in the current implementation.

```python
def _extract_harmonization_targets(metadata, start_paths=None):
    return self.target_extractor.extract(metadata, start_paths=start_paths)
```

### `HarmonizationTargetExtractor`

Role: extract normalized metadata edit targets from dictionaries and lists.

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

`dedupe_targets(...)` preserves first-seen target order, keeps the first target's
singular path fields for compatibility, adds `occurrences` with every matched
path/value location, and reassigns stable sequential ids. The dedupe identity is
the exact `pre_hz_field:pre_hz_label` pair.

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
        self.ontology_frameworks = copy(DEFAULT_ONTOLOGY_FRAMEWORKS)
        if ontology_frameworks:
            self.ontology_frameworks.update(ontology_frameworks)
        self.storage_dir = DEFAULT_STORAGE_DIR if storage_dir is None else Path(storage_dir)
        self.downloaded_paths = {}

    def add_url(name, url, version=None):
        framework = {"url": url}
        if version is not None:
            framework["version"] = version
        self.ontology_frameworks[name] = framework

    def add_urls(ontology_frameworks):
        self.ontology_frameworks.update(ontology_frameworks)
```

```python
def get(name, force=False):
    owl_path = self._target_path(name)
    json_path = self._json_target_path(owl_path)
    if json_path.exists() and not force:
        return json_path

    if force:
        self._download_to_path(name, owl_path)
    elif owl_path.exists():
        self.downloaded_paths[name] = owl_path
    else:
        owl_path = self.download(name)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    return Owl2json(owl_path).write_json(json_path)

def download(name):
    target = self._target_path(name)
    if target.exists():
        self.downloaded_paths[name] = target
        return target

    return self._download_to_path(name, target)

def _download_to_path(name, target):
    self.storage_dir.mkdir(parents=True, exist_ok=True)
    url = self._framework_url(name)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    target.write_bytes(response.content)
    self.downloaded_paths[name] = target
    return target

def _target_path(name):
    url = self._framework_url(name)
    return self.storage_dir / self._filename_from_url(name=name, url=url)

def _json_target_path(owl_path):
    return self.storage_dir / "jsons" / f"{owl_path.stem}.json"
```

Internal calls from `get()`:

- `_target_path(name)`: computes the local path for the configured ontology.
- `_json_target_path(owl_path)`: computes the parsed JSON path.
- `download(name)`: downloads and records `downloaded_paths[name]` when the
  `.owl` file is missing.
- `_download_to_path(name, owl_path)`: redownloads and overwrites the `.owl`
  when `force=True`.
- `Owl2json(owl_path).write_json(json_path)`: parses the `.owl` into JSON.

Internal calls from `download()`:

- `_target_path(name)`: computes the local path for the configured ontology.
- `_download_to_path(name, target)`: writes the response bytes and records
  `downloaded_paths[name]`.
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

    def parse():
        self._validate_rdf_xml_candidate()
        graph = self._parse_graph()
        return {
            "ontology": self._extract_ontology_metadata(graph),
            "terms": self._extract_terms(graph),
        }

    def write_json(output_path):
        output_path.write_text(json.dumps(self.parse(), indent=2) + "\n")
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
  each term, and returns `accession`, `iri`, and `label` lookup dictionaries.
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
        platform = self._platform_for_model(model)
        return platform.generate_response(
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

    def generate_response(prompt, model=None, config=None, tools=None, **extra_options):
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
        return self._model_adapter(effective_model).parse_response(raw_response)
```

Internal calls from `generate_response()`:

- `_generation_config(...)`
- `_clean_options(...)`
- `_client()`
- `_model_adapter(...)`
- `parse_response(...)` on `GeminiModelAdapter` or `ClaudeModelAdapter`

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

    def generate_response(prompt, model=None, config=None, tools=None, **extra_options):
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
```

Internal calls from `generate_response()`:

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
- ontology harmonizer imports, root exports, metadata-only return behavior, and
  `OntoStore` defaults/overrides
- Owl2json imports, ontology metadata extraction, normalized term JSON,
  accession fallback, deprecated/replaced terms, HTML rejection, and JSON file
  writing
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
