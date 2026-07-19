# agentic-curator

LLM-assisted query generation, thematic publication review, and ontology metadata harmonization for life-science curation.

## Description

`agentic-curator` provides three main curator workflows: it generates bounded
Europe PMC queries from a research theme, evaluates publications and accessions
against thematic criteria, and maps metadata fields and values to controlled
ontology terms. It also includes MINiML target extraction and application,
local exact and FTS5 search, Gemini/USearch semantic retrieval, OLS4 fallback,
controlled-field assignment, ontology cache construction, and provider adapters
for Gemini and Claude on Vertex AI.

The principal entrypoints are the public Python API and four installed console
commands. Detailed architecture and internal behavior live in the
[codebase handoff](docs/codebase.md#project-purpose-and-layout).

## Installation

Install the package and console commands from a checkout:

```bash
python -m pip install -e .
```

Install development dependencies as well:

```bash
python -m pip install -e ".[dev]"
```

Alternatively, install the mirrored dependency set from `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

### Requirements

- Python 3.10 or newer.
- Runtime packages declared in `pyproject.toml`: `anthropic[vertex]`,
  `filelock`, `google-genai`, `ijson`, `rdflib`, `requests`, and `usearch`.
- `pytest>=8` for development and test execution.
- Google Cloud Application Default Credentials and an accessible Vertex AI
  project for live Gemini, Claude, or embedding calls.
- Network access for live provider calls, OLS4 searches, and ontology downloads.
- Local disk space for ontology OWL/JSON files, SQLite data, and USearch indexes
  when ontology caching is enabled.

The repository does not currently provide a Dockerfile or Docker Compose
configuration. Docker is therefore not a supported interface.

## Configuration

The package does not automatically load a dotenv file. Authenticate the Google
SDK with Application Default Credentials, then pass project/location explicitly
when required by your environment:

```bash
gcloud auth application-default login
```

```python
from agentic_curator.wrappers import LLM

llm = LLM(
    platform="gemini_enterprise",
    project="my-gcp-project",
    location="global",
)
```

The default LLM platform is `gemini_enterprise` with model
`gemini-2.5-flash`. Select `claude_vertex` for Claude; a call-level model name
beginning with `claude-` is also routed to the Claude adapter. Both adapters
accept `project`, `location`, `model`, a default generation `config`, default
`tools`, an injected `client`, and provider client options. See the
[LLM internals](docs/codebase.md#llm-wrapper).

Ontology behavior is configured with these cooperating objects:

```python
from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore, RequestPolicy

policy = RequestPolicy(
    timeout_seconds=30,
    max_attempts=3,
    backoff_base_seconds=1,
    cache_ttl_seconds=604800,
    force_refresh=False,
)
store = OntoStore(
    ontology_frameworks={
        "custom": {
            "url": "https://example.org/custom.owl",
            "title": "Custom ontology",
            "rag_similarity_threshold": 0.6,
        }
    },
    preferred_ontology_ids=["custom"],
    fields={"organism": {"label": "Organism"}},
    storage_dir=".cache/ontologies",
    request_policy=policy,
)
harmonizer = OntologyHarmonizer(
    ontostore=store,
    request_policy=policy,
    rag_similarity_threshold=0.5,
    rag_hierarchy=False,
    rag_parent_depth=2,
    rag_child_depth=1,
    rag_hierarchy_threshold_offset=0.1,
)
```

- `ontology_frameworks` extends or replaces built-in framework definitions by
  ID; framework data may come from a URL, OWL path, or JSON path.
- `preferred_ontology_ids` is an ordered, advisory judge preference. It does
  not restrict retrieval and must refer to configured frameworks.
- `fields` seeds the persistent controlled-field registry.
- `storage_dir` contains ontology sources, SQLite, response cache data, and
  vector indexes.
- `RequestPolicy` controls external timeout, retry attempts, exponential
  backoff, response-cache TTL, and forced refresh.
- `rag_similarity_threshold` is inclusive and may be overridden per framework.
  Hierarchy expansion is off by default and uses cached parents/children only.

Equivalent CLI configuration is available through `--ontology-frameworks`,
`--fields`, `--storage-dir`, request/cache flags, and RAG hierarchy flags in the
[CLI guide](#cli-guide). Full ontology behavior is documented in the
[ontology harmonizer handoff](docs/codebase.md#ontology-harmonizer).

## Quickstart

The major supported interfaces are the Python API and installed CLI commands.

### Python Query Generation

See the [Python API guide](#python-api-guide) and
[query-generator internals](docs/codebase.md#query-generator).

```python
from agentic_curator import QueryGenerator

result = QueryGenerator().generate_queries(
    "Human fibrosis transcriptomics studies with linked datasets.",
    max_queries=3,
)
print(result["queries"])
```

### CLI Query Generation

See the [CLI guide](#cli-guide).

```bash
cli_query_generator --theme-file theme.md --max-queries 3 --out queries.json
```

### Python Thematic Review

See the [Python API guide](#python-api-guide) and
[reviewer workflow](docs/codebase.md#reviewer-workflow).

```python
from agentic_curator import ThematicReviewer

result = ThematicReviewer().review_relevancy(
    publication_text="Full publication text",
    theme="Human fibrosis transcriptomics with accession-linked evidence",
    metadata={"GSE110147": "organism=human; tissue=lung"},
    title="Publication title",
    accessions=["GSE110147"],
)
print(result["judgement"])
```

### CLI Thematic Review

See the [CLI guide](#cli-guide).

```bash
cli_thematic_reviewer review \
  --publication-text-file publication.txt \
  --theme-file theme.md \
  --metadata-file metadata.txt \
  --title "Publication title" \
  --accession GSE110147 \
  --out review.json
```

### Python Ontology Harmonization

See the [Python API guide](#python-api-guide) and
[ontology harmonizer internals](docs/codebase.md#ontology-harmonizer).

```python
from agentic_curator import OntologyHarmonizer

result = OntologyHarmonizer().harmonize(
    publication_context="Human lung study.",
    target={
        "id": "target-1",
        "pre_hz_field": "organism",
        "pre_hz_label": "Homo sapiens",
        "ontology_ids": ["ncbitaxon"],
    },
)
print(result["harmonization_targets"])
```

### CLI Ontology Harmonization

See the [CLI guide](#cli-guide).

```bash
cli_ontology_harmonizer harmonize \
  --publication-context-file publication.txt \
  --target-file target.json \
  --fields-file fields.json \
  --out harmonized.json
```

### Ontology Cache Builder

See the [Ontology cache builder guide](#ontology-cache-builder-guide).

```bash
build_ontology_cache --max-workers 4 --timeout 2700 --rag-index
```

### Inputs & Outputs

| Workflow | Main inputs | Main output |
| --- | --- | --- |
| Query generation | Non-empty theme; maximum of 1–3 queries | `queries`, per-query `details`, and `strategy_summary`; every query includes the ThematicAtlases dataset-link filter |
| Thematic review | Publication text, theme, optional title/metadata, accession list, review strategy | Publication `judgement`, reasoning, confidence, accession assessments, and high-confidence removals |
| Ontology harmonization | One target, a target list, or MINiML JSON; optional publication/metadata context and stage controls | Harmonized fields/labels, selected term identifiers, per-stage traces, controls, and optionally updated MINiML JSON |
| Ontology cache builder | Configured built-in frameworks, concurrency/timeout options, optional semantic-index flag | Cached ontology data, synchronized SQLite index, optional USearch partitions, log, and JSON manifest |
| LLM facade | Prompt plus optional model, generation config, and tools | Text, or metadata containing text, raw response, citations, tool calls, and provider |

Direct CLI values and their `--*-file` equivalents accept UTF-8 text. File
arguments take precedence. Ontology, evidence, framework, field, target-path,
and MINiML inputs documented as JSON are parsed before dispatch. Curator CLI
results are pretty JSON on stdout unless `--out` is supplied; logs use stderr.

## Guide

### Python API Guide

The canonical imports are:

```python
from agentic_curator import OntologyHarmonizer, QueryGenerator, ThematicReviewer
```

All curator classes accept an injected LLM-like object for testing or custom
provider integration and otherwise create the default facade lazily.

#### QueryGenerator

```python
QueryGenerator(llm=None)
generate_queries(theme, max_queries=3) -> dict
```

`theme` must be non-empty and `max_queries` must be an integer from 1 to 3. One
schema-constrained model call returns topical clauses; Python validates unique,
non-empty details and adds `(HAS_DATA:y OR HAS_LABSLINKS:y)`. The class does not
call Europe PMC, count results, or retry generation. See
[query generation](docs/codebase.md#query-generator).

#### ThematicReviewer

```python
ThematicReviewer(llm=None)

review_relevancy(
    publication_text=None,
    theme=None,
    metadata=None,
    title=None,
    accessions=None,
    strategy="direct",
) -> dict

extract_evidence(
    publication_text=None,
    theme=None,
    metadata=None,
    title=None,
    accessions=None,
) -> dict | list

judge_evidence(
    evidences,
    theme=None,
    title=None,
    accessions=None,
) -> dict | list
```

`strategy` is `direct` or the legacy `evidence_then_judgement`. Direct review
uses one model call and deterministically derives publication/accession
decisions from four criterion assessments. The legacy strategy extracts
evidence and judges it in two calls. Unknown or duplicate accessions are
discarded, missing assessments become uncertain, and only medium/high-confidence
failures become removals. See the
[reviewer workflow](docs/codebase.md#reviewer-workflow).

#### OntologyHarmonizer

```python
OntologyHarmonizer(
    ontostore=None,
    llm=None,
    request_policy=None,
    rag_similarity_threshold=0.5,
    rag_hierarchy=False,
    rag_parent_depth=2,
    rag_child_depth=1,
    rag_hierarchy_threshold_offset=0.1,
)
```

Main workflow methods and all stage controls:

```python
harmonize(
    publication_context=None,
    metadata_context=None,
    harmonization_targets=None,
    target=None,
    ontostore=None,
    target_paths=None,
    target_checker=True,
    direct_lookup_judge=True,
    rag_lookup=True,
    rag_lookup_judge=True,
    ols_lookup=True,
    ols_lookup_judge=True,
    field_assignment_judge=True,
) -> dict

harmonize_miniml_json(
    publication_context=None,
    miniml_json=None,
    ontostore=None,
    target_paths=None,
    target_checker=True,
    direct_lookup_judge=True,
    rag_lookup=True,
    rag_lookup_judge=True,
    ols_lookup=True,
    ols_lookup_judge=True,
    field_assignment_judge=True,
) -> dict

apply_targets(miniml_json, harmonization_targets) -> dict | list | None
```

Additional public workflow helpers are `lookup_label(...)`,
`lookup_rag_label(...)`, `judge_lookup(..., candidate_limit=10)`,
`harmonize_label(...)`, `harmonize_field(...)`, and `assign_field(...)`.

The fixed term workflow is target checker → local exact/FTS lookup → cached
semantic lookup → unrestricted OLS4 lookup → label promotion → controlled-field
resolution. `no_match` continues to the next term strategy; `false` terminally
skips the target. Disabling a judge retains ambiguous candidates as trace
evidence rather than applying the first candidate. MINiML mode extracts and
deduplicates meaningful sample/channel values, delegates to the same workflow,
and applies non-skipped results back to the object. See the complete
[ontology harmonizer guide](docs/codebase.md#ontology-harmonizer).

#### OntoStore and ontology utilities

```python
OntoStore(
    ontology_frameworks=None,
    preferred_ontology_ids=None,
    fields=None,
    storage_dir=None,
    sqlite_path=None,
    request_policy=None,
    embedding_provider=None,
)
```

Important public operations include:

- Framework configuration: `configure_framework(...)`, `add_url(...)`,
  `add_urls(...)`, `set_preferred_ontology_ids(...)`, `get(...)`, and
  `download(...)`.
- Lexical/semantic lookup: `lookup(...)`, `lookup_with_metadata(...)`,
  `lookup_exact(...)`, `lookup_rag(...)`, and `lookup_rag_many(...)`.
- Indexing/caching: `index_framework(...)`, `index_owl_framework(...)`,
  `sync_sqlite(...)`, `build_rag_index(...)`, `cache_all(...)`, and
  `remove_indexed_framework(...)`.
- Controlled fields and response cache: field CRUD, review-status operations,
  `get_cached_response(...)`, `set_cached_response(...)`, and
  `clear_cached_responses(...)`.
- Conversion/extraction: `Owl2json.parse()`, `Owl2json.write_json()`,
  `HarmonizationTargetExtractor`, and `build_miniml_metadata_context(...)`.

Exact lookup and FTS5 use SQLite. Semantic lookup only considers frameworks
that already have local OWL/JSON data; it does not trigger downloads. USearch
partitions are persistent and memory-mapped for queries. See
[ontology SQLite and semantic indexing](docs/codebase.md#ontology-harmonizer).

#### RequestPolicy

```python
RequestPolicy(
    timeout_seconds=30,
    max_attempts=3,
    backoff_base_seconds=1,
    cache_ttl_seconds=604800,
    force_refresh=False,
)
```

Transient timeouts, connection failures, HTTP 429, and server errors are
retried with jittered exponential backoff. Exhausted or non-transient errors
propagate with a request trace.

#### Python LLM Facade

```python
LLM(platform="gemini_enterprise", **platform_options)

generate_response(
    prompt,
    model=None,
    config=None,
    tools=None,
    **extra_options,
) -> str

generate_response_with_metadata(
    prompt,
    model=None,
    config=None,
    tools=None,
    **extra_options,
) -> dict
```

`generate_response_with_metadata()` returns `text`, `raw_response`,
`citations`, `tool_calls`, and `provider`. Gemini defaults to
`gemini-2.5-flash`; Claude defaults to `claude-opus-4-8`; both use temperature
`0.2` and a default maximum of 8192 output tokens. Curator methods may override
these defaults. See the [LLM wrapper](docs/codebase.md#llm-wrapper),
[Gemini adapter](docs/codebase.md#gemini-enterprise-platform), and
[Claude adapter](docs/codebase.md#claude-vertex-platform).

### CLI Guide

All installed curator CLIs support
`--verbosity {quiet,error,warning,info,debug}`. Logs go to stderr. JSON output
goes to stdout unless `--out PATH` is provided. Each command also supports
`-h`/`--help`.

#### CLI Query Generation

Command: `cli_query_generator`

| Option | Default | Behavior |
| --- | --- | --- |
| `--theme TEXT` | `None` | Theme supplied directly |
| `--theme-file PATH` | `None` | UTF-8 theme file; takes precedence over `--theme` |
| `--max-queries {1,2,3}` | `3` | Maximum generated queries |
| `--verbosity LEVEL` | `warning` | Stderr logging level |
| `--out PATH` | stdout | Pretty JSON destination |

#### CLI Thematic Review

Command: `cli_thematic_reviewer [review|extract-evidence|judge-evidence]`.
Omitting the subcommand runs `review` and accepts the legacy top-level option
form.

| Option | Commands | Default and behavior |
| --- | --- | --- |
| `--publication-text TEXT`, `--publication-text-file PATH` | `review`, `extract-evidence` | Publication text; file takes precedence |
| `--theme TEXT`, `--theme-file PATH` | all | Theme text; file takes precedence |
| `--metadata TEXT`, `--metadata-file PATH` | `review`, `extract-evidence` | Metadata remains text; file takes precedence |
| `--title TEXT`, `--title-file PATH` | all | Optional title; file takes precedence |
| `--accession ID` | `review` | Repeatable supplied accession; default empty |
| `--strategy {direct,evidence_then_judgement}` | `review` | Default `direct` |
| `--evidences JSON`, `--evidences-file PATH` | `judge-evidence` | Parsed JSON evidence; file takes precedence |
| `--verbosity LEVEL` | all | Default `warning`; may follow the subcommand |
| `--out PATH` | all | Pretty JSON file; otherwise stdout |

#### CLI Ontology Harmonization

Commands:

- `cli_ontology_harmonizer harmonize`
- `cli_ontology_harmonizer harmonize-miniml-json`

Shared options:

| Option | Default | Behavior |
| --- | --- | --- |
| `--publication-context TEXT`, `--publication-context-file PATH` | `None` | Publication context; file takes precedence |
| `--ontology-frameworks JSON`, `--ontology-frameworks-file PATH` | built-ins | Framework configuration; file takes precedence |
| `--fields JSON`, `--fields-file PATH` | `{}` | Controlled fields; file takes precedence |
| `--storage-dir PATH` | package ontology storage | Cache, SQLite, and vector root |
| `--target-paths JSON`, `--target-paths-file PATH` | automatic/default | Extraction path specifications; file takes precedence |
| `--target-checker`, `--no-target-checker` | enabled | Enable/disable compound target checking |
| `--direct-lookup-judge`, `--no-direct-lookup-judge` | enabled | Enable/disable local candidate judging |
| `--rag-lookup`, `--no-rag-lookup` | enabled | Enable/disable cached semantic retrieval |
| `--rag-lookup-judge`, `--no-rag-lookup-judge` | enabled | Enable/disable semantic candidate judging |
| `--ols-lookup`, `--no-ols-lookup` | enabled | Enable/disable unrestricted OLS4 retrieval |
| `--ols-lookup-judge`, `--no-ols-lookup-judge` | enabled | Enable/disable OLS candidate judging |
| `--field-assignment-judge`, `--no-field-assignment-judge` | enabled | Enable/disable model field assignment |
| `--request-timeout SECONDS` | `30` | External request timeout |
| `--request-max-attempts N` | `3` | Maximum transport attempts |
| `--request-backoff SECONDS` | `1` | Exponential-backoff base |
| `--cache-ttl-seconds N` | `604800` | External-response cache TTL |
| `--force-refresh` | false | Bypass reusable external-response entries |
| `--rag-hierarchy` | false | Add cached parents/children to semantic candidates |
| `--rag-parent-depth N` | `2` when enabled | Parent traversal depth; requires `--rag-hierarchy` |
| `--rag-child-depth N` | `1` when enabled | Child traversal depth; requires `--rag-hierarchy` |
| `--rag-hierarchy-threshold-offset FLOAT` | `0.1` when enabled | Relative-score threshold offset; requires `--rag-hierarchy` |
| `--verbosity LEVEL` | `warning` | Stderr logging level; may follow the subcommand |
| `--out PATH` | stdout | Pretty JSON destination |

`harmonize`-only options:

| Option | Behavior |
| --- | --- |
| `--metadata-context TEXT`, `--metadata-context-file PATH` | Compact metadata context; file takes precedence |
| `--harmonization-targets JSON`, `--harmonization-targets-file PATH` | Target wrapper/list; file takes precedence |
| `--target JSON`, `--target-file PATH` | One target; file takes precedence |

`harmonize-miniml-json`-only options:

| Option | Behavior |
| --- | --- |
| `--miniml-json JSON`, `--miniml-json-file PATH` | MINiML object/list; file takes precedence |

### Ontology Cache Builder Guide

Command: `build_ontology_cache`. It runs each configured built-in framework in
an isolated child process, validates successful JSON incrementally, synchronizes
SQLite, and optionally builds semantic indexes. It prints manifest/log paths and
records per-framework failures without discarding successful work.

| Option | Default | Behavior |
| --- | --- | --- |
| `--timeout SECONDS` | `2700` | Per-framework child-process timeout |
| `--out-dir PATH` | repository `.dev` | Manifest and log directory |
| `--out-prefix TEXT` | timestamped | Manifest/log filename prefix |
| `--max-workers N` | CPU-bounded default | Concurrent framework workers |
| `--force-framework ID` | none | Redownload/reparse an ID; repeatable |
| `--rag-index` | false | Build Gemini/USearch partitions after SQLite sync |
| `-h`, `--help` | — | Display command help |

The programmatic equivalent is:

```python
from agentic_curator.curators.ontology_harmonizer.cache_builder import (
    build_ontology_cache,
)

manifest = build_ontology_cache(
    frameworks=None,
    out_dir=".dev",
    prefix=None,
    timeout=2700,
    force_frameworks=(),
    max_workers=None,
    rag_index=False,
)
```

### Code flow

```text
Python API or CLI
  ├─ QueryGenerator
  │    validate theme → structured LLM call → validate JSON → add dataset filter
  ├─ ThematicReviewer
  │    direct whole-publication review OR evidence extraction → judgement
  ├─ OntologyHarmonizer
  │    normalize/extract targets → target checker
  │    → SQLite exact/FTS → cached RAG → OLS4
  │    → promote term → resolve field → optionally update MINiML
  └─ build_ontology_cache
       parallel child builds → validate → SQLite sync → optional USearch indexes

Shared LLM facade → Gemini Vertex or Claude Vertex
Ontology boundaries → files, SQLite/FTS5, USearch, Gemini embeddings, OLS4 HTTP
```

The CLI parses direct/file inputs and writes JSON; curator orchestrators build
prompts and validate results; the LLM facade performs provider routing; provider
adapters translate requests and normalize responses. Provider exceptions
generally propagate, while ontology multi-framework and batch-cache operations
isolate failures where possible. See the canonical
[code flow](docs/codebase.md#code-flow) and
[method pseudocode](docs/codebase.md#method-orchestrator-pseudocode).

## Docs

- [Documentation index](docs/index.md) — routing table for stable handoff anchors.
- [Codebase handoff](docs/codebase.md) — canonical architecture, APIs,
  workflows, external calls, tests, and commands.

## Authors

Created by [jaychowcl](https://github.com/jaychowcl) @
[Saez-Rodriguez Group](https://saezlab.org) &
[GSK](https://www.gsk.com/) on June 2026.

### Please cite us using

Chow, J. (Jay Chow), Saez-Rodriguez Group, & GSK. (June 2026).
*agentic-curator* (Version 0.1.0) [Computer software]. GitHub.
https://github.com/jaychowcl/agentic_curator
