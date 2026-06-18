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

import re
from typing import Any

from .matching import keyword_matches
from .location import (
    SIG_ESTONIA_REMOTE_EU,
    SIG_EU_ACTIONABLE,
    SIG_HYBRID_EU,
    SIG_NON_EU,
    SIG_REMOTE_GLOBAL,
    SIG_UNCLEAR,
)

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
# profile-fit classifier (role_family / pillars / hard_blockers / evidence_fit)
# ---------------------------------------------------------------------------
# Audit-only in this task: results are emitted into outputs/audit_jobs.json.
# The recommendation cutover (APPLY/ASK_FIRST/BACKUP/SKIP) is a later task and
# Track A/B/C behaviour is unchanged.

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

TARGET_FAMILIES = frozenset(ROLE_FAMILIES) - {"WEAK_ADJACENT", "WRONG_FAMILY"}

HARD_BLOCKER_CATEGORIES = (
    "LOCATION_BLOCKER",
    "ML_RESEARCH_MISMATCH",
    "HARD_ML_REQUIREMENT",
    "PLATFORM_MLOPS_MISMATCH",
    "PEOPLE_MANAGEMENT",
    "PRODUCT_MANAGER_NO_ENGINEERING",
    "WRONG_FUNCTION",
    "LANGUAGE_BLOCKER",
    "PURE_BACKEND_WEAK_RELEVANCE",
)

LOCATION_FIT = {
    SIG_ESTONIA_REMOTE_EU: 2,
    SIG_EU_ACTIONABLE: 2,
    SIG_HYBRID_EU: 1,
    SIG_REMOTE_GLOBAL: 1,
    SIG_UNCLEAR: 0,
    SIG_NON_EU: 0,
}

# --- term banks ------------------------------------------------------------
_AI_TERMS = [
    "ai", "artificial intelligence", "llm", "llms", "genai", "generative ai",
    "agent", "agents", "agentic", "claude", "claude code", "codex", "cursor",
    "copilot", "gpt", "chatbot", "rag", "machine learning",
]
_FIN_TERMS = [
    "fintech", "defi", "on-chain", "onchain", "vault", "vaults", "blockchain",
    "crypto", "web3", "digital asset", "digital assets", "stablecoin",
    "payments", "lending", "credit", "underwriting", "trading",
    "financial infrastructure", "financial systems", "banking", "custody",
    "treasury", "capital markets", "credit risk",
]
_API_TERMS = [
    "api", "apis", "rest api", "graphql", "sdk", "webhook", "webhooks",
    "integration", "integrations",
]
_PRODUCT_TERMS = [
    "product engineer", "product engineering", "product specification",
    "product specifications", "product spec", "prioritization",
    "prioritisation", "roadmap", "prototype", "prototyping", "launch",
    "product-minded", "build products", "0 to 1", "zero to one",
    "end-to-end ownership",
]
_WORKFLOW_TERMS = [
    "agent", "agents", "agentic", "mcp", "claude code", "codex", "cursor",
    "workflow orchestration", "multi-agent", "orchestration", "automation",
    "automate", "eval", "evals", "rag", "pipeline",
]
_IMPL_TERMS = [
    "forward deployed", "forward-deployed", "customer-facing", "client-facing",
    "implementation", "deployment", "onboarding", "solutions", "field engineer",
    "work directly with customers", "embed with", "deliver solutions",
    "integration", "integrations",
]
_ADOPTION_TERMS = [
    "ai adoption", "ai enablement", "tehisaru", "ai transformation",
    "process automation", "digital transformation", "automation specialist",
    "ai specialist", "ai literacy", "internal ai",
]

