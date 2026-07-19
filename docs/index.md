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

# Codebase Documentation Index

This index maps major topics to anchored sections in `docs/codebase.md`.
Agents should use this file first, then retrieve only the sections relevant to
the task.

## Section Index

| ID | Section | Description | Keywords |
| --- | --- | --- | --- |
| `project-purpose-and-layout` | [Project Purpose And Layout](codebase.md#project-purpose-and-layout) | Repository purpose, tracked layout, canonical authors-header policy, README citation, and ignored/external files. | layout, purpose, README, authors, author header, exactly one, Markdown prompt comment, linked affiliations, Please cite us using, software citation, LICENSE, external source, ignored, .dev, .env, .vscode |
| `runtime-and-packaging` | [Runtime And Packaging](codebase.md#runtime-and-packaging) | Packaging metadata, requirements file, dependencies, console scripts, package data, and editable install. | pyproject, requirements.txt, setuptools, dependencies, google-genai, anthropic, rdflib, requests, pytest, package-data, build_ontology_cache, cli_thematic_reviewer, cli_ontology_harmonizer |
| `public-api` | [Public API](codebase.md#public-api) | Main exported API, lazy LLM creation, parsed JSON curator responses, ontology helper exports, and legacy import status. | ThematicReviewer, 16384 output tokens, OntologyHarmonizer, build_miniml_metadata_context, curators, review_relevancy, extract_evidence, judge_evidence, parsed JSON, ontology_harmonizer, OntoStore, Owl2json, OlsClient, legacy module |
| `query-generator` | [Query Generator](codebase.md#query-generator) | Domain-neutral comprehensive concept-group generation, bounded structured output, dataset-link filters, validation, and ThematicAtlases handoff. | QueryGenerator, generate_queries, one comprehensive query, AND concept groups, OR synonyms, unbridgeable gap, Europe PMC, HAS_DATA, HAS_LABSLINKS, max_queries, strategy_summary |
| `ontology-harmonizer` | [Ontology Harmonizer](codebase.md#ontology-harmonizer) | Core compound-target checking and pruning, fixed local exact/FTS, semantic RAG, optional hierarchy expansion, preferred ontology judge bias, unrestricted OLS, label promotion, validated field assignment, independent stage controls, and MINiML application. | OntologyHarmonizer, OntoStore, preferred_ontology_ids, set_preferred_ontology_ids, harmonize, target_checker, prune, pruned_count, raw metadata, direct_lookup_judge, rag_lookup, rag_lookup_judge, ols_lookup, ols_lookup_judge, field_assignment_judge, controls, candidates_unjudged, local_rag_ols, metadata_context, lookup_label, lookup_rag_label, rag_hierarchy, harmonize_label, harmonize_field, assign_field, miniml_json, OLS4, unrestricted, no_match, false |
| `ontology-sqlite-index` | [Ontology SQLite And Semantic Index](codebase.md#ontology-harmonizer) | Bounded-memory OWL/JSON streaming, eager semantic cache preparation, exact/FTS5 SQLite lookup, indexed hierarchy-edge backfill, Gemini embeddings, sequential multi-framework USearch partitions, field registry, and caches. | SQLite, ijson, USearch, GeminiEmbeddingProvider, gemini-embedding-001, cache_all, semantic_frameworks, lookup_rag, lookup_rag_many, parent_depth, child_depth, subClassOf, term_hierarchy, parent lookup index, build_rag_index, memory map, cached URL framework, vector, semantic, FTS5, field registry |
| `ontology-search-judge` | [Ontology Judge Context](codebase.md#ontology-harmonizer) | Context contracts, preferred ontology candidate reservations and advisory bias, candidate ID/accession/IRI resolution, similarity thresholds, balanced semantic and optional hierarchy candidates, and decision semantics. | LLM context, preferred ontology, preferred_ontology_ids, fixed pool, round robin, calls per target, 0 to 4 calls, lookup judge, semantic judge, id, accession, IRI, RAG threshold, hierarchy threshold offset, rag_relation, rag_depth, rag_seed_id, two per ontology, balanced candidates, OLS judge, no_match, false, identifier enrichment |
| `reviewer-workflow` | [Reviewer Workflow](codebase.md#reviewer-workflow) | Direct whole-publication, criterion-based accession review, confidence-aware exclusions, revision markers, compact metadata context, and the legacy evidence-then-judgement strategy. | workflow, direct, review_revision, revision 2, low confidence uncertain, accession_assessments, human_samples, transcriptomics_assay, established_fibrosis, accession_linkage, derived judgement, compact MINiML, evidence_then_judgement, accessions_to_remove, response_schema, prompt, metadata, JSON |
| `code-flow` | [Code Flow](codebase.md#code-flow) | End-to-end flow across CLIs, reviewer and ontology orchestrators, conditional LLM calls, provider adapters, logging, and response parsing. | code flow, decision path, LLM call matrix, logical call, provider attempt, orchestrator, CLI, ThematicReviewer, OntologyHarmonizer, provider adapter, routing |
| `method-orchestrator-pseudocode` | [Method Orchestrator Pseudocode](codebase.md#method-orchestrator-pseudocode) | Current method-by-method pseudocode for main classes, exact/FTS and strategy orchestration, internal calls, and external APIs. | pseudocode, methods, orchestrators, classes, call graph, internal methods, external APIs, ThematicReviewer, OntologyHarmonizer, OntoStore, RequestPolicy, field registry, response cache, OLS, grounded search, LLM, GeminiEnterprisePlatform, ClaudeVertexPlatform, CLI |
| `prompts` | [Prompts](codebase.md#prompts) | Header-free packaged model prompts, evidence/judge roles, target checking, lookup judgement, field assignment, and local fibrosis theme example. | prompts, no author headers, model context, curator package, evidence_extraction, judge_evidence, target_checker, compound target, judge_lookup, assign_field, theme.md, fibrosis |
| `llm-wrapper` | [LLM Wrapper](codebase.md#llm-wrapper) | Provider routing, safe call telemetry, metadata responses, Claude auto-routing, and ADC troubleshooting. | LLM, logging, telemetry, elapsed time, response characters, no prompt bodies, routing, generate_response_with_metadata, citations, tool_calls, provider, gemini_enterprise, claude_vertex, ADC |
| `gemini-enterprise-platform` | [Gemini Enterprise Platform](codebase.md#gemini-enterprise-platform) | Google Gen AI client creation, request shape, config/tool merging, response parsing, citation extraction, and Google Search grounding metadata. | GeminiEnterprisePlatform, google.genai, generate_content, vertexai, enterprise, tools, google_search, candidate text, annotations, citations, steps, google_search_call, google_search_result |
| `claude-vertex-platform` | [Claude Vertex Platform](codebase.md#claude-vertex-platform) | Anthropic Vertex client creation, Messages request shape, config mapping, schema normalization, parsed text, and metadata response wrapper. | ClaudeVertexPlatform, AnthropicVertex, messages.create, output_config, json_schema, max_tokens, generate_response_with_metadata, raw_response, citations, tool_calls, provider |
| `cli` | [CLI](codebase.md#cli) | Command-line inputs, all subcommands/options, request policy controls, UTF-8/JSON files, precedence, logging, and output behavior. | cli, cli_thematic_reviewer, cli_ontology_harmonizer, build_ontology_cache, argparse, review, extract-evidence, judge-evidence, harmonize, harmonize-miniml-json, request-timeout, request-max-attempts, cache-ttl-seconds, force-refresh, verbosity, file precedence, UTF-8, JSON, out |
| `tests` | [Tests](codebase.md#tests) | Pytest coverage, fake-client strategy, adapter behavior, CLI/logging tests, repository metadata tests, and no-live-provider baseline. | tests, pytest, fake clients, wrapper tests, CLI tests, ontology CLI tests, logging tests, repository metadata, authors headers, response adapter, schema normalization |
| `local-development` | [Local Development](codebase.md#local-development) | Local ignored fixtures, VS Code conventions, status checks. | local, .dev, .env, .vscode, fixtures, git status |
| `common-commands` | [Common Commands](codebase.md#common-commands) | Frequently used install, requirements install, test, CLI, ontology cache builder, ontology CLI, and fixture commands. | commands, install, requirements.txt, pytest, CLI, build_ontology_cache, cache_builder, cli_thematic_reviewer, cli_ontology_harmonizer, fixtures |

## Retrieval Template

Use this self-contained Python template to retrieve relevant sections from
`docs/codebase.md` by matching query terms against the index rows above.

```python
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.md"
CODEBASE = ROOT / "docs" / "codebase.md"


def parse_index(index_text: str) -> list[dict[str, str]]:
    rows = []
    for line in index_text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 4:
            continue
        section_id = cells[0].strip("`")
        rows.append(
            {
                "id": section_id,
                "section": cells[1],
                "description": cells[2],
                "keywords": cells[3],
            }
        )
    return rows


def score_row(row: dict[str, str], query_terms: set[str]) -> int:
    haystack = " ".join(row.values()).lower()
    return sum(1 for term in query_terms if term in haystack)


def extract_section(codebase_text: str, section_id: str) -> str:
    anchor = f'<a id="{section_id}"></a>'
    start = codebase_text.find(anchor)
    if start == -1:
        raise ValueError(f"Missing section anchor: {section_id}")

    next_anchor = codebase_text.find('<a id="', start + len(anchor))
    if next_anchor == -1:
        return codebase_text[start:].strip()
    return codebase_text[start:next_anchor].strip()


def retrieve_sections(query: str, limit: int = 3) -> list[str]:
    query_terms = set(re.findall(r"[a-zA-Z0-9_.-]+", query.lower()))
    rows = parse_index(INDEX.read_text(encoding="utf-8"))
    ranked = sorted(
        ((score_row(row, query_terms), row) for row in rows),
        key=lambda item: item[0],
        reverse=True,
    )

    codebase_text = CODEBASE.read_text(encoding="utf-8")
    selected = [row for score, row in ranked if score > 0][:limit]
    if not selected:
        selected = rows[:1]

    return [extract_section(codebase_text, row["id"]) for row in selected]


if __name__ == "__main__":
    for section in retrieve_sections("ThematicReviewer response schema workflow"):
        print(section)
        print("\n---\n")
```

## Maintenance Notes

- Keep section IDs in this index synchronized with `<a id="..."></a>` anchors in
  `docs/codebase.md`.
- Prefer adding a new row when a new subsystem appears rather than overloading an
  existing section with unrelated keywords.
- Keep the retrieval template dependency-free so it can run in constrained agent
  environments.
