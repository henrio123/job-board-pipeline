"""Shared source-adapter contract and constants.

An adapter is any callable ``fetch(token: str, company: str) -> list[dict]``
returning job dicts in the canonical pre-normalization shape:
    {company, title, location, url, description, source, id}

Adapters perform network IO and may raise requests.RequestException; the
orchestrator (pipeline.fetch_jobs) is responsible for per-source error handling,
pacing, and logging. Adapters do NOT log, sleep, or swallow errors themselves.
"""

from __future__ import annotations

from typing import Any, Protocol

REQUEST_TIMEOUT = 20  # seconds, per board API call


class SourceAdapter(Protocol):
    def __call__(self, token: str, company: str) -> list[dict[str, Any]]: ...
