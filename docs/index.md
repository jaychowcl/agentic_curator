# Codebase Documentation Index

This index maps major topics to anchored sections in `docs/codebase.md`.
Agents should use this file first, then retrieve only the sections relevant to
the task.

## Section Index

| ID | Section | Description | Keywords |
| --- | --- | --- | --- |
| `project-purpose-and-layout` | [Project Purpose And Layout](codebase.md#project-purpose-and-layout) | Repository purpose, tracked layout, and ignored local artifacts. | layout, purpose, files, ignored, .dev, .env, .vscode |
| `runtime-and-packaging` | [Runtime And Packaging](codebase.md#runtime-and-packaging) | Packaging metadata, dependencies, console script, package data, and editable install. | pyproject, setuptools, dependencies, google-genai, anthropic, requests, pytest, package-data |
| `public-api` | [Public API](codebase.md#public-api) | Main exported API, lazy LLM creation, raw generated-text contract, and legacy import status. | ThematicReviewer, curators, review_relevancy, extract_evidence, judge_evidence, raw text, legacy module |
| `ontology-harmonizer` | [Ontology Harmonizer](codebase.md#ontology-harmonizer) | Ontology harmonizer curator, metadata-only public harmonize method, OntoStore downloads, built-in titled and described ontology frameworks, configurable private target extraction, path specs, and extraction modes. | OntologyHarmonizer, OntoStore, title, description, OLS4, versionIri, stable current URL, EFO, efo, efo.owl, MONDO, mondo, UBERON, HP, hp, CL, ChEBI, PATO, OBI, SNOMED, NCIT, NCBITaxon, ncbitaxon, 2026-06-02, download, add_url, add_urls, version, ontology_frameworks, ontology_frameworks directory, requests, harmonize, publication_text, metadata, target_paths, DEFAULT_TARGET_PATHS, start_paths, path specs, scalar, tag_value, container_value, field_path, label_path, JSON Pointer, curator |
| `reviewer-workflow` | [Reviewer Workflow](codebase.md#reviewer-workflow) | Two-step evidence extraction and evidence judging flow, prompt labels, JSON formatting, response schemas. | workflow, evidence, judgement, response_schema, prompt, metadata, JSON |
| `code-flow` | [Code Flow](codebase.md#code-flow) | End-to-end flow across CLI, reviewer orchestrator, primitives, LLM routing, provider adapters, and response parsing. | code flow, orchestrator, primitives, CLI, ThematicReviewer, LLM, provider adapter, routing |
| `method-orchestrator-pseudocode` | [Method Orchestrator Pseudocode](codebase.md#method-orchestrator-pseudocode) | Method-by-method pseudocode for main classes, orchestrators, internal calls, and external API calls. | pseudocode, methods, orchestrators, classes, call graph, internal methods, external APIs, ThematicReviewer, OntologyHarmonizer, OntoStore, LLM, GeminiEnterprisePlatform, ClaudeVertexPlatform, CLI |
| `prompts` | [Prompts](codebase.md#prompts) | Per-curator packaged Markdown prompts, evidence/judge prompt roles, and local fibrosis theme example. | prompts, curator package, evidence_extraction, judge_evidence, theme.md, fibrosis |
| `llm-wrapper` | [LLM Wrapper](codebase.md#llm-wrapper) | Provider routing facade, supported platform names, and Claude model auto-routing behavior. | LLM, routing, gemini_enterprise, claude_vertex, claude model, ValueError |
| `gemini-enterprise-platform` | [Gemini Enterprise Platform](codebase.md#gemini-enterprise-platform) | Google Gen AI client creation, request shape, config/tool merging, and response parsing. | GeminiEnterprisePlatform, google.genai, generate_content, vertexai, enterprise, tools, candidate text |
| `claude-vertex-platform` | [Claude Vertex Platform](codebase.md#claude-vertex-platform) | Anthropic Vertex client creation, Messages request shape, config mapping, schema normalization, and parsing. | ClaudeVertexPlatform, AnthropicVertex, messages.create, output_config, json_schema, max_tokens |
| `cli` | [CLI](codebase.md#cli) | Command-line inputs, UTF-8 file reads, metadata-as-string behavior, file precedence, stdout/outfile behavior. | cli, cli_thematic_reviewer, argparse, publication-text-file, metadata-file, UTF-8, out |
| `tests` | [Tests](codebase.md#tests) | Pytest coverage, fake-client strategy, adapter behavior, and no-live-provider baseline. | tests, pytest, fake clients, wrapper tests, CLI tests, response adapter, schema normalization |
| `local-development` | [Local Development](codebase.md#local-development) | Local ignored fixtures, VS Code conventions, status checks. | local, .dev, .env, .vscode, fixtures, git status |
| `common-commands` | [Common Commands](codebase.md#common-commands) | Frequently used install, test, CLI, and fixture commands. | commands, install, pytest, CLI, fixtures |

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
