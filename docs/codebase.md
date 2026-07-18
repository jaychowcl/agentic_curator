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
publications. The current package covers Europe PMC query generation,
publication evidence extraction, final relevance judging, ontology
harmonization, and provider adapters for Gemini and Claude on Vertex AI.

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
    cli_query_generator.py
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
        judge_search.md
    query_generator/
      __init__.py
      generator.py
      prompts/
        generate_queries.md
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
  test_cli_query_generator.py
  test_cli_thematic_reviewer.py
  test_curator_llm_wrappers.py
  test_ontology_harmonizer.py
  test_query_generator.py
  test_owl2json.py
  test_repository_metadata.py
  test_thematic_reviewer.py
  test_workflow_logging.py
```

Ignored local development artifacts include `.dev/`, `.env/`, `.vscode/`,
Python caches, pytest caches, build outputs, and editable-install metadata.

Tracked comment-capable project files carry exactly one distinctive authors
header at the top of the file. Python, TOML, requirements, and `.gitignore` use
`#` comments; all project-owned Markdown other than `README.md` uses a leading
HTML comment, including packaged prompts. `README.md` keeps linked authorship in
its visible `## Authors` section and includes a complete software citation
subsection. The externally sourced GPL `LICENSE` is intentionally unchanged.

<a id="runtime-and-packaging"></a>
## Runtime And Packaging

The package uses a `src/` layout with setuptools:

- project name: `agentic-curator`
- import package: `agentic_curator`
- Python requirement: `>=3.10`
- runtime dependencies: `anthropic[vertex]>=0.107,<1`, `filelock>=3,<4`,
  `google-genai>=1.72,<2`, `ijson>=3,<4`, `rdflib>=7,<8`,
  `requests>=2,<3`, and `usearch>=2,<3`
- dev extra: `pytest>=8`
- `requirements.txt` mirrors the direct runtime/dev dependencies for pip-based
  environment bootstrap and includes `-e .`
