"""Agentic Engineering Jobs public REST API adapter (no auth).

A single public aggregator endpoint (NOT a per-company board): the ``token``
argument is treated as optional and ``company`` is an unused display fallback —
each job carries its own ``companyName``. Public/PII-free fields only; the job
``description`` is fetched for scoring but high-churn/analytics/decorative fields
(viewCount/clickCount/impressionCount/brandColors/featured*) are dropped. No
auth, cookies, credentials, or HTML scraping.

Emits the canonical pre-normalization shape used by pipeline.py:
    {company, title, location, url, description, source, id}
with ``source = "agentic_engineering_jobs"`` and ``id`` from the job ``slug``.
"""

from __future__ import annotations

from typing import Any

import requests

from .base import REQUEST_TIMEOUT

URL = "https://agentic-engineering-jobs.com/api/v1/jobs"
SOURCE = "agentic_engineering_jobs"
DEFAULT_PARAMS = {"sort": "newest", "locationType": "remote"}


def _apply_url(job: dict[str, Any]) -> str:
    """Best-effort public apply/listing URL from applyMethods, else companyWebsite."""
    methods = job.get("applyMethods")
    if isinstance(methods, list):
        for m in methods:
            if isinstance(m, dict):
                u = m.get("url") or m.get("value") or m.get("href") or m.get("link")
                if u:
                    return str(u)
            elif isinstance(m, str) and m.startswith("http"):
                return m
    elif isinstance(methods, dict):
        u = methods.get("url") or methods.get("value") or methods.get("href")
        if u:
            return str(u)
    elif isinstance(methods, str) and methods.startswith("http"):
        return methods
    return str(job.get("companyWebsite") or "")


def _location(job: dict[str, Any]) -> str:
    loc = job.get("location") or job.get("city") or ""
    if not loc:
        countries = job.get("countries")
        if isinstance(countries, list) and countries:
            loc = ", ".join(str(c) for c in countries if c)
    return str(loc or "")


def normalize_jobs(payload: Any) -> list[dict[str, Any]]:
    """Map an API payload ({data: [...], meta: {...}} or a bare list) to canonical
    job dicts. Pure (no network) so it is unit-testable with a fixture."""
    if isinstance(payload, dict):
        jobs = payload.get("data")
    elif isinstance(payload, list):
        jobs = payload
    else:
        jobs = None
    if not isinstance(jobs, list):
        jobs = []
    out: list[dict[str, Any]] = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        out.append(
            {
                "company": str(j.get("companyName") or ""),
                "title": str(j.get("title") or ""),
                "location": _location(j),
                "url": _apply_url(j),
                "description": str(j.get("description") or ""),
                "source": SOURCE,
                "id": str(j.get("slug") or ""),
            }
        )
    return out


def fetch(token: str = "", company: str = "") -> list[dict[str, Any]]:
    """Fetch newest remote postings from the public Agentic Engineering Jobs API.

    Single no-auth GET. ``token``/``company`` are accepted for adapter-signature
    compatibility but the source is an aggregator (each job carries its company).
    """
    resp = requests.get(
        URL,
        params=dict(DEFAULT_PARAMS),
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "job-board-pipeline/1.0"},
    )
    resp.raise_for_status()
    return normalize_jobs(resp.json() or {})
