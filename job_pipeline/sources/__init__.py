"""Source adapters: per-board fetch functions and a type -> adapter registry.

Each adapter exposes ``fetch(token, company) -> list[dict]`` returning job dicts
in the canonical pre-normalization shape used by pipeline.py:
    {company, title, location, url, description, source, id}

It may raise requests.RequestException, which the orchestrator handles.
"""

from __future__ import annotations

from . import greenhouse, lever

# type string (as used in sources.yaml) -> fetch callable
ADAPTERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
}

__all__ = ["ADAPTERS", "greenhouse", "lever"]