- console scripts:
  - `build_ontology_cache = "agentic_curator.curators.ontology_harmonizer.cache_builder:main"`
  - `cli_thematic_reviewer = "agentic_curator.cli.cli_thematic_reviewer:main"`
  - `cli_ontology_harmonizer = "agentic_curator.cli.cli_ontology_harmonizer:main"`
  - `cli_query_generator = "agentic_curator.cli.cli_query_generator:main"`
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
from agentic_curator.curators import OntologyHarmonizer, QueryGenerator, ThematicReviewer
```

`agentic_curator.__init__` also exports all three curator classes. The old flat
module import `agentic_curator.thematic_reviewer` remains intentionally absent.

`agentic_curator.curators.ontology_harmonizer` exports ontology-specific helper
classes including `OntoStore`, `Owl2json`, `OlsClient`,
`NullSearchClient`, `GeminiGroundedSearchClient`, `WebsearchStrategyHandler`,
`RagStrategyHandler`, and `RequestPolicy`.

`ThematicReviewer(llm=None)` accepts an optional LLM-like object. If no object is
provided, the reviewer lazily creates `agentic_curator.wrappers.LLM()` on the
first generation call.

Main methods:

- `review_relevancy(..., accessions=None, strategy="direct") -> dict`
- `extract_evidence(..., accessions=None) -> dict | list` (legacy)
- `judge_evidence(..., accessions=None) -> dict | list` (legacy)

`metadata` may be a string, dictionary, list, or `None` when used by reviewer
prompt helpers. The reviewer asks providers for JSON output, passes dict/list
responses through, parses JSON text with `json.loads(...)`, and raises
`ValueError` for invalid JSON text.

Direct review, evidence extraction, and final judgement request
`max_output_tokens=16384`.
Gemini counts internal thinking against this budget, so the reviewer overrides
the wrapper's smaller general default for long full-text evidence responses.
Invalid or truncated consumed responses still raise and are not regenerated
automatically; the atlas caller isolates and records the affected publication.

<a id="query-generator"></a>
## Query Generator

`QueryGenerator(llm=None).generate_queries(theme, max_queries=3)` makes one
structured LLM call. `theme` must be non-empty and `max_queries` must be an
integer from one to three. The model returns topical clauses and purposes; the
curator validates non-empty, unique details and derives this public result:

```python
{
    "queries": ["(<topical clause>) AND (HAS_DATA:y OR HAS_LABSLINKS:y)"],
    "details": [{"query": "<same final query>", "purpose": "..."}],
    "strategy_summary": "...",
}
```

The dataset-link filter is added in code and model responses containing
`HAS_DATA:` or `HAS_LABSLINKS:` are rejected. The curator does not call Europe
PMC, count hits, or retry generation. `queries` is directly compatible with
ThematicAtlases' current `list[str]` collector input; downstream
`max_publications` remains the cost boundary.
The domain-neutral prompt defaults to one comprehensive query. It asks the
model to identify independent mandatory theme concepts, build an extensive
synonym/variant `OR` group for each, and join concept groups with `AND`.
Additional queries are allowed only for an explained unbridgeable Boolean,
semantic-collision, syntax, or query-length gap; organ, disease, assay subtype,
mechanism, and spelling variations must remain in one query when `OR` can
bridge them. This is prompt guidance rather than semantic response validation.

<a id="ontology-harmonizer"></a>
## Ontology Harmonizer

`agentic_curator.curators.ontology_harmonizer.OntologyHarmonizer` maps extracted
metadata targets to local ontology terms, semantic neighbours, OLS terms, and
canonical fields. The workflow is fixed; callers no longer select a strategy.
Constructor hierarchy controls are `rag_hierarchy=False`,
`rag_parent_depth=2`, `rag_child_depth=1`, and
`rag_hierarchy_threshold_offset=0.1`.

Public methods:

- `harmonize(publication_context=None, metadata_context=None, harmonization_targets=None, target=None, ontostore=None, target_paths=None, lookup_llm_judge=True, search_llm_judge=True, llm=True) -> dict`
- `harmonize_miniml_json(publication_context=None, miniml_json=None, ontostore=None, target_paths=None, lookup_llm_judge=True, search_llm_judge=True, llm=True) -> dict`
- `lookup_label(...)`, `lookup_rag_label(...)`, and `harmonize_label(...)`
- `judge_lookup(..., candidate_limit=10)`
- `harmonize_field(...)` and `assign_field(...)`
- `apply_targets(miniml_json, harmonization_targets) -> dict | list | None`

The top-level wrapper contains `workflow="local_rag_ols"`. Per-stage OLS
results use `source="ols"`; there is no public `strategy` argument or
`--strategy` CLI option.

### Per-target workflow

1. Normalize `pre_hz_field` and `pre_hz_label` into working `hz_field` and
   `hz_label`.
2. Run exact local SQLite lookup, then FTS5 when exact lookup misses.
3. If local candidates exist, the lookup judge either selects an ID, returns
   `no_match` to continue, or returns `false` to terminally skip the target.
4. After a local miss or `no_match`, call `OntoStore.lookup_rag_many(...)` for
   the locally cached candidate frameworks. It embeds the label once, searches
   each framework partition sequentially, filters by the effective similarity
   threshold, reserves up to two hits per qualifying ontology, and lets the
   same judge accept or reject the balanced candidates. Optional hierarchy
   expansion appends bounded vector-ranked parents and children before that
   same judge call; it is disabled by default.
5. After a semantic miss or `no_match`, search OLS without first asking the
   model to select a framework. OLS is the only external ontology search;
   grounded web search is not part of this workflow.
6. An OLS judge selection is locally enriched by exact identifier only. A
   `no_match` result remains unmatched and a `false` result terminally skips
   the target.
7. Promote the selected ontology term title to `hz_label`.
8. Harmonize the field using that harmonized label. Registry lookup runs first;
   an unknown field may be assigned and persisted by the field LLM.
9. `harmonize_miniml_json(...)` applies non-skipped targets back to the supplied
   object.

`llm=False` disables semantic lookup because semantic candidates require an
LLM judge, disables OLS judging, and disables field assignment. It does not
disable deterministic exact/FTS lookup or raw OLS retrieval behavior.

A selected term mutates the target with `ontology_match=True`,
`ontology_id`, `ontology_lookup`, and `ontology_lookup_hits`. Semantic
traces live at `ontology_rag`; OLS traces live at `ontology_ols_result`.
Terminal rejections record `harmonization_status="skipped"` and
`harmonization_skip`, and bypass later stages and MINiML application.

### LLM calls and model context

All structured calls preserve the full user `publication_context` and the
separate compact `metadata_context` when supplied. They use compact semantic
target projections rather than serializing the mutable target, occurrences,
paths, prior traces, or internal framework file metadata.

| Logical call | When | Model-facing context |
| --- | --- | --- |
| Local lookup judge | Exact or FTS candidates exist and judging is enabled. | Publication context; metadata context; semantic target with original field/label; top 10 compact local hits. |
| Semantic lookup judge | Local lookup misses and semantic neighbours meet their thresholds. | The same contexts and target; balanced compact RAG hits including ontology IDs and scores. Up to two hits are reserved per qualifying ontology; the list expands beyond 10 when required, otherwise remaining seats are filled globally by similarity. When hierarchy expansion is enabled, accepted relatives also include `rag_relation`, `rag_depth`, and `rag_seed_id`. |
| OLS judge | Local and semantic lookup miss and OLS returns candidates. | Publication context; metadata context; semantic target; one neutral OLS candidate list. No restricted/unrestricted stage literal is included. |
| Field assignment | Registry lookup misses after label harmonization. | Publication context; metadata context; semantic target containing the current harmonized label plus `pre_hz_label`; current ontology ID when known; configured field projections. |

Compact candidate hits contain identifiers, title, complete description, and
ontology ID; semantic hits also contain their RAG score and optional hierarchy
provenance. Lookup- and OLS-judge decisions may use one supplied ID, accession,
or IRI, plus `no_match` or `false`. `no_match` rejects the candidates but
continues the workflow; `false` declares the target non-harmonizable and stops
it. For a selected candidate, the judge copies one non-null identifier exactly;
validation resolves only identifiers from the candidate list actually sent to
that judge. This supports ontology caches whose canonical terms provide an
accession but no separate `id`.

The default RAG threshold is inclusive `rag_score >= 0.5`. The harmonizer-wide
value is configurable through `rag_similarity_threshold`; a framework's
`rag_similarity_threshold` metadata overrides it. Effective thresholds are
recorded in `ontology_rag.similarity_thresholds`. An ontology with no hit above
its threshold has no reserved candidate. Deduplication is ontology-scoped so a
shared identifier can remain represented in more than one framework.

`rag_hierarchy=False` is the default and preserves non-expanding behavior.
When enabled, the first two reserved semantic terms per ontology become
anchors. Defaults add at most one best direct parent, one best second-level
parent, and one best direct child per ontology. A relative must meet
`max(-1, ontology_threshold - rag_hierarchy_threshold_offset)`, whose default
offset is `0.1`. Selection reuses the original query and stored term vectors,
so there is still one query embedding and one semantic judge call. With the 11
built-in frameworks, 22 reserved semantic candidates can grow to at most 55.
The `ontology_rag.hierarchy` trace records enabled depths, offset, and selected
relatives.

The maximum is four logical LLM calls per target: local judge, semantic judge,
OLS judge, and field assignment. A stage without candidates makes no judge call.
A successful earlier term match skips later term-search calls. Retry policy can
make multiple provider attempts for one logical call.

### MINiML extraction and application

`harmonize_miniml_json(...)` uses `HarmonizationTargetExtractor`. With no
explicit `target_paths`, it discovers meaningful sample/channel source,
molecule, organism, and characteristic values, then deduplicates identical
field/label targets while preserving all occurrence paths. It creates a
deterministic metadata context from the first series title and unique
`field=value` pairs, collapsed to one line and capped at 500 characters.
`build_miniml_metadata_context(...)` exposes the same behavior.

`apply_targets(...)` writes direct sibling `hz_<field>` values for scalars,
additional tag/value rows for tag-shaped data, and sibling lists for container
values. It adds term IDs and ontology IDs when available. Malformed paths and
skipped targets are ignored.

### OntoStore and persistent semantic lookup

`OntoStore` owns ontology framework configuration, local OWL/JSON sources, the
shared SQLite database, field registry, external-response cache, and semantic
indexes.

Important methods:

- `lookup(...)`, `lookup_with_metadata(...)`, and `lookup_exact(...)`
- `lookup_rag(label, ontology_id, top_k=10)`
- `lookup_rag_many(label, ontology_ids, top_k=10, parent_depth=0, child_depth=0)`
- `build_rag_index(ontology_id, force=False)`
- `index_framework(...)`, `index_owl_framework(...)`, `sync_sqlite(...)`,
  and `remove_indexed_framework(...)`
- `cache_all(...)`
- field registry and external-response cache CRUD methods

Exact normalized lookup precedes FTS5 over labels, synonyms, descriptions, IDs,
accessions, and IRIs. Legacy JSON is parsed incrementally with `ijson`: each of
the label, ID, accession, and IRI maps is streamed into bounded SQLite batches,
then canonical stored terms are streamed into FTS5 batches. RDF/XML classes use
a bounded temporary SQLite staging database. Framework replacement is
transactional and freshness uses source path, size, and nanosecond mtime.

`lookup_rag(...)` never downloads an uncached framework. It returns an empty
list unless a local JSON or OWL source already exists. For a cached framework it
ensures SQLite terms exist, builds or reuses one USearch cosine index partition,
embeds the query, retrieves top-k vector IDs, joins those IDs back to canonical
SQLite term payloads, and returns terms with `ontology_id` and `rag_score`.
`lookup_rag_many(...)` prepares eligible partitions in configuration order,
isolates per-framework build/search failures, embeds the query exactly once,
and searches the partitions sequentially. It returns all per-partition hits and
errors; the harmonizer deduplicates and globally ranks the combined candidates.
The harmonizer requests up to 10 neighbours from every partition, applies each
framework's threshold, reserves its best two qualifying unique terms, and fills
any remaining capacity up to 10 from the global score order. If the reservations
alone exceed 10, every reservation is retained in the single judge call.

Non-zero hierarchy depths lazily build persistent same-ontology edges from the
named `parents` and `parent_iris` already stored in SQLite. Anonymous,
unresolved, external, and self references are ignored. Parent traversal uses
the forward `subClassOf` edge and child traversal uses its indexed reverse;
the lazy backfill indexes normalized temporary parent lookup keys so large
frameworks resolve edges with indexed probes rather than repeated broad scans.
Shortest-depth cycle detection prevents revisits. Only the best two semantic
hits in each ontology are traversed. Related vector rows are read and scored in
batches of 500 with exact cosine similarity to the original query vector.
`lookup_rag_many(...)` returns direct `hits` unchanged and hierarchy candidates
separately in `hierarchy_hits` whenever expansion is requested.

Automatic local and semantic framework selection is cache-based, not
URL-configuration-based. A built-in or custom URL-backed framework participates
when its configured JSON or OWL path exists. URL-only frameworks without a
local file are excluded, including when named explicitly by a target, so lookup
and semantic lookup never trigger an ontology download.

Each ontology term is one chunk containing its framework ID, title, synonyms,
complete description, ID, accession, and IRI. The default
`GeminiEmbeddingProvider` calls Vertex AI through the Google Gen AI SDK with
model `gemini-embedding-001`, 768 dimensions,
`RETRIEVAL_DOCUMENT` for chunks, and `RETRIEVAL_QUERY` for queries. Document
requests are batched to at most 250 texts.
All batches use the same provider model and dimensionality and therefore occupy
the same vector space. Building one partition still holds that framework's
USearch vectors in process memory; it does not load the source JSON document.
Query-time reuse opens each persisted partition with `Index.view(...)`, so it is
memory-mapped rather than fully loaded. Partitions are not merged or sharded.

Semantic partitions and their SQLite mappings are guarded by a file lock.
Manifests bind the index to source freshness, embedding model/dimensions, chunk
schema, index path, and term count. A stale or missing manifest triggers a
rebuild; a new process can reuse a current on-disk partition without re-embedding
documents.

The shared schema also stores framework metadata, term payloads, exact lookup
entries, FTS rows, persistent hierarchy edges and completion markers,
controlled fields, external response cache rows, semantic manifests, and
vector-to-term mappings. Framework replacement transactionally cascades stale
hierarchy rows and causes lazy reconstruction. WAL mode and a busy timeout
support concurrent readers.

`build_ontology_cache --rag-index` first materializes framework JSON and
synchronizes SQLite, then builds semantic partitions for successful frameworks.
Its JSON manifest records per-framework semantic success or failure. Without
the flag, cache building does not call the embedding API.

### External calls

- Ontology downloads: `requests.get(...)` under `RequestPolicy`.
- OLS: OLS4 ontology metadata, search, and term endpoints under the same retry
  and response-cache policy.
- Embeddings: `google.genai.Client(...).models.embed_content(...)`.
- Structured judgements and assignments:
  `GeminiEnterprisePlatform.generate_response(...)` through the LLM facade.
<a id="reviewer-workflow"></a>
## Reviewer Workflow

`review_relevancy()` supports two strategies. `direct` is the default and makes
one model call over the complete publication. Its prompt appends labeled
`Theme`, `Title`, `Publication Text`, `Metadata`, and deduplicated `Accessions`
blocks. Metadata may contain an accession-keyed compact MINiML context when it
was collected before review; the prompt forbids transferring that evidence to
another accession or using remembered accession knowledge.
`evidence_then_judgement` retains two legacy model calls:

1. `extract_evidence()` reads `prompts/evidence_extraction.md`, then appends
   labeled `Theme`, `Title`, `Publication Text`, and `Metadata` blocks.
2. `judge_evidence()` reads `prompts/judge_evidence.md`, then appends labeled
   `Theme`, `Title`, and `Evidences` blocks.

Direct review requires one assessment for every supplied accession. Each
assessment contains `human_samples`, `transcriptomics_assay`,
`established_fibrosis`, and `accession_linkage` criterion objects with a
`meets`, `fails`, or `uncertain` status and supporting evidence. Normalization
drops unknown/duplicate assessments, supplies uncertain entries for missing
accessions, and derives the accession decisions, publication judgement,
confidence, and removal list. The legacy strategy continues to return its
model-authored flat decision and stores its evidence object under `evidences`.
Direct review revision 2 evaluates all four criteria independently, requires
absent or unmapped accession linkage to remain uncertain, and reserves linkage
failure for an explicitly different or ineligible cohort. Any failed criterion
at low overall assessment confidence is normalized to an uncertain accession
decision; only medium- or high-confidence failures produce exclusions. New
direct outputs carry `review_revision=2` so selectively rerun checkpoints can
be distinguished from earlier schema-compatible direct results.
Direct output has this shape:

```python
{
    "judgement": "relevant",
    "reasoning": "...",
    "confidence": "high",
    "accessions_to_remove": [],
    "accession_assessments": [
        {
            "accession": "GSE1",
            "human_samples": {"status": "meets", "evidence": "..."},
            "transcriptomics_assay": {"status": "meets", "evidence": "..."},
            "established_fibrosis": {"status": "meets", "evidence": "..."},
            "accession_linkage": {"status": "meets", "evidence": "..."},
            "confidence": "high",
            "reason": "...",
            "decision": "qualifies",
        }
    ],
    "strategy": "direct",
    "review_revision": 2,
}
```

Prompt values that are dictionaries or lists are serialized as sorted,
indented JSON. `None` prompt values become empty strings and all other values
are converted with `str(...)`.

All model calls pass `response_mime_type="application/json"` and a response
schema. The direct schema requires `accession_assessments`, enumerates criterion
statuses and confidence levels, and does not ask the model for a publication
verdict or removal list. The legacy evidence schema asks for an object with a
required `evidences` array, while its decision schema retains `judgement`,
`reasoning`, `confidence`, and `accessions_to_remove`.

<a id="code-flow"></a>
## Code Flow

Major orchestration flow:

1. CLI users call `cli_query_generator`, `cli_thematic_reviewer`, or
   `cli_ontology_harmonizer`. The
   CLI helpers read direct or UTF-8 file inputs, parse JSON inputs where the
   exposed curator method expects structured data, configure stderr logging
   from `--verbosity`, and write pretty JSON to stdout or `--out`.
2. `QueryGenerator.generate_queries()` validates its inputs, requests topical
   query details once, validates parsed JSON, and adds the dataset-link filter.
3. `review_relevancy()` either judges the complete publication directly once,
   or calls `extract_evidence(...)` followed by `judge_evidence(...)` for the
   legacy strategy.
4. Each reviewer primitive loads its packaged Markdown prompt, appends labeled
   input blocks, then calls `self._llm().generate_response(...)` with a JSON
   response schema.
5. `LLM.generate_response(...)` delegates to the configured platform. Claude
   model names are routed to `ClaudeVertexPlatform` when the default platform is
   Gemini.
6. Provider adapters construct SDK-specific requests, call the injected or
   lazily created client, and normalize the provider response to a raw text
   string.
7. Curator methods that request JSON parse dict/list or JSON text responses
   before returning.

The CLI configures standard-library logging to stderr. Curator workflows emit
INFO logs for orchestration boundaries and DEBUG logs for detailed internal
choices. Provider exceptions are not wrapped; they propagate to callers.

`OntologyHarmonizer.harmonize(...)` normalizes target input, then runs the fixed
local exact/FTS, local semantic, and OLS sequence. A successful earlier stage
skips later term searches. After selecting and promoting a term label, it calls
`harmonize_field(...)`; identifier enrichment cannot replace the judged identity.
`harmonize_miniml_json(...)` additionally derives the compact metadata context
before delegation, so ontology prompts receive relevant sample values without
serializing the full MINiML document.

<a id="method-orchestrator-pseudocode"></a>
## Method Orchestrator Pseudocode

This section traces the main classes and methods by call flow. Names here match
the implementation so an agent can jump directly from a pseudocode step to the
corresponding method.

### `QueryGenerator`

```python
def generate_queries(theme, max_queries=3):
    validate non-empty theme and max_queries in 1..3
    response = lazy_llm.generate_response(
        packaged prompt plus theme and maximum,
        JSON schema for details and strategy_summary,
    )
    parsed = parse_json_response(response)
    validate one-to-max unique topical clauses and non-empty purposes
    reject model-supplied HAS_DATA or HAS_LABSLINKS filters
    final details = add "(HAS_DATA:y OR HAS_LABSLINKS:y)" to each clause
    return queries derived from final details plus strategy_summary
