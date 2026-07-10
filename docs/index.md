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
| `project-purpose-and-layout` | [Project Purpose And Layout](codebase.md#project-purpose-and-layout) | Repository purpose, tracked layout, authors header policy, citation location, and ignored local artifacts. | layout, purpose, files, authors, author header, citation, README Authors, skipped prompts, LICENSE, ignored, .dev, .env, .vscode |
| `runtime-and-packaging` | [Runtime And Packaging](codebase.md#runtime-and-packaging) | Packaging metadata, requirements file, dependencies, console scripts, package data, and editable install. | pyproject, requirements.txt, setuptools, dependencies, google-genai, anthropic, rdflib, requests, pytest, package-data, build_ontology_cache, cli_thematic_reviewer, cli_ontology_harmonizer |
| `public-api` | [Public API](codebase.md#public-api) | Main exported API, lazy LLM creation, parsed JSON curator responses, ontology helper exports, and legacy import status. | ThematicReviewer, OntologyHarmonizer, curators, review_relevancy, extract_evidence, judge_evidence, parsed JSON, parse_json_response, ontology_harmonizer, OntoStore, Owl2json, OlsClient, NullSearchClient, GeminiGroundedSearchClient, WebsearchStrategyHandler, RagStrategyHandler, legacy module |
| `ontology-harmonizer` | [Ontology Harmonizer](codebase.md#ontology-harmonizer) | Ontology harmonizer curator, public harmonize method, OntoStore lookup/downloads, cache builder, LLM framework and field assignment, sanitized LLM target prompt context, always-run field harmonization, post-assignment strategy handlers, post-strategy lookup enrichment, HarmonizationTargetExtractor target extraction, target application, Owl2json RDF/XML parser, built-in titled and described ontology frameworks, path specs, and extraction modes. | OntologyHarmonizer, HarmonizationTargetExtractor, target_extractor, OntoStore, lookup, lookup_label, lookup_fields, lookup_llm_judge, lookup_llm_threshold, cache_builder, build_ontology_cache, ThreadPoolExecutor, max_workers, force_framework, manifest, sanitized target prompt context, prompt pruning, _target_prompt_context, _assignment_target_prompt_context, _field_target_prompt_context, _lookup_target_prompt_context, always field harmonization, field harmonization after lookup success, post-strategy lookup, _lookup_harmonized_label, ontology_lookup_hits, ontology_lookup_judgement, judge_lookup, assign_field, harmonize_field, field_lookup, field_assignment, fields, assign_onto_framework, sanitized framework prompt metadata, harmonize_label, apply_targets, miniml_json, direct hz fields, tag value rows, container sibling list, scalar collision suffix, hz_field, hz_label, hz_<field>_id, hz_<field>_onto, collision, WebsearchStrategyHandler, OlsClient, NullSearchClient, GeminiGroundedSearchClient, google_search, Gemini grounding, web_search_error, request_budget, last_response, last_error, search_client, OLS4 search API, restricted OLS search, unrestricted OLS search, RagStrategyHandler, websearch, rag, ontology_strategy_result, ontology_framework_assignment, decision, confidence, reason, new_field, LLM, llm flag, assign_onto_framework.md, assign_field.md, judge_lookup.md, harmonize_key, normalized keys, ontology_lookup, ontology_match, ontology_id, ontology_ids, ontology id, ontology.id, Owl2json, Owl2jsonParseError, owl2json, rdflib, RDF/XML, owl:Class, term JSON, terms label id accession iri indexes, jsons directory, force, reparse, redownload, accession, synonyms, xrefs, title, description, OLS4, versionIri, stable current URL, EFO, efo, efo.owl, MONDO, mondo, UBERON, HP, hp, CL, ChEBI, PATO, OBI, SNOMED, NCIT, NCBITaxon, ncbitaxon, 2026-06-02, download, add_url, add_urls, configure_framework, owl_path, json_path, remove, local path, path-backed framework, version, ontostore, ontostore injection, ontology_frameworks, ontology_frameworks directory, requests, harmonize, target, single target, strategy, publication_text, metadata, target_paths, DEFAULT_TARGET_PATHS, start_paths, path specs, scalar, tag_value, container_value, field_path, label_path, JSON Pointer, curator |
| `reviewer-workflow` | [Reviewer Workflow](codebase.md#reviewer-workflow) | Two-step evidence extraction and evidence judging flow, prompt labels, JSON formatting, response schemas. | workflow, evidence, judgement, response_schema, prompt, metadata, JSON |
| `code-flow` | [Code Flow](codebase.md#code-flow) | End-to-end flow across CLIs, reviewer and ontology orchestrators, primitives, LLM routing, provider adapters, logging, and response parsing. | code flow, orchestrator, primitives, CLI, cli_thematic_reviewer, cli_ontology_harmonizer, verbosity, logging, ThematicReviewer, OntologyHarmonizer, LLM, provider adapter, routing |
| `method-orchestrator-pseudocode` | [Method Orchestrator Pseudocode](codebase.md#method-orchestrator-pseudocode) | Method-by-method pseudocode for main classes, orchestrators, internal calls, and external API calls. | pseudocode, methods, orchestrators, classes, call graph, internal methods, external APIs, ThematicReviewer, OntologyHarmonizer, OntoStore, LLM, GeminiEnterprisePlatform, ClaudeVertexPlatform, CLI |
| `prompts` | [Prompts](codebase.md#prompts) | Per-curator packaged Markdown prompts, evidence/judge prompt roles, ontology framework, lookup judgement, field assignment prompts, and local fibrosis theme example. | prompts, curator package, evidence_extraction, judge_evidence, assign_onto_framework, judge_lookup, assign_field, theme.md, fibrosis |
| `llm-wrapper` | [LLM Wrapper](codebase.md#llm-wrapper) | Provider routing facade, supported platform names, metadata responses, Claude model auto-routing behavior, and ADC token-refresh troubleshooting. | LLM, routing, generate_response, generate_response_with_metadata, metadata, raw_response, citations, tool_calls, provider, gemini_enterprise, claude_vertex, claude model, ADC, google.auth, oauth2.googleapis.com, token refresh, sandbox DNS, ValueError |
| `gemini-enterprise-platform` | [Gemini Enterprise Platform](codebase.md#gemini-enterprise-platform) | Google Gen AI client creation, request shape, config/tool merging, response parsing, citation extraction, and Google Search grounding metadata. | GeminiEnterprisePlatform, google.genai, generate_content, vertexai, enterprise, tools, google_search, candidate text, annotations, citations, steps, google_search_call, google_search_result |
| `claude-vertex-platform` | [Claude Vertex Platform](codebase.md#claude-vertex-platform) | Anthropic Vertex client creation, Messages request shape, config mapping, schema normalization, parsed text, and metadata response wrapper. | ClaudeVertexPlatform, AnthropicVertex, messages.create, output_config, json_schema, max_tokens, generate_response_with_metadata, raw_response, citations, tool_calls, provider |
| `cli` | [CLI](codebase.md#cli) | Command-line inputs, subcommands, UTF-8 file reads, JSON inputs, verbosity logging, file precedence, stdout/outfile behavior. | cli, cli_thematic_reviewer, cli_ontology_harmonizer, argparse, review, extract-evidence, judge-evidence, harmonize, harmonize-miniml-json, verbosity, logging, publication-text-file, metadata-file, evidences-file, target-file, harmonization-targets-file, miniml-json-file, target-paths-file, ontology-frameworks-file, fields-file, UTF-8, JSON, out |
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
