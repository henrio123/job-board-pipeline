"""Pure, dependency-free helpers for building the shortlist JSON output.

Kept separate from pipeline.py on purpose: these functions have no third-party
imports (no requests/yaml/dotenv), so they can be unit-tested without the network,
without API credentials, and without a real profile.yaml.

The pipeline reuses the already-fetched, already-scored, already-sorted in-memory
job rows; nothing here fetches, scores, or sends anything.
"""

from __future__ import annotations

import hashlib
from typing import Any

SCHEMA_VERSION = "1.0"


def make_job_id(source: str, source_id: str, company: str, title: str, url: str) -> str:
    """Return a stable, deterministic id for a job.

    - Prefer ``f"{source}:{source_id}"`` when the board provided an id.
    - Otherwise derive a deterministic id from source/company/title/url via a
      short SHA-1 digest, so the same job always maps to the same id across runs.
    """
    if source_id:
        return f"{source}:{source_id}"
    basis = "|".join([source, company, title, url])
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"{source}:{digest}"


def shortlist_job(row: dict[str, Any]) -> dict[str, Any]:
    """Project a single scored job row into the shortlist JSON shape."""
    source = str(row.get("source", "") or "")
    source_id = str(row.get("id", "") or "")
    company = str(row.get("company", "") or "")
    title = str(row.get("title", "") or "")
    url = str(row.get("url", "") or "")
    return {
        "job_id": make_job_id(source, source_id, company, title, url),
        "source": source,
        "source_id": source_id,
        "company": company,
        "title": title,
        "location": str(row.get("location", "") or ""),
        "url": url,
        "score": row.get("score"),
        "track": row.get("track"),
        "status": "shortlisted",
        "raw": {"description": str(row.get("description", "") or "")},
    }


def build_shortlist_payload(jobs_scored: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    """Build the full shortlist payload from already-scored job rows.

    Only Track A and Track B jobs are included (the same set drafted for and
    summarised in the CSV digest). Jobs are sorted by score descending, matching
    the CSV/shortlist order. Scoring and classification are NOT recomputed here.
    """
    selected = [r for r in jobs_scored if r.get("track") in {"A", "B"}]
    selected.sort(key=lambda r: (r.get("score") or 0), reverse=True)
    jobs = [shortlist_job(r) for r in selected]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": "job-board-pipeline",
        "count": len(jobs),
        "jobs": jobs,
    }
