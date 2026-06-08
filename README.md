# agentic-curator

`agentic-curator` provides a small LLM-assisted reviewer for assessing whether
life science publications are relevant to a thematic curation target.

## Install

```bash
python -m pip install -e ".[dev]"
```

The runtime package supports Google Gen AI Gemini generation and Anthropic
Claude on Vertex AI. Tests use fake clients and do not require live model calls.

## Python API

```python
from agentic_curator import ThematicReviewer

reviewer = ThematicReviewer()
result = reviewer.review_relevancy(
    publication_text="Full publication text",
    theme="fibrosis",
    metadata={"organism": "human", "tissue": "lung"},
    title="Fibrosis atlas publication",
)
```

`review_relevancy()` returns a dictionary with raw generated text under
`evidences` and `judgement`. The reviewer requests JSON responses from the
configured model but intentionally leaves parsing and validation to callers.

## CLI

```bash
cli_thematic_reviewer \
  --publication-text-file publication.txt \
  --theme-file theme.txt \
  --metadata-file metadata.json \
  --title "Publication title" \
  --out decision.json
```

The CLI accepts direct values or `*-file` inputs. File inputs take precedence
over direct values, and metadata is passed through as text.
