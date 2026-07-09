from __future__ import annotations

import json
from typing import Any


def parse_json_response(response: Any) -> Any:
    """Return structured JSON from an LLM response."""
    if isinstance(response, (dict, list)):
        return response

    if isinstance(response, str):
        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response was not valid JSON.") from exc

    raise ValueError("LLM response must be JSON text, an object, or an array.")