_RESEARCH_TITLES = [
    "research scientist", "applied scientist", "research engineer",
    "data scientist", "machine learning scientist", "ml scientist",
    "ai scientist", "research lead", "principal scientist", "ml researcher",
    "research manager", "deep learning engineer",
]
_WRONG_FUNCTION_TITLES = [
    "product designer", "ux designer", "ux researcher", "graphic designer",
    "legal counsel", "attorney", "lawyer", "accountant", "bookkeeper",
    "controller", "account executive", "sales manager", "sales development",
    "business development representative", "marketing manager",
    "marketing operations", "brand manager", "content marketing",
    "communications manager", "pr manager", "copywriter", "recruiter",
    "talent acquisition", "sourcer", "people operations", "hr business partner",
    "office manager", "executive assistant", "customer success manager",
    "customer success", "community manager", "support specialist",
]
_EXEC_TITLES = ["director", "head of", "vp", "vice president", "chief", "head,"]
_PM_TITLES = [
    "product manager", "senior product manager", "group product manager",
    "principal product manager", "product owner",
]
_FD_TITLES = [
    "forward deployed", "forward-deployed", "deployment engineer",
    "deployment strategist", "agent builder", "forward deployed agent builder",
]
_APPLIED_AI_TITLES = ["applied ai engineer", "applied ai", "ai engineer"]
_ML_ENGINEER_TITLES = ["ml engineer", "machine learning engineer"]
_WORKFLOW_TITLES = [
    "ai workflow", "workflow engineer", "ai automation", "automation engineer",
    "agentic",
]
_SOLUTIONS_TITLES = [
    "ai solutions engineer", "ai solutions", "ai implementation",
    "implementation engineer", "solutions engineer", "solutions architect",
    "sales engineer", "customer engineer",
]
_DEVEX_TITLES = [
    "developer experience", "developer productivity", "devex",
    "internal tools", "developer advocate", "tooling",
]
_LOCAL_AI_TITLES = [
    "tehisaru", "ai adoption", "ai enablement", "ai transformation",
    "ai specialist", "automation specialist",
]
_BACKEND_TITLES = [
    "backend engineer", "back-end engineer", "back end engineer",
    "software engineer", "full stack engineer", "fullstack engineer",
    "frontend engineer", "front-end engineer", "site reliability", "sre",
    "infrastructure engineer", "data engineer", "systems engineer",
    "qa engineer", "security engineer", "mobile engineer", "platform engineer",
]

_HARD_ML_TERMS = [
    "tensorflow", "pytorch", "keras", "jax", "scikit-learn", "model training",
    "training models", "train models", "fine-tuning", "fine tuning",
    "deep learning", "neural networks",
]
_PLATFORM_TERMS = [
    "mlops", "ml infrastructure", "ml platform", "feature store", "kubeflow",
    "sagemaker", "model serving", "model deployment at scale",
]
_STRONG_QUALIFIERS = [
    "required", "must have", "must-have", "must be", "minimum qualification",
    "minimum qualifications", "you must", "strong proficiency",
    "proficiency in", "proficient in", "expertise in", "deep expertise",
    "extensive experience", "years of experience", "years experience",
    "strong experience", "proven experience", "solid experience",
    "deep understanding", "strong background",
]
_SOFT_NEGATORS = [
    "nice to have", "nice-to-have", "a plus", "bonus", "preferred", "ideally",
    "would be", "not required", "familiarity", "exposure", "some experience",
    "helpful", "plus if",
]


def _has(title: str, desc: str, terms: list[str]) -> bool:
    return any(keyword_matches(title, t) or keyword_matches(desc, t) for t in terms)


def _title_has(title: str, terms: list[str]) -> bool:
    return any(keyword_matches(title, t) for t in terms)


def _required_near(text_lower: str, term: str, window: int = 90) -> bool:
    """True if `term` appears near a strong requirement qualifier and not next
    to a soft negator (nice-to-have / a plus). Description-only, proximity-based
    — avoids the whole-blob false positives of bare keyword presence."""
    pattern = r"\s+".join(re.escape(p) for p in term.lower().split())
    for m in re.finditer(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text_lower):
        seg = text_lower[max(0, m.start() - window): m.end() + window]
        if any(q in seg for q in _STRONG_QUALIFIERS) and not any(n in seg for n in _SOFT_NEGATORS):
            return True
    return False


