"""Recommendation engine (STUB — not implemented, not wired).

The next task implements recommend() to return one of RECOMMENDATIONS from an
Assessment. The approved decision defaults are recorded here as the spec to
build against; nothing in the pipeline calls this yet.

Approved decision defaults (from architecture sign-off):
    - HYBRID_EU                -> ASK_FIRST by default; APPLY only with explicit
                                  remote/flexible EU AND very strong fit.
    - UK / London              -> ASK_FIRST by default (not APPLY).
    - Seniority                -> Mid/Senior IC target; Staff/Lead = ASK_FIRST if
                                  IC; people-management = blocked (SKIP).
    - evidence_fit             -> coarse only in this public repo; precise CV
                                  mapping stays in career-evidence-system.
    - REMOTE_GLOBAL_OR_UNCLEAR -> ASK_FIRST if strong fit, BACKUP if medium fit.
    - AI_SOLUTIONS_IMPLEMENTATION -> ASK_FIRST by default; APPLY only with clear
                                  hands-on implementation signals.
    - NON_EU / hard blocker / wrong family / weak evidence -> SKIP.
"""

from __future__ import annotations

from typing import Any

RECOMMENDATIONS = ("APPLY", "ASK_FIRST", "BACKUP", "SKIP")


def recommend(assessment: Any, profile: Any = None) -> tuple[str, list[str]]:
    """TODO (next task): return (recommendation, reasons<=3) from an Assessment.
    Not implemented in the scaffold phase."""
    raise NotImplementedError("recommend: implemented in the recommendation-engine task")
