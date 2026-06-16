"""Lightweight data models for the target architecture.

Defined now for forward reference; NOT yet adopted by the running pipeline
(which still passes plain dicts). Adoption happens incrementally in later tasks
so this scaffold introduces no behaviour change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Job:
    """Canonical, source-agnostic job posting."""
    job_id: str
    source: str
    source_id: str
    company: str
    title: str
    location_raw: str
    description_text: str
    url: str
    posted_at: Optional[str] = None
    dedup_key: str = ""


@dataclass
class Pillars:
    """Per-pillar fit. Integer pillars use 0=absent, 1=weak, 2=strong."""
    product_engineering_fit: int = 0
    ai_workflow_fit: int = 0
    finance_systems_fit: int = 0
    implementation_fit: int = 0
    location_fit: int = 0
    level_fit: int = 0
    evidence_fit: str = "WEAK"  # STRONG | VIABLE | WEAK | REJECT (coarse, PII-free)


@dataclass
class Assessment:
    """Full assessment of a Job. recommendation/reasons populated by recommend()."""
    role_family: str = "WEAK_ADJACENT"
    pillars: Pillars = field(default_factory=Pillars)
    location_signal: str = "LOCATION_UNCLEAR"
    hard_blockers: list[str] = field(default_factory=list)
    positive_signals: list[str] = field(default_factory=list)
    recommendation: str = "SKIP"
    reasons: list[str] = field(default_factory=list)
    fit_score: int = 0  # evidence strength; tiebreaker only, never the gate
