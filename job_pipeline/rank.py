"""Ranking & company-diversity selection (pure, dependency-free).

Moved verbatim from shortlist.py during the scaffold phase — logic unchanged.
"""

from __future__ import annotations

from typing import Any

from .location import SIG_UNCLEAR, actionability_rank


def _rank_score(job: dict[str, Any]) -> float:
    val = job.get("adjusted_score")
    if val is None:
        val = job.get("score")
    return val if val is not None else 0


def select_company_diverse(jobs: list[dict[str, Any]], max_companies: int = 20) -> list[dict[str, Any]]:
    """One best role per company (Track A/B only): prefer Track A over B, then
    highest adjusted_score. The returned list is ordered by location
    actionability first (Estonia/Remote-EU > EU > Hybrid-EU > Remote/global >
    unclear > non-EU), then by adjusted_score descending, so the most readily
    applicable roles surface first. Each entry gains an `actionability_rank`
    field. Operates on already-projected shortlist job dicts; entries are copied
    so the main `jobs` list is not mutated.
    """
    eligible = [j for j in jobs if j.get("track") in {"A", "B"}]
    best: dict[str, tuple] = {}
    for j in eligible:
        company = j.get("company", "")
        track_rank = 0 if j.get("track") == "A" else 1
        key = (track_rank, -_rank_score(j))
        cur = best.get(company)
        if cur is None or key < cur[0]:
            best[company] = (key, j)
    selected = []
    for _, j in best.values():
        item = dict(j)
        item["actionability_rank"] = actionability_rank(j.get("location_signal", SIG_UNCLEAR))
        selected.append(item)
    selected.sort(key=lambda j: (j["actionability_rank"], -_rank_score(j)))
    return selected[:max_companies]
