# agentic-curator

LLM-assisted thematic review and ontology metadata harmonization for life-science publications & metadata.

## Description

`agentic-curator` provides three curator workflows: a Europe PMC query
generator, a thematic reviewer that extracts and judges publication evidence,
and an ontology harmonizer that maps metadata fields and values to controlled
terms. It includes MINiML target
extraction/application, OWL-to-JSON conversion, exact and FTS5 SQLite lookup,
OLS and grounded-web search, LLM candidate judging, persistent field and
response caches, and provider routing for Gemini Enterprise and Claude on
Vertex AI.

## Installation

Install the package and console scripts from this repository:

```bash
python -m pip install -e .
```

Install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Or install the mirrored direct dependencies:

```bash
python -m pip install -r requirements.txt
```

### Requirements

- Python 3.10 or newer
- `anthropic[vertex]>=0.107,<1`
- `google-genai>=1.72,<2`
- `rdflib>=7,<8`
- `requests>=2,<3`
- `pytest>=8` for development
- Google Cloud credentials and project configuration for live Gemini Enterprise
  or Claude Vertex calls
- Network access for live LLM, OLS, web-search, and ontology-download requests

## Quickstart

### Python Query Generation

```python
from agentic_curator import QueryGenerator

result = QueryGenerator().generate_queries(
    "Include publications about fibrosis and fibrotic biology."
)
print(result["queries"])
```

The returned `queries` list can be passed directly to ThematicAtlases.

### CLI Query Generation

```bash
cli_query_generator --theme-file theme.md --max-queries 3 --out queries.json
```

### Python Thematic Review

