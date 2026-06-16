"""Classification layer.

LIVE in this scaffold phase:
    - title_score(): title-weighted scoring (moved verbatim from pipeline.py).

STUBS (defined for the next task, NOT wired into the pipeline yet):
    - classify_role_family()
    - compute_pillars()
    - detect_hard_blockers()

The stubs intentionally raise NotImplementedError so nothing accidentally
depends on placeholder output. The recommendation engine (recommend.py) will be
built on top of these in the follow-up task.
"""

from __future__ import annotations

from typing import Any

from .matching import keyword_matches

# ---------------------------------------------------------------------------
# Title-weighted scoring (LIVE — moved from pipeline.py, behaviour unchanged)
# ---------------------------------------------------------------------------
# Title signals are strong discriminators that JD-body keyword density cannot
# fake. Role-family negatives here apply to the TITLE ONLY (a body that merely
# says "partner with the product manager" is not penalised).

TITLE_STRONG = [
    "ai product engineer", "product engineer", "applied ai engineer",
    "forward deployed engineer", "forward-deployed engineer",
    "forward deployed agent builder", "ai workflow engineer",
    "ai automation engineer", "ai solutions engineer", "ai solutions builder",
    "ai implementation engineer", "technical product engineer",
    "internal ai tools engineer", "claude code", "agent builder",
    "frontier agents engineer",
]
TITLE_MEDIUM = [
    "fullstack", "full-stack", "product engineering",
    "developer experience", "solutions engineer", "ai engineer",
]
# "solutions architect" is medium ONLY when paired with AI context (handled below).
TITLE_NEG = [
    "product designer", "ux designer", "ux researcher", "legal counsel",
    "accountant", "recruiter", "talent acquisition", "account executive",
    "sales manager", "marketing manager", "marketing operations",
    "customer success manager", "product manager", "senior product manager",
    "group product manager", "principal product manager", "engineering manager",
    "director", "head of", "manager of", "global lead", "architecture lead",
    "finance manager", "people operations", "hr business partner",
    "office manager", "executive assistant", "copywriter",
]

TITLE_STRONG_PER_HIT = 18
TITLE_STRONG_CAP = 36
TITLE_MEDIUM_PER_HIT = 8
TITLE_MEDIUM_CAP = 16
TITLE_NEG_PER_HIT = -35


def title_score(title: str, description: str = "") -> int:
    """Score based on the job TITLE only (description used solely for the
    AI-context gate on 'solutions architect'). Returns a signed int."""
    t = title or ""
    strong = min(
        sum(TITLE_STRONG_PER_HIT for k in TITLE_STRONG if keyword_matches(t, k)),
        TITLE_STRONG_CAP,
    )
    medium = sum(TITLE_MEDIUM_PER_HIT for k in TITLE_MEDIUM if keyword_matches(t, k))
    # Conditional: "Solutions Architect" only counts when AI context is present
    # in the title or description.
    if keyword_matches(t, "solutions architect"):
        ai_ctx = any(
            keyword_matches(t, c) or keyword_matches(description or "", c)
            for c in ("ai", "applied ai", "claude", "agent", "llm")
        )
        if ai_ctx:
            medium += TITLE_MEDIUM_PER_HIT
    medium = min(medium, TITLE_MEDIUM_CAP)
    neg = sum(TITLE_NEG_PER_HIT for k in TITLE_NEG if keyword_matches(t, k))
    return int(strong + medium + neg)


# ---------------------------------------------------------------------------
# Role family / pillars / hard blockers (STUBS — not implemented, not wired)
# ---------------------------------------------------------------------------

ROLE_FAMILIES = (
    "AI_PRODUCT_ENGINEER",
    "APPLIED_AI_BUILDER",
    "AI_WORKFLOW_AUTOMATION",
    "FORWARD_DEPLOYED_AI",
    "AI_SOLUTIONS_IMPLEMENTATION",
    "FINTECH_PRODUCT_ENGINEER",
    "FINANCIAL_SYSTEMS_API",
    "LOCAL_AI_ADOPTION",
    "DEVEX_AI_TOOLS",
    "WEAK_ADJACENT",
    "WRONG_FAMILY",
)


def classify_role_family(job: dict[str, Any], profile: Any = None) -> str:
    """TODO (next task): return a value from ROLE_FAMILIES based on title-first
    then description signals. Not implemented in the scaffold phase."""
    raise NotImplementedError("classify_role_family: implemented in the classify/recommend task")


def compute_pillars(job: dict[str, Any], profile: Any = None, location_signal: str | None = None) -> Any:
    """TODO (next task): compute the seven fit pillars (see models.Pillars)."""
    raise NotImplementedError("compute_pillars: implemented in the classify/recommend task")


def detect_hard_blockers(job: dict[str, Any], profile: Any = None, location_signal: str | None = None) -> list[str]:
    """TODO (next task): return a list of hard-blocker reasons (empty = none).
    Will use section + qualifier proximity, not bare keyword presence."""
    raise NotImplementedError("detect_hard_blockers: implemented in the classify/recommend task")