def _features(job: dict[str, Any]) -> dict[str, Any]:
    title = job.get("title", "") or ""
    desc = job.get("description", "") or ""
    dl = desc.lower()

    pm_title = _title_has(title, _PM_TITLES)
    has_eng = _title_has(title, ["engineer", "engineering", "developer"])
    has_manager = keyword_matches(title, "manager")

    f = {
        "title": title,
        "desc": desc,
        "ai_ctx": _has(title, desc, _AI_TERMS),
        "fin_ctx": _has(title, desc, _FIN_TERMS),
        "api_ctx": _has(title, desc, _API_TERMS),
        "workflow_ctx": _has(title, desc, _WORKFLOW_TERMS),
        "impl_ctx": _has(title, desc, _IMPL_TERMS),
        "adoption_ctx": _has(title, desc, _ADOPTION_TERMS) or _title_has(title, _LOCAL_AI_TITLES),
        "research_title": _title_has(title, _RESEARCH_TITLES),
        "wrong_func_title": _title_has(title, _WRONG_FUNCTION_TITLES),
        "pm_title": pm_title,
        "pm_no_eng": pm_title and not _title_has(title, ["engineer", "engineering"]),
        "has_eng": has_eng,
        "is_fd": _title_has(title, _FD_TITLES),
        "is_agent_builder": keyword_matches(title, "agent builder"),
        "is_ai_product_title": keyword_matches(title, "ai product engineer"),
        "is_product_engineer_title": _title_has(
            title, ["product engineer", "product engineering", "technical product engineer"]
        ),
        "is_applied_ai_title": _title_has(title, _APPLIED_AI_TITLES),
        "is_ml_engineer_title": _title_has(title, _ML_ENGINEER_TITLES),
        "is_workflow_title": _title_has(title, _WORKFLOW_TITLES),
        "is_solutions_title": _title_has(title, _SOLUTIONS_TITLES),
        "is_devex_title": _title_has(title, _DEVEX_TITLES),
        "is_local_ai_title": _title_has(title, _LOCAL_AI_TITLES),
        "backend_title": _title_has(title, _BACKEND_TITLES),
    }
    f["mgmt_title"] = _title_has(title, _EXEC_TITLES) or (has_manager and not pm_title)
    f["product_ctx"] = _has(title, desc, _PRODUCT_TERMS) or f["is_product_engineer_title"]

    # Requirement-level (proximity) detections — description only.
    f["hard_ml"] = any(_required_near(dl, t) for t in _HARD_ML_TERMS)
    f["platform_ml"] = (
        _title_has(title, ["mlops", "ml platform", "ml infrastructure"])
        or any(_required_near(dl, t) for t in _PLATFORM_TERMS)
    )
    f["phd_required"] = (
        "phd required" in dl or "ph.d. required" in dl
        or _required_near(dl, "phd") or _required_near(dl, "ph.d")
        or _required_near(dl, "doctorate")
    )
    f["russian_required"] = (
        any(p in dl for p in ("professional russian", "fluent russian", "native russian", "russian language"))
        or _required_near(dl, "russian")
    )
    return f


def _decide_family(f: dict[str, Any]) -> str:
    if f["research_title"]:
        return "WRONG_FAMILY"
    if f["wrong_func_title"]:
        return "WRONG_FAMILY"
    if f["mgmt_title"]:
        return "WRONG_FAMILY"
    if f["pm_no_eng"]:
        return "WRONG_FAMILY"

    if f["is_fd"] and (f["ai_ctx"] or f["is_agent_builder"]):
        return "FORWARD_DEPLOYED_AI"
    if f["is_ai_product_title"] or (f["is_product_engineer_title"] and f["ai_ctx"]):
        return "AI_PRODUCT_ENGINEER"
    if f["is_local_ai_title"]:
        return "LOCAL_AI_ADOPTION"
    if f["is_applied_ai_title"] and f["ai_ctx"]:
        return "APPLIED_AI_BUILDER"
    if f["is_workflow_title"] and f["ai_ctx"]:
        return "AI_WORKFLOW_AUTOMATION"
    if f["is_solutions_title"] and f["ai_ctx"]:
        return "AI_SOLUTIONS_IMPLEMENTATION"
    if f["is_devex_title"] and f["ai_ctx"]:
        return "DEVEX_AI_TOOLS"
    if f["is_product_engineer_title"] and f["fin_ctx"]:
        return "FINTECH_PRODUCT_ENGINEER"
    if f["is_product_engineer_title"]:
        return "AI_PRODUCT_ENGINEER" if f["ai_ctx"] else "WEAK_ADJACENT"
    if f["is_ml_engineer_title"]:
        return "APPLIED_AI_BUILDER" if f["ai_ctx"] else "WRONG_FAMILY"

    # Description-driven finance / API routes.
    if (f["is_product_engineer_title"] or f["product_ctx"]) and f["fin_ctx"]:
        return "FINTECH_PRODUCT_ENGINEER"
    if f["fin_ctx"] and f["api_ctx"]:
        return "FINANCIAL_SYSTEMS_API"
    if f["backend_title"] and (f["fin_ctx"] or f["api_ctx"]) and not f["ai_ctx"]:
        return "FINANCIAL_SYSTEMS_API"

    if f["adoption_ctx"] and f["ai_ctx"]:
        return "LOCAL_AI_ADOPTION"
    if f["ai_ctx"] and (f["workflow_ctx"] or f["impl_ctx"]) and f["has_eng"]:
        return "APPLIED_AI_BUILDER"

    if f["ai_ctx"] or f["fin_ctx"] or f["product_ctx"]:
        return "WEAK_ADJACENT"
    if f["backend_title"]:
        return "WRONG_FAMILY"
    return "WRONG_FAMILY"


