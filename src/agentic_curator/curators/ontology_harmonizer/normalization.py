from __future__ import annotations

import re
import string
from typing import Any


EDGE_PUNCTUATION = string.punctuation


def harmonize_key(value: Any) -> str:
    normalized = str(value).lower().strip().strip(EDGE_PUNCTUATION)
    return re.sub(r"\s+", "_", normalized)