```

Internal calls are `_prompt(...)`, `_response_schema(...)`, `_llm()`,
`parse_json_response(...)`, and `_validated_response(...)`. The only external
call is the configured LLM provider; Europe PMC is not called.

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

Role: fixed local exact/FTS → local semantic → OLS term harmonization followed
by label promotion and field harmonization.

```python
class OntologyHarmonizer:
    WORKFLOW = "local_rag_ols"

    def harmonize(
        publication_context=None,
        metadata_context=None,
        harmonization_targets=None,
        target=None,
        ontostore=None,
        target_paths=None,
        lookup_llm_judge=True,
        search_llm_judge=True,
        llm=True,
    ):
        store = effective OntoStore
        targets = normalize target or target list
        for target in targets:
            normalize pre_hz values into working hz_field and hz_label

            match = lookup_label(
                target,
                publication_context,
                metadata_context,
                store,
                lookup_llm_judge=lookup_llm_judge and llm,
            )
            if target was terminally skipped:
                continue

            if not match and llm:
                match = lookup_rag_label(
                    target,
                    publication_context,
                    metadata_context,
                    store,
                    lookup_llm_judge=lookup_llm_judge,
                )
            if target was terminally skipped:
                continue

            if not match:
                clear stale ontology match state
                ols = harmonize_label(
                    target,
                    publication_context,
                    metadata_context,
                    store,
                    search_llm_judge=search_llm_judge and llm,
                )
                if ols matched:
                    enrich the selected identity from local exact lookup
                if ols terminally skipped:
                    continue

            promote selected ontology title to hz_label
            harmonize_field(
                target,
                publication_context,
                metadata_context,
                store,
                llm=llm,
            )

        return wrapper with workflow="local_rag_ols"

    def lookup_label(...):
        search each locally cached candidate framework with lookup_with_metadata
        prefer exact hits; otherwise use FTS hits and retain FTS ranking
        if no hits:
            return False
        if FTS and judging disabled:
            retain candidates and return False
        selected = _select_lookup_hit(source="local")
        on selection, set ontology_id, ontology_lookup, hits, and match=True
        return selected or False

    def lookup_rag_label(...):
        result = store.lookup_rag_many(
            hz_label,
            cached_frameworks,
            top_k=10,
            parent_depth=2 if rag_hierarchy else 0,
            child_depth=1 if rag_hierarchy else 0,
        )
        preserve result.errors and isolate failed framework partitions
        for each framework, filter hits below its threshold (default 0.5)
        dedupe within each framework and reserve its best two qualifying hits
        fill remaining seats to 10 globally; expand if reservations exceed 10
        if rag_hierarchy:
            choose one best qualifying relative per ontology/direction/depth
            append relatives with score, relation, depth, and seed provenance
        write balanced hits and effective thresholds to ontology_rag trace
        if no candidates or judging disabled:
            return False
        selected = _select_lookup_hit(source="rag")
        on selection, set ontology lookup state and RAG status="matched"
        on no_match, set RAG status="no_match" and return False
        on false, mark target skipped and return False

    def _select_lookup_hit(target, hits, source, lookup_llm_judge):
        if judging disabled:
            return hits[0]
        judgement = judge_lookup(compact target and stage-specific candidate limit)
        append source-tagged judgement to ontology_lookup_judgements
        if decision == "no_match":
            return False
        if decision == "false":
            mark target terminally skipped at local or RAG judge stage
            return False
        return supplied hit whose id equals decision, else raise ValueError

    def harmonize_label(...):
        return OlsStrategyHandler(search_judge=judge_search_results).handle(...)

    def harmonize_field(...):
        lookup = store.lookup_fields(hz_field)
        if lookup:
            replace hz_field with canonical field and return lookup
        if llm is disabled:
            return False
        return assign_field(
            semantic target containing current hz_label and original pre_hz_label
        )

    def harmonize_miniml_json(...):
        discover paths when omitted
        extract and optionally dedupe targets
        create compact metadata_context
        result = harmonize(...)
        result["miniml_json"] = apply_targets(input object, result targets)
        return result