def _decide_blockers(f: dict[str, Any], location_signal: str | None) -> list[str]:
    blockers: list[str] = []
    if location_signal == SIG_NON_EU:
        blockers.append("LOCATION_BLOCKER")
    if f["research_title"] or f["phd_required"]:
        blockers.append("ML_RESEARCH_MISMATCH")
    if f["hard_ml"]:
        blockers.append("HARD_ML_REQUIREMENT")
    if f["platform_ml"]:
        blockers.append("PLATFORM_MLOPS_MISMATCH")
    if f["mgmt_title"]:
        blockers.append("PEOPLE_MANAGEMENT")
    if f["pm_no_eng"]:
        blockers.append("PRODUCT_MANAGER_NO_ENGINEERING")
    if f["wrong_func_title"]:
        blockers.append("WRONG_FUNCTION")
    if f["russian_required"]:
        blockers.append("LANGUAGE_BLOCKER")
    if f["backend_title"] and not (f["ai_ctx"] or f["fin_ctx"] or f["api_ctx"] or f["product_ctx"]):
        blockers.append("PURE_BACKEND_WEAK_RELEVANCE")
    # Preserve order, dedupe.
    seen: set[str] = set()
    return [b for b in blockers if not (b in seen or seen.add(b))]


def _decide_pillars(f: dict[str, Any], location_signal: str | None) -> dict[str, int]:
    # product_engineering_fit
    if f["is_product_engineer_title"] or f["is_ai_product_title"]:
        pe = 2
    elif f["product_ctx"]:
        pe = 1
    else:
        pe = 0
    # ai_workflow_fit
    if f["is_ai_product_title"] or f["is_applied_ai_title"] or f["is_workflow_title"] or (
        f["ai_ctx"] and f["workflow_ctx"]
    ):
        aw = 2
    elif f["ai_ctx"]:
        aw = 1
    else:
        aw = 0
    # finance_systems_fit
    if f["fin_ctx"] and (f["api_ctx"] or f["product_ctx"]):
        fs = 2
    elif f["fin_ctx"] or f["api_ctx"]:
        fs = 1
    else:
        fs = 0
    # implementation_fit
    if f["is_fd"] or f["is_solutions_title"]:
        im = 2
    elif f["impl_ctx"]:
        im = 1
    else:
        im = 0
    # location_fit
    loc = LOCATION_FIT.get(location_signal, 0)
    # level_fit
    if f["mgmt_title"] or f["research_title"] or f["wrong_func_title"] or f["pm_no_eng"]:
        lvl = 0
    elif _title_has(f["title"], ["staff", "lead", "principal"]):
        lvl = 1 if f["has_eng"] else 0
    elif _title_has(f["title"], ["intern", "graduate", "junior", "apprentice"]):
        lvl = 1
    else:
        lvl = 2
    return {
        "product_engineering_fit": pe,
        "ai_workflow_fit": aw,
        "finance_systems_fit": fs,
        "implementation_fit": im,
        "location_fit": loc,
        "level_fit": lvl,
    }