See the [Python thematic reviewer guide](#python-thematic-reviewer).

```python
from agentic_curator import ThematicReviewer

result = ThematicReviewer().review_relevancy(
    publication_text="Full publication text",
    theme="fibrosis",
    metadata={"organism": "human", "tissue": "lung"},
    title="Publication title",
    accessions=["GSE110147", "GSE102674"],
)
print(result["judgement"])
```

### CLI Thematic Review

See the [thematic reviewer CLI guide](#thematic-reviewer-cli).

```bash
cli_thematic_reviewer review \
  --publication-text-file publication.txt \
  --theme-file theme.txt \
  --metadata-file metadata.json \
  --title "Publication title" \
  --out review.json
```

### Python Ontology Harmonization

See the [Python ontology guide](#python-ontology-harmonization).

```python
from agentic_curator import OntologyHarmonizer
from agentic_curator.curators.ontology_harmonizer import OntoStore

store = OntoStore(fields={"organism": {"label": "Organism"}})
result = OntologyHarmonizer(ontostore=store).harmonize(
    publication_context="Mouse lung study.",
    target={
        "id": "target-1",
        "pre_hz_field": "organism",
        "pre_hz_label": "Mus musculus",
        "ontology_ids": ["ncbitaxon"],
    },
)
```

### CLI Ontology Harmonization

See the [ontology harmonizer CLI guide](#ontology-harmonizer-cli).

```bash
cli_ontology_harmonizer harmonize \
  --publication-context-file publication.txt \
  --target-file target.json \
  --fields-file fields.json \
  --out targets.json
```

### Ontology Cache Builder

See the [cache-builder guide](#ontology-cache-builder-guide).

```bash
build_ontology_cache --max-workers 4 --timeout 2700
```

### Python LLM Facade

See the [LLM facade guide](#python-llm-facade).

```python
from agentic_curator.wrappers import LLM

llm = LLM(platform="gemini_enterprise", project="my-project", location="global")
print(llm.generate_response("Summarize this publication."))
```

### Docker

This repository does not currently provide a Dockerfile or Docker Compose
interface. Use the Python package or installed console scripts.

### Inputs & Outputs

Query generation accepts a non-empty theme and returns final Europe PMC query
strings alongside matching purposes and a strategy summary. Each final query
includes the dataset-link filter used by ThematicAtlases.

The thematic reviewer accepts publication text, a theme, optional metadata and
title, and accession identifiers. Direct review is the default and returns one
flat structured decision over the complete publication:

```json
{
  "judgement": "relevant",
  "reasoning": "...",
  "confidence": "high",
  "accessions_to_remove": [],
  "strategy": "direct"
}
```

Ontology harmonization accepts a target, a target list, or MINiML-style JSON.
Targets use human-readable `pre_hz_field` and `pre_hz_label`; outputs add
normalized `hz_field`, `hz_label`, ontology match metadata, assignments, and
stage traces. The wrapper is:

```json
{
  "publication_context": "...",
  "harmonization_targets": [],
  "workflow": "local_rag_ols",
  "controls": {},
  "target_paths": []
}
```

`harmonize_miniml_json(...)` also returns the same input object under
`miniml_json` after applying direct `hz_<field>`, `hz_<field>_id`, and
`hz_<field>_onto` values. Tag/value inputs receive additional tag/value rows;
container inputs receive a sibling `hz_<field>` list. Its `target_checker`
trace describes dataset-level compound-label additions made before lookup.

`OntoStore.lookup(...)` returns term dictionaries with `ontology_id`.
`LLM.generate_response_with_metadata(...)` returns `text`, `raw_response`,
`citations`, `tool_calls`, and `provider`.

## Guide

### Python Query Generator

`QueryGenerator(llm=None).generate_queries(theme, max_queries=3)` makes one
schema-constrained LLM call and returns `queries`, matching `details`, and a
short `strategy_summary`. The domain-neutral prompt prefers one comprehensive
query made of AND-joined mandatory concept groups with extensive OR synonyms;
more queries require an unbridgeable logical, semantic, syntax, or length gap.
It adds `(HAS_DATA:y OR HAS_LABSLINKS:y)` programmatically to every query.

At DEBUG/INFO, shared LLM telemetry reports platform/model, prompt and response
sizes, tool/citation counts, duration, and failures. Curators add aggregate
query, evidence, judgement, ontology-target, and cache-framework statistics.
Prompt/response bodies, publication and metadata contexts, credentials, and
headers are not logged.
The curator does not call Europe PMC or estimate hit counts.

### Query Generator CLI

| Option | Behavior |
| --- | --- |
| `--theme`, `--theme-file` | Theme definition; file takes precedence |
| `--max-queries {1,2,3}` | Maximum complementary queries; default `3` |
| `--verbosity {debug,error,info,quiet,warning}` | Logging level on stderr |
| `--out` | Pretty JSON file; otherwise stdout |

### Python Thematic Reviewer

`ThematicReviewer(llm=None)` accepts an injected LLM-like object or lazily
creates `LLM()`.

| Method | Inputs | Output |
| --- | --- | --- |
| `review_relevancy(..., accessions=None, strategy="direct")` | Text/theme, optional metadata/title, accessions, and `direct` or `evidence_then_judgement` | Flat judgement with trace-only accession exclusions |
| `extract_evidence(..., accessions=None)` | Legacy reviewer source inputs | Parsed evidence dict/list |
| `judge_evidence(..., accessions=None)` | Legacy evidence object plus theme/title/accessions | Flat parsed judgement |

The methods load packaged Markdown prompts, request schema-constrained JSON,
and parse provider text with `parse_json_response(...)`. Invalid JSON raises
`ValueError`.

### Thematic Reviewer CLI

Commands:

| Command | Python method |
| --- | --- |
| No subcommand or `review` | `review_relevancy(...)` |
| `extract-evidence` | `extract_evidence(...)` |
| `judge-evidence` | `judge_evidence(...)` |

Options:

| Option | Availability and behavior |
| --- | --- |
| `--verbosity {debug,error,info,quiet,warning}` | Global or subcommand logging level; logs go to stderr |
| `--publication-text`, `--publication-text-file` | Review/extraction text; file takes precedence |
| `--theme`, `--theme-file` | Theme text; file takes precedence |
| `--metadata`, `--metadata-file` | Review/extraction metadata text; file takes precedence |
| `--title`, `--title-file` | Optional title; file takes precedence |
| `--evidences`, `--evidences-file` | JSON for `judge-evidence`; file takes precedence |
| `--out` | Pretty JSON file; otherwise stdout |

### Python Ontology Harmonization

#### `OntologyHarmonizer`

`OntologyHarmonizer(ontostore=None, llm=None, request_policy=None,
rag_similarity_threshold=0.5, rag_hierarchy=False, rag_parent_depth=2,
rag_child_depth=1, rag_hierarchy_threshold_offset=0.1)` coordinates target
normalization, lookup, assignment, search, enrichment, and application.

| Method | Main options |
| --- | --- |
| `harmonize(...)` | User contexts and targets plus independent target-checker, direct, RAG, OLS, and field-stage controls |
| `harmonize_miniml_json(...)` | User `publication_context`, `miniml_json`, `ontostore`, `target_paths`, and the same stage controls; `metadata_context` is generated automatically |
| `lookup_label(...)` | Target, publication context, store, and direct judge toggle |
| `lookup_rag_label(...)` | Target, contexts, store, and semantic judge toggle |
| `judge_lookup(..., candidate_limit=10)` | Judge compact local or balanced semantic candidates |
| `harmonize_field(...)` | Target, publication context, store, and field-assignment judge toggle |
| `harmonize_label(...)` | Target, publication context, store, and OLS judge toggle |
| `apply_targets(miniml_json, harmonization_targets)` | Mutates and returns MINiML JSON |

Local term lookup uses exact normalized SQLite keys first, then FTS5 over
labels, synonyms, descriptions, IDs, accessions, and IRIs. Every local candidate
set is judged by default, including a single exact hit. A local or OLS judge can
return `decision="false"` to terminally skip a non-harmonizable target. Skipped
targets record `harmonization_status="skipped"` and a structured
`harmonization_skip` trace, then bypass OLS fallback, label promotion, field
harmonization, and MINiML application. A genuine local miss proceeds to
semantic lookup over cached local frameworks, then to OLS if semantic lookup
also misses. A selected OLS term supplies its framework metadata and
may be enriched locally only by matching its identifier. The OLS judge receives
one neutral `OLS Hits` candidate section without restricted/unrestricted stage
cues. Field-assignment context includes both the canonical `label` and the
original `pre_hz_label` when available.

There is no global runtime model toggle. Retrieval and judging are controlled
independently for each stage. An unjudged direct lookup accepts only one unique
exact identity; ambiguous exact, FTS, RAG, and OLS candidates remain trace
evidence and are not applied automatically. The result records the effective
settings under `controls`.

Before per-target lookup, `harmonize(...)` makes one target-checker LLM call
over its complete normalized target list, whether supplied directly or by the
MINiML wrapper. It can append missing atomic
concepts from compound labels while preserving every original target. Only
medium/high-confidence additions are accepted, capped at three per source;
equivalent additions are merged with per-source reasons and occurrence paths.
Same-role abbreviations, synonyms, and broader/narrower restatements are not
additions. The field is a hint and is finalized by the normal field stage.
Invalid calls are retried once and then fail open. Set `target_checker=False`
to opt out.

Semantic candidates must meet the inclusive default `rag_score >= 0.5`.
Framework configuration may set `rag_similarity_threshold` to override the
harmonizer-wide value. Up to two qualifying candidates are reserved from every
ontology, remaining seats up to 10 are filled by global similarity, and the
single judge context expands when the reservations exceed 10. Effective
thresholds and balanced hits are retained in the `ontology_rag` trace.

Hierarchy-aware semantic expansion is disabled by default. When
`rag_hierarchy=True`, the best two reserved semantic terms in each ontology
become graph anchors. Cached named `rdfs:subClassOf` edges contribute at most
one best parent at each configured depth and one best child at each configured
depth. The defaults inspect parents through depth two and children through
depth one. Relatives reuse the original query vector and persisted term vectors,
must meet `max(-1, ontology_threshold - 0.1)`, and are appended to the same
single semantic judge call with relation, depth, seed, and score provenance.

#### `OntoStore`

`OntoStore(ontology_frameworks=None, fields=None, storage_dir=None,
sqlite_path=None, request_policy=None)` owns framework files and the shared
SQLite database.

| Method | Purpose |
| --- | --- |
| `configure_framework(...)`, `add_url(...)`, `add_urls(...)` | Add, edit, or remove framework configuration, including an optional RAG similarity threshold |
| `download(name)`, `get(name, force=False)` | Download OWL and create/reuse JSON |
| `lookup(value, ontology_id)` | Compatible exact-then-FTS term lookup |
| `lookup_with_metadata(value, ontology_id)` | Return `match_type`, hits, and FTS ranking |
| `lookup_exact(value, ontology_id, ensure_index=True)` | Exact normalized lookup only |
| `lookup_rag(value, ontology_id, top_k=10)` | Semantic top-k lookup over one cached local framework |
| `lookup_rag_many(value, ontology_ids, top_k=10, parent_depth=0, child_depth=0)` | Embed once and search cached framework partitions sequentially; optional depths return hierarchy hits separately |
| `build_rag_index(ontology_id, force=False)` | Build or reuse its persistent Gemini/USearch partition |
| `index_framework(...)`, `index_owl_framework(...)`, `sync_sqlite(...)`, `remove_indexed_framework(...)` | Import legacy JSON or stream OWL into SQLite term indexes |
| `cache_all(..., force_frameworks=())` | Stream-cache every selected active framework, optionally forcing named downloads |
| `lookup_fields(field)` | Resolve a canonical field or alias |
| `add_field(...)`, `update_field(...)`, `remove_field(...)` | Persistent field-registry mutation |
| `get_field(...)`, `list_fields(...)`, `set_field_review_status(...)` | Retrieve and review fields |
| `get_cached_response(...)`, `set_cached_response(...)`, `clear_cached_responses(...)` | External-response cache CRUD |
| `harmonize_key(value)` | Normalize lookup keys |

LLM-created fields are immediately active and persisted as `unreviewed`.
Field metadata can include canonical labels, aliases, descriptions, expected
ontologies, allowed extraction modes, source, confidence, and reason.

#### Extraction And OWL Utilities

`HarmonizationTargetExtractor.extract(metadata, start_paths=None)` supports
`field_value`, `tag_value`, and `container_value` path modes.
`build_miniml_sample_target_paths(...)` discovers sample channel source,
molecule, organism, and characteristic paths. `dedupe_targets(...)` combines
identical field/label targets while retaining all occurrences.

`build_miniml_metadata_context(miniml_json, max_chars=500)` creates the shared
LLM-facing MINiML summary: first series title plus unique source, molecule,
organism, and characteristic `field=value` pairs. It is deterministic,
whitespace-normalized, and excludes unrelated protocol/platform sections.

`Owl2json(owl_path).parse(ontology_id=None)` reads RDF/XML with RDFLib.
`write_json(output_path, ontology_id=None)` writes label, ID, accession, and
IRI indexes while retaining ontology and term metadata.

#### Request And Search Controls

`RequestPolicy(timeout_seconds=30, max_attempts=3,
backoff_base_seconds=1, cache_ttl_seconds=604800, force_refresh=False)` controls
network/LLM retries and response reuse. Transient network, 429, and 5xx errors
use exponential jittered backoff.

`OlsClient` calls OLS4 search and ontology APIs. `OlsStrategyHandler`
implements restricted and unrestricted OLS search judging without grounded web
search. `RagStrategyHandler` remains a placeholder.

### Ontology Harmonizer CLI

Commands are `harmonize` and `harmonize-miniml-json`. Direct JSON options and
their `-file` counterparts are mutually substitutable; files take precedence.

| Option | Behavior |
| --- | --- |
| `--verbosity {debug,error,info,quiet,warning}` | Logging level; logs go to stderr |
| `--publication-context`, `--publication-context-file` | User-supplied publication context |
| `--metadata-context`, `--metadata-context-file` | Compact metadata context for direct `harmonize` only; files take precedence |
| `--ontology-frameworks`, `--ontology-frameworks-file` | JSON framework configuration |
| `--fields`, `--fields-file` | JSON controlled-field configuration |
| `--storage-dir` | OWL, JSON, and SQLite storage root |
| `--target-paths`, `--target-paths-file` | JSON path specifications |
| `--target-checker`, `--no-target-checker` | Enable/disable compound-target checking for either harmonization command; enabled by default |
| `--direct-lookup-judge`, `--no-direct-lookup-judge` | Enable/disable judging ambiguous local exact and FTS candidates; enabled by default |
| `--rag-lookup`, `--no-rag-lookup` | Enable/disable local semantic retrieval; enabled by default |
| `--rag-lookup-judge`, `--no-rag-lookup-judge` | Enable/disable judging semantic candidates; enabled by default |
| `--ols-lookup`, `--no-ols-lookup` | Enable/disable unrestricted OLS retrieval; enabled by default |
| `--ols-lookup-judge`, `--no-ols-lookup-judge` | Enable/disable judging OLS candidates; enabled by default |
| `--field-assignment-judge`, `--no-field-assignment-judge` | Enable/disable model assignment when the field registry misses; enabled by default |
| `--request-timeout SECONDS` | Per-request timeout; default `30` |
| `--request-max-attempts N` | Maximum attempts; default `3` |
| `--request-backoff SECONDS` | Exponential backoff base; default `1` |
| `--cache-ttl-seconds N` | External cache TTL; default seven days |
| `--force-refresh` | Bypass cached external responses |
| `--rag-hierarchy` | Enable cached parent/child expansion; disabled by default |
| `--rag-parent-depth N` | Parent traversal depth; default `2` when hierarchy is enabled |
| `--rag-child-depth N` | Child traversal depth; default `1` when hierarchy is enabled |
| `--rag-hierarchy-threshold-offset SCORE` | Relax each ontology threshold for relatives; default `0.1` |
| `--harmonization-targets`, `--harmonization-targets-file` | Target object/list for `harmonize` |
| `--target`, `--target-file` | Single target for `harmonize`; cannot accompany target list |
| `--miniml-json`, `--miniml-json-file` | MINiML JSON for `harmonize-miniml-json` |
| `--out` | Pretty JSON file; otherwise stdout |

The three hierarchy tuning options require `--rag-hierarchy`; using one without
the enable flag is a parser error.

### Ontology Cache Builder Guide

`build_ontology_cache` downloads and parses built-in frameworks concurrently,
then synchronizes successful JSON caches into the shared SQLite database.
Pass `--rag-index` to build persistent semantic partitions after SQLite sync.

Programmatic callers can eagerly prepare one configured store before a workflow:

```python
store = OntoStore(storage_dir=".cache/ontologies")
store.configure_framework("snomed", remove=True)
manifest = store.cache_all(force_frameworks=["ncbitaxon"])
```

`cache_all()` directly streams OWL through a temporary SQLite triple store and
does not create new JSON caches. Existing JSON remains readable, and
`Owl2json.write_json()` remains available for explicit conversion. The method
attempts active frameworks in configuration order before raising
`OntologyCacheError` for aggregate failures. The exception exposes the complete
manifest through `.results`; pass `fail_on_error=False` to continue with a
partial cache.

Existing legacy JSON caches are also indexed without materializing the complete
document: `ijson` streams their lookup maps into bounded SQLite batches. A
URL-backed default framework is eligible for exact, FTS, and semantic lookup
whenever its configured JSON or OWL cache path exists. An uncached framework is
skipped—even when explicitly requested—so lookup never downloads ontology data.

For multi-framework semantic lookup, the query is embedded once and each
ontology's persistent USearch partition is searched sequentially. Query-time
partitions are memory-mapped from disk. Document embeddings are still generated
in batches of at most 250 with one model and dimensionality, placing every batch
in the same vector space. Building a partition keeps that one framework's
USearch vectors in memory; the indexes remain separate rather than being merged.
Before the semantic judge call, results are thresholded per ontology and
balanced by reserving its best two qualifying terms. The base context remains
10 candidates, but grows when more than five ontologies have two qualifying
reservations.

| Option | Behavior |
| --- | --- |
| `--timeout SECONDS` | Per-framework child-process timeout |
| `--out-dir PATH` | Output directory for status files |
| `--out-prefix TEXT` | Status filename prefix |
| `--max-workers N` | Concurrent framework workers |
| `--force-framework ID` | Redownload/reparse one framework; repeatable |
| `--rag-index` | Embed successful framework terms and build USearch partitions |

### Python LLM Facade

`LLM(platform="gemini_enterprise", **platform_options)` supports
`gemini_enterprise` and `claude_vertex`.

| Method | Output |
| --- | --- |
| `generate_response(prompt, model=None, config=None, tools=None, **extra_options)` | Text |
| `generate_response_with_metadata(prompt, model=None, config=None, tools=None, **extra_options)` | Text plus raw response, citations, tool calls, and provider |

A call-level model beginning with `claude-` routes to a lazily created Claude
Vertex adapter even when Gemini is the default. `GeminiEnterprisePlatform`
calls `google.genai.Client.models.generate_content(...)`.
`ClaudeVertexPlatform` calls
`anthropic.AnthropicVertex.messages.create(...)`.

### Code flow

#### Thematic reviewer

```python
def review_relevancy(inputs):
    if inputs.strategy == "direct":
        return direct_whole_publication_judgement(inputs)  # one LLM call
    evidences = extract_evidence(inputs)                   # legacy call one
    judgement = judge_evidence(evidences, inputs)          # legacy call two
    return {**judgement, "evidences": evidences}
```

#### Ontology harmonizer

```python
def harmonize(targets, publication_context):
    targets = normalize_targets(targets)
    targets += target_checker_additions(targets)  # one enabled-by-default call
    for target in targets:
        normalize_working_field_and_label(target)
        local = lookup_exact_then_fts(target)
        if local:
            local = judge_lookup_or_skip(local[:10], publication_context)
        if target.is_skipped:
            continue
        if not local:
            semantic = lookup_cached_framework_vectors(target.label)
            qualifying = apply_per_ontology_similarity_thresholds(semantic)
            balanced = reserve_two_per_ontology_then_fill_globally(qualifying)
            if hierarchy_enabled:
                relatives = best_cached_relatives(top_two_per_ontology(balanced))
                balanced.extend(apply_relative_thresholds(relatives))
            local = judge_semantic_candidates_or_continue(balanced)  # one call
        if not local:
            unrestricted = OLS.search(target.label)
            selected = judge_ols_candidates_or_skip(unrestricted)
            if target.is_skipped:
                continue
            if selected:
                configure_selected_framework_from_OLS(selected)
            enrich_selected_term_by_exact_identifier_only(selected)
        promote_selected_term_title_to_harmonized_label(target)
        resolve_field_from_registry_or_assign_and_persist(target)
    return target_wrapper
```

`harmonize_miniml_json(...)` calls target-path discovery, extraction and
deduplication, delegates the extracted list and target-checker option to
`harmonize(...)`, then calls `apply_targets(...)`;
application defensively ignores every skipped target.

#### Ontology store and cache

```python
def get(framework):
    owl = existing_file_or_requests_download(framework.url)
    return Owl2json(owl).write_json(framework.json_path)  # explicit JSON API

def index_owl_framework(framework):
    owl = existing_file_or_requests_download(framework.url)
    staging = stream_rdfxml_triples_to_temporary_sqlite(owl)
    atomically_stream_class_terms_into_shared_sqlite(staging)
    delete_staging_sqlite(staging)

def lookup(value, framework):
    exact = lookup_exact(normalize(value), framework)
    return exact or fts5_rank(value, framework)

def lookup_rag_many(value, cached_frameworks, parent_depth=0, child_depth=0):
    indexes = build_or_reuse_each_partition_sequentially(cached_frameworks)
    query_vector = embed_query_once(value)
    semantic = search_each_memory_mapped_partition(query_vector, indexes)
    if parent_depth or child_depth:
        edges = lazily_backfill_named_subclass_edges_from_sqlite_terms()
        anchors = top_two_per_ontology(semantic)
        hierarchy = traverse_and_score_relatives(query_vector, anchors, edges)
    return semantic, hierarchy
```

The SQLite database stores framework freshness, terms, exact lookup entries,
FTS5 rows, persistent hierarchy edges, persistent fields/aliases, and cached
OLS/Gemini responses.

#### CLI and providers

```python
def cli_main(argv):
    args = parse_args(argv)
    read_direct_or_file_inputs(args)
    result = dispatch_to_reviewer_or_harmonizer(args)
    write_pretty_json_to_out_or_stdout(result)

def LLM.generate_response_with_metadata(prompt, model=None, **options):
    platform = route_claude_model_or_use_default(model)
    return platform.generate_response_with_metadata(prompt, model=model, **options)
```

External boundaries are Google Gen AI, Anthropic Vertex, OLS4, ontology HTTP
downloads, SQLite, and RDFLib. See the canonical handoff for method-level call
graphs and LLM context tables.

## Docs

- [Documentation index](docs/index.md)
- [Codebase handoff](docs/codebase.md)

## Authors

Created by [jaychowcl](https://github.com/jaychowcl) @
[Saez-Rodriguez Group](https://saezlab.org) &
[GSK](https://www.gsk.com/) on June 2026

### Please cite us using

Chow, J. (Jay Chow), Saez-Rodriguez Group, & GSK. (June 2026).
*agentic-curator* (Version 0.1.0) [Computer software]. GitHub.
https://github.com/jaychowcl/agentic_curator
