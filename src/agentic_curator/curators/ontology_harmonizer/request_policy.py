# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Any, Callable


@dataclass(frozen=True)
class RequestPolicy:
    """Shared timeout, retry, and external-response cache policy."""

    timeout_seconds: float = 30
    max_attempts: int = 3
    backoff_base_seconds: float = 1
    cache_ttl_seconds: int = 7 * 24 * 60 * 60
    force_refresh: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.backoff_base_seconds < 0:
            raise ValueError("backoff_base_seconds cannot be negative.")
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative.")


def is_transient_error(exc: Exception) -> bool:
    """Return whether an external request error is suitable for retry."""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return True
    message = str(exc).lower()
    markers = ("timeout", "temporar", "connection", "429", "500", "502", "503", "504", "resource_exhausted")
    return any(marker in message for marker in markers)


def request_with_retry(
    operation: Callable[[], Any],
    policy: RequestPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> tuple[Any, dict[str, Any]]:
    """Execute an external operation and return its request trace."""
    started = time.monotonic()
    errors: list[str] = []
    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = operation()
            return result, {
                "status": "success",
                "attempts": attempt,
                "errors": errors,
                "elapsed_seconds": time.monotonic() - started,
            }
        except Exception as exc:
            errors.append(str(exc))
            if attempt >= policy.max_attempts or not is_transient_error(exc):
                setattr(exc, "request_trace", {
                    "status": "failed",
                    "attempts": attempt,
                    "errors": errors,
                    "elapsed_seconds": time.monotonic() - started,
                })
                raise
            delay = policy.backoff_base_seconds * (2 ** (attempt - 1))
            sleep(delay * (0.5 + random_value() * 0.5))

    raise RuntimeError("unreachable")