```

```python
class OlsStrategyHandler:
    def handle(target, publication_context, metadata_context, ontostore):
        hits = OLS search for current hz_label
        if judging enabled and hits:
            judgement = judge top 10 candidates
            if judgement selects supplied id/accession/IRI:
                selected = candidate
            elif judgement == "no_match":
                return not_harmonized result
            elif judgement == "false":
                mark target terminally skipped
                return skipped result
            else:
                fail closed
        elif hits:
            selected = hits[0]
        else:
            return not_harmonized result

        require complete OLS framework metadata
        configure selected framework locally
        set target ontology state from selected hit
        store result at ontology_ols_result with source="ols"
        return matched result
```

The OLS handler does not use grounded web search and does not perform a
restricted/unrestricted two-stage search. Search-judge prompts receive a neutral
candidate list and no search-stage literal.

`apply_targets(...)` resolves each occurrence JSON pointer, writes harmonized
scalar siblings, tag/value rows, or container lists, and copies optional term
and ontology IDs. It ignores skipped targets and malformed paths.
### `OntoStore`

Role: ontology framework/configuration store, SQLite lookup engine, persistent
field registry, and external-response cache.

```python
class OntoStore:
    DEFAULT_ONTOLOGY_FRAMEWORKS = {...}
    DEFAULT_STORAGE_DIR = package_dir / "ontology_frameworks"

    def __init__(ontology_frameworks=None, fields=None, storage_dir=None,
                 sqlite_path=None, request_policy=None):
        self.storage_dir = DEFAULT_STORAGE_DIR if storage_dir is None else Path(storage_dir)
        self.sqlite_path = sqlite_path or self.storage_dir / "sqlite" / "ontologies.sqlite3"
        self.ontology_frameworks = self._normalize_frameworks(
            DEFAULT_ONTOLOGY_FRAMEWORKS plus ontology_frameworks
        )
        self.request_policy = request_policy or RequestPolicy()
        initialize or migrate SQLite schema
        self.fields = persisted fields plus normalized constructor fields

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
    return lookup_with_metadata(label, ontology_id)["hits"]

