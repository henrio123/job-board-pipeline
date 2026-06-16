"""Lever public postings adapter.

Mapping moved verbatim from pipeline.fetch_jobs — output dicts are byte-for-byte
identical to the previous inline implementation.
"""

from __future__ import annotations

from typing import Any

import requests

from .base import REQUEST_TIMEOUT

URL = "https://api.lever.co/v0/postings/{token}?mode=json"


def fetch(token: str, company: str) -> list[dict[str, Any]]:
    resp = requests.get(URL.format(token=token), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    jobs = resp.json() or []
    out: list[dict[str, Any]] = []
    for j in jobs:
        out.append(
            {
                "company": company,
                "title": j.get("text", ""),
                "location": (j.get("categories") or {}).get("location", ""),
                "url": j.get("hostedUrl", ""),
                "description": j.get("descriptionPlain", "") or "",
                "source": "lever",
                "id": str(j.get("id", "")),
            }
        )
    return out
