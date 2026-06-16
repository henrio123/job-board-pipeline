"""Greenhouse public board adapter.

Mapping moved verbatim from pipeline.fetch_jobs — output dicts are byte-for-byte
identical to the previous inline implementation.
"""

from __future__ import annotations

from typing import Any

import requests

from .base import REQUEST_TIMEOUT

URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch(token: str, company: str) -> list[dict[str, Any]]:
    resp = requests.get(URL.format(token=token), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    out: list[dict[str, Any]] = []
    for j in jobs:
        out.append(
            {
                "company": company,
                "title": j.get("title", ""),
                "location": (j.get("location") or {}).get("name", ""),
                "url": j.get("absolute_url", ""),
                "description": j.get("content", "") or "",
                "source": "greenhouse",
                "id": str(j.get("id", "")),
            }
        )
    return out