def lookup_with_metadata(label, ontology_id):
    index_framework(ontology_id)
    exact = lookup_exact(label, ontology_id, ensure_index=False)
    if exact:
        return {"match_type": "exact", "hits": exact, "ranking": []}
    ensure FTS rows exist for legacy indexes
    fts_hits, ranking = query FTS5 over labels, synonyms, descriptions, and identifiers
    return {"match_type": "fts" or "none", "hits": fts_hits, "ranking": ranking}

def lookup_rag(label, ontology_id, top_k=10):
    if framework has no cached local JSON or OWL source:
        return []
    index_path = build_rag_index(ontology_id)
    query = embedding_provider.embed_query(label)
    vector_ids, distances = USearch cosine top-k query
    join vector IDs through rag_term_map to canonical SQLite term payloads
    return payloads with ontology_id and rag_score=1-distance

def build_rag_index(ontology_id, force=False):
    require an existing local framework source; never download
    ensure canonical SQLite terms are current
    acquire framework/model-specific file lock
    reuse a current manifest and partition, otherwise batch-embed every term
    atomically replace the partition and transactionally replace its mappings
    return index path

def index_framework(ontology_id, force=False):
    transactionally add or refresh one stale JSON cache in SQLite

def remove_indexed_framework(ontology_id):
    remove one framework from SQLite while retaining OWL and JSON caches