def _decide_evidence_fit(role_family: str, pillars: dict[str, int], hard_blockers: list[str]) -> str:
    non_location = [b for b in hard_blockers if b != "LOCATION_BLOCKER"]
    ge1 = sum(1 for v in pillars.values() if v >= 1)
    if role_family == "WRONG_FAMILY" or non_location:
        return "REJECT"
    target = role_family in TARGET_FAMILIES
    if target and ge1 >= 3 and not hard_blockers:
        return "STRONG"
    if target and ge1 >= 2:
        return "VIABLE"
    return "WEAK"


def _decide_signals(f: dict[str, Any], location_signal: str | None) -> tuple[list[str], list[str]]:
    pos: list[str] = []
    if f["ai_ctx"]:
        pos.append("AI/LLM context")
    if f["workflow_ctx"]:
        pos.append("agent/workflow signals")
    if f["impl_ctx"] or f["is_fd"]:
        pos.append("implementation / forward-deployed")
    if f["product_ctx"]:
        pos.append("product engineering")
    if f["fin_ctx"]:
        pos.append("fintech/finance context")
    if f["api_ctx"]:
        pos.append("APIs/integrations")
    if location_signal == SIG_ESTONIA_REMOTE_EU:
        pos.append("Estonia / Remote-EU location")
    elif location_signal == SIG_EU_ACTIONABLE:
        pos.append("EU location")
    elif location_signal == SIG_HYBRID_EU:
        pos.append("hybrid EU location")

    neg: list[str] = []
    if location_signal == SIG_NON_EU:
        neg.append("non-EU / US-onsite location")
    elif location_signal == SIG_UNCLEAR:
        neg.append("unclear location")
    if f["research_title"]:
        neg.append("research/scientist title")
    if f["mgmt_title"]:
        neg.append("management title")
    if f["pm_no_eng"]:
        neg.append("PM title without engineering")
    if f["wrong_func_title"]:
        neg.append("wrong-function title")
    if f["hard_ml"]:
        neg.append("hard ML requirement")
    if f["platform_ml"]:
        neg.append("ML platform/MLOps focus")
    if f["backend_title"] and not (f["ai_ctx"] or f["fin_ctx"] or f["api_ctx"] or f["product_ctx"]):
        neg.append("pure backend, low relevance")
    return pos, neg


def classify_role_family(job: dict[str, Any], profile: Any = None) -> str:
    """Return one of ROLE_FAMILIES. Title-first, then description context."""
    return _decide_family(_features(job))


def compute_pillars(job: dict[str, Any], profile: Any = None, location_signal: str | None = None) -> dict[str, int]:
    """Return the six fit pillars as 0/1/2 ints (see models.Pillars)."""
    return _decide_pillars(_features(job), location_signal)


def detect_hard_blockers(job: dict[str, Any], profile: Any = None, location_signal: str | None = None) -> list[str]:
    """Return a list of HARD_BLOCKER_CATEGORIES (empty = none). Title-only for
    wrong-function/management/PM; proximity-gated for hard ML/platform/PhD."""
    return _decide_blockers(_features(job), location_signal)


def evidence_fit(role_family: str, pillars: dict[str, int], hard_blockers: list[str]) -> str:
    """Coarse, PII-free fit verdict: STRONG | VIABLE | WEAK | REJECT."""
    return _decide_evidence_fit(role_family, pillars, hard_blockers)


def assess(job: dict[str, Any], location_signal: str | None = None, profile: Any = None) -> dict[str, Any]:
    """Full classifier bundle for one job (audit layer). Pure; no recommendation."""
    f = _features(job)
    role_family = _decide_family(f)
    hard_blockers = _decide_blockers(f, location_signal)
    pillars = _decide_pillars(f, location_signal)
    ev = _decide_evidence_fit(role_family, pillars, hard_blockers)
    positive_signals, negative_signals = _decide_signals(f, location_signal)
    return {
        "role_family": role_family,
        "pillars": pillars,
        "evidence_fit": ev,
        "positive_signals": positive_signals,
        "negative_signals": negative_signals,
        "hard_blockers": hard_blockers,
    }
