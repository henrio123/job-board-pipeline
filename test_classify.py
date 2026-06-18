"""Golden-fixture tests for the profile-fit classifier (job_pipeline/classify.py).

Pure: no network, no profile.yaml. Fixtures are synthetic JD snippets.
Runs under pytest or directly: ``python3 test_classify.py``.
"""

from job_pipeline.classify import (
    assess,
    classify_role_family,
    compute_pillars,
    detect_hard_blockers,
    evidence_fit,
)
from job_pipeline.location import derive_location_signal


def make(title, description="", location=""):
    return {"title": title, "description": description, "location": location}


def sig(location, description=""):
    return derive_location_signal(location, description)["location_signal"]


def assess_fixture(title, description="", location=""):
    job = make(title, description, location)
    s = sig(location, description)
    return assess(job, s), s


# --- golden fixtures -------------------------------------------------------

def test_awin_senior_ai_engineer_eu():
    a, _ = assess_fixture(
        "Senior AI Engineer",
        "Build LLM-powered features and internal AI tooling. Ship prototypes to production using Claude and agents.",
        "Amsterdam, Netherlands; Berlin, Germany",
    )
    assert a["role_family"] in {"APPLIED_AI_BUILDER", "DEVEX_AI_TOOLS"}
    assert a["evidence_fit"] in {"VIABLE", "STRONG"}
    assert a["hard_blockers"] == []


def test_vercel_forward_deployed_engineer_hybrid_eu():
    a, _ = assess_fixture(
        "Forward-Deployed Engineer",
        "Work directly with customers to implement AI agents and integrations, from prototype to production.",
        "Hybrid - London, Berlin",
    )
    assert a["role_family"] == "FORWARD_DEPLOYED_AI"
    assert a["pillars"]["implementation_fit"] == 2
    assert a["hard_blockers"] == []


def test_pipedrive_principal_ai_ml_scientist_tallinn():
    a, _ = assess_fixture(
        "Principal AI/ML Scientist",
        "Conduct deep learning research and publish papers. Train large models.",
        "Tallinn, Estonia",
    )
    assert a["role_family"] == "WRONG_FAMILY"
    assert "ML_RESEARCH_MISMATCH" in a["hard_blockers"]
    assert a["evidence_fit"] == "REJECT"


def test_product_manager_developer_productivity():
    blockers = detect_hard_blockers(
        make("Product Manager, Developer Productivity", "Own the roadmap for developer tools."),
        location_signal="EU_ACTIONABLE",
    )
    assert "PRODUCT_MANAGER_NO_ENGINEERING" in blockers
    assert classify_role_family(make("Product Manager, Developer Productivity")) == "WRONG_FAMILY"


def test_veriff_backend_no_relevance_tallinn():
    a, _ = assess_fixture(
        "Senior Back-End Engineer",
        "Maintain backend services and databases. Work with PostgreSQL and Go to ensure reliability.",
        "Tallinn, Estonia",
    )
    assert a["role_family"] in {"WEAK_ADJACENT", "WRONG_FAMILY"}
    assert a["evidence_fit"] in {"WEAK", "REJECT"}
    assert a["evidence_fit"] != "STRONG"


def test_tehisaru_local_ai_adoption_estonia():
    a, _ = assess_fixture(
        "Tehisaru ekspert",
        "Drive AI adoption and process automation across the organisation; build internal automation and workflows.",
        "Tallinn, Estonia",
    )
    assert a["role_family"] == "LOCAL_AI_ADOPTION"
    assert a["evidence_fit"] in {"VIABLE", "STRONG"}


def test_anthropic_applied_ai_engineer_non_eu():
    a, s = assess_fixture(
        "Applied AI Engineer",
        "Build LLM applications with customers using Claude. Ship prototypes to production.",
        "San Francisco, CA | New York City, NY",
    )
    assert a["role_family"] == "APPLIED_AI_BUILDER"
    assert "LOCATION_BLOCKER" in a["hard_blockers"]
    assert a["pillars"]["ai_workflow_fit"] >= 1
    assert a["pillars"]["location_fit"] == 0


def test_backend_with_apis_fintech_product():
    a, _ = assess_fixture(
        "Backend Engineer",
        "Build payment APIs and integrations for our fintech platform. Own product features end-to-end.",
        "Lisbon, Portugal",
    )
    assert a["role_family"] in {"FINANCIAL_SYSTEMS_API", "FINTECH_PRODUCT_ENGINEER"}
    assert "PURE_BACKEND_WEAK_RELEVANCE" not in a["hard_blockers"]


def test_pm_mention_in_body_only_does_not_block():
    blockers = detect_hard_blockers(
        make("Software Engineer", "You will partner with the product manager to ship features."),
        location_signal="EU_ACTIONABLE",
    )
    assert "PRODUCT_MANAGER_NO_ENGINEERING" not in blockers


def test_recruiter_mention_in_body_only_does_not_block():
    blockers = detect_hard_blockers(
        make("AI Engineer", "Our recruiter will contact you after you apply."),
        location_signal="EU_ACTIONABLE",
    )
    assert "WRONG_FUNCTION" not in blockers


# --- proximity gate for hard ML requirement --------------------------------

def test_pytorch_nice_to_have_is_not_hard_requirement():
    blockers = detect_hard_blockers(
        make("AI Engineer", "Familiarity with PyTorch is a plus, but not required."),
        location_signal="EU_ACTIONABLE",
    )
    assert "HARD_ML_REQUIREMENT" not in blockers


def test_pytorch_required_is_hard_requirement():
    blockers = detect_hard_blockers(
        make("AI Engineer", "Requirements: you must have strong experience with PyTorch and model training."),
        location_signal="EU_ACTIONABLE",
    )
    assert "HARD_ML_REQUIREMENT" in blockers


def test_evidence_fit_helper_rejects_wrong_family():
    pillars = compute_pillars(make("Director, Engineering"), location_signal="EU_ACTIONABLE")
    fam = classify_role_family(make("Director, Engineering"))
    assert fam == "WRONG_FAMILY"
    assert evidence_fit(fam, pillars, ["PEOPLE_MANAGEMENT"]) == "REJECT"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