def sync_sqlite(frameworks=None, force=False):
    index selected or all existing framework JSON caches and return counts

def add_field/update_field/remove_field/get_field/list_fields/set_field_review_status(...):
    validate metadata and aliases, persist registry rows, and refresh active fields

def get_cached_response/set_cached_response/clear_cached_responses(...):
    read or mutate normalized provider/operation/request cache entries with TTL

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
    response = request_with_retry(
        lambda: requests.get(url, timeout=self.request_policy.timeout_seconds),
        self.request_policy,
    )
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

- `requests.get(url, timeout=request_policy.timeout_seconds)`, wrapped by
  transient retry/backoff policy

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
        if generation_tools:
            generation_config["tools"] = generation_tools
        request = {
            "model": effective_model,
            "contents": prompt,
            "config": generation_config,
            **extra_options,
        }
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

Generation tools are nested under `config["tools"]`, matching the Google Gen AI
SDK `generate_content(model=..., contents=..., config=...)` signature. They are
not sent as an unsupported top-level request keyword. The provider-neutral
`{"type": "google_search"}` descriptor is translated at this adapter boundary
to the SDK's `{"google_search": {}}` tool shape.

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

### CLI Entry Points

Role: parse command-line input, dispatch to reviewer or ontology orchestrators,
and write JSON.

```python
def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbosity)
    direct/file inputs = input_value(...) or json_input(...)
    if thematic command:
        result = dispatch to review_relevancy/extract_evidence/judge_evidence
    if ontology command:
        policy = RequestPolicy(from timeout/retry/cache flags)
        store = OntoStore(from framework/field/storage flags, policy)
        result = dispatch to harmonize/harmonize_miniml_json
    write_json_output(result, args.out)
    return 0
```

Internal calls:

- `_build_parser()`
- `input_value(...)` for text inputs and `json_input(...)` for structured input.
- `ThematicReviewer` method selected by reviewer subcommand.
- `OntologyHarmonizer` method selected by ontology subcommand.
- `RequestPolicy(...)` and `OntoStore(...)` construction for ontology commands.

File-system calls:

- `Path(file).read_text(encoding="utf-8")` for input file options.
- `open(args.out, "w", encoding="utf-8")` when writing to an output file.

<a id="prompts"></a>
## Prompts

Each curator owns its packaged prompt files inside its own subpackage. The
thematic reviewer prompts live under
`src/agentic_curator/curators/thematic_reviewer/prompts/`.
Packaged prompt Markdown intentionally omits repository author headers so
authorship metadata is never sent as model context; repository tests exempt
prompt files from the header requirement and assert author text is absent.

- `evidence_extraction.md` instructs the model to extract direct or indirect
  evidence statements verbatim and return an evidence list.
- `judge_evidence.md` instructs the model to judge whether extracted evidence
  satisfies the theme criteria and return relevance, reasoning, and confidence.
- `theme.md` is a fibrosis theme example used by local development fixtures and
  manual CLI runs. It is packaged but not loaded automatically by
  `ThematicReviewer`.

`query_generator/prompts/generate_queries.md` requests one to three
complementary Europe PMC topical clauses, short per-query purposes, and a
strategy summary. It forbids dataset-link filters because the curator adds them
deterministically.

The active ontology harmonizer prompt files are:

- `assign_field.md` instructs the model to choose or create a normalized field
  key and return `decision`, `confidence`, `reason`, and `new_field`.
- `judge_lookup.md` instructs the model to choose the best local or semantic
  lookup hit ID, return `no_match`, or terminally reject with `false`.
- `judge_search.md` instructs the model to select one supplied OLS candidate or
  return `no_match` or `false` using the supplied target context.

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
The facade emits safe structured telemetry: DEBUG logs call start with
platform/model, prompt character count, tool count, and structured-output flag;
INFO logs completion with response character count, citation/tool-call counts,
and elapsed time; failures log platform/model/duration with a traceback. Prompt
text, response bodies, contexts, credentials, and request headers are never
logged. Curators add query-length, evidence-count, judgement, target-match, and
ontology-cache framework progress statistics.

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

The installed console commands are `build_ontology_cache`,
`cli_query_generator`, `cli_thematic_reviewer`, and
`cli_ontology_harmonizer`. The modules can also be run directly:

```bash
.env/bin/python -m agentic_curator.curators.ontology_harmonizer.cache_builder --help
.env/bin/python -m agentic_curator.cli.cli_thematic_reviewer --help
.env/bin/python -m agentic_curator.cli.cli_ontology_harmonizer --help
.env/bin/python -m agentic_curator.cli.cli_query_generator --help
```

The curator CLI commands accept `--verbosity {quiet,error,warning,info,debug}`.
Logs are written to stderr and JSON results stay on stdout unless `--out` is
supplied.

`cli_query_generator` accepts `--theme` or `--theme-file`, `--max-queries`
from one to three, and `--out`. Theme files take precedence over direct text.

`build_ontology_cache` prepares OWL/JSON caches for configured built-in
ontology frameworks. Options include `--timeout`, `--out-dir`, `--out-prefix`,
`--max-workers`, repeated `--force-framework FRAMEWORK_ID`, and `--rag-index`
to build persistent Gemini/USearch semantic partitions after SQLite sync.

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
- `--metadata-context` or `--metadata-context-file` for direct `harmonize`
- `--target` or `--target-file`
- `--harmonization-targets` or `--harmonization-targets-file`
- `--miniml-json` or `--miniml-json-file`
- `--target-paths` or `--target-paths-file`
- `--lookup-llm-judge` or `--no-lookup-llm-judge` (enabled by default)
- `--search-llm-judge` or `--no-search-llm-judge` (enabled by default)
- `--llm` or `--no-llm`
- `--ontology-frameworks` or `--ontology-frameworks-file`
- `--fields` or `--fields-file`
- `--storage-dir`
- `--request-timeout`, `--request-max-attempts`, and `--request-backoff`
- `--cache-ttl-seconds` and `--force-refresh`
- `--rag-hierarchy` to opt into cached parent/child expansion
- `--rag-parent-depth`, `--rag-child-depth`, and
  `--rag-hierarchy-threshold-offset` to tune an enabled expansion; supplying
  any tuning option without `--rag-hierarchy` is a parser error

By default the CLI writes pretty JSON to stdout. When `--out` is provided, it
writes pretty JSON to that file and keeps stdout quiet.

<a id="tests"></a>
## Tests

The test suite is pytest-based and avoids live provider calls by using fake
clients and fake LLM objects.

Test coverage includes:

- query generator exports, prompt/schema construction, one-call generation,
  bounded and unique details, deterministic dataset filters, lazy LLM creation,
  malformed responses, and CLI direct/file inputs
- reviewer instantiation, public exports, missing legacy module, prompt
  construction, schema construction, and two-call ordering
- ontology harmonizer imports, root exports, fixed local-semantic-OLS routing,
  local and OLS `no_match`/`false` behavior, MINiML target application,
  persistent semantic index build/reuse, threshold filtering, two-per-ontology
  RAG balancing, optional hierarchy edge backfill/traversal, cycle handling,
  dynamic semantic judge limits, and `OntoStore`
  defaults/overrides/download/get/exact/FTS/RAG behavior
- ontology cache builder framework ordering, default worker count, threaded
  scheduling, force flags, failure collection, SQLite/RAG synchronization,
  manifest/log writing, and console script metadata
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
.env/bin/python -m agentic_curator.curators.ontology_harmonizer.cache_builder --help
.env/bin/python -m agentic_curator.cli.cli_thematic_reviewer --help
.env/bin/python -m agentic_curator.cli.cli_ontology_harmonizer --help
```

Build ontology OWL/JSON caches with concurrent framework jobs:

```bash
.env/bin/python -m agentic_curator.curators.ontology_harmonizer.cache_builder \
  --max-workers 4 \
  --timeout 2700
```

Add `--rag-index` to embed cached ontology terms and persist semantic indexes.

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
