"""Tests for word-boundary keyword matching in pipeline.py scoring.

Covers keyword_matches(), keyword_score(), and score_job() keyword behaviour.
Pure local tests: no network, no profile.yaml, no sources.yaml — the Profile
is constructed in-memory with illustrative placeholder keywords only.

Runs under pytest or directly: ``python3 test_scoring.py``.
"""

from __future__ import annotations

from job_pipeline.classify import title_score
from job_pipeline.matching import keyword_matches, keyword_score, normalize
from pipeline import Profile, score_job

# Substring traps the matcher must NOT fall into.
NEGATIVE_CASES = [
    ("defi", "defined"),
    ("ai", "email"),
    ("ai", "maintain"),
    ("ai", "available"),
    ("ai", "paid"),
    ("ai", "said"),
    ("api", "rapidly"),
]

# Whole-word / phrase / hyphen / case matches that MUST hit.
POSITIVE_CASES = [
    ("defi", "DeFi"),
    ("ai", "AI"),
    ("api", "API"),
    ("lending", "lending"),
    ("credit risk", "credit risk"),
    ("on-chain", "on-chain"),
    ("smart contract", "smart contract"),
    ("llm", "LLM"),
    ("commission-only", "commission-only"),
]

WEIGHTS = {
    "must_have": 8.0,
    "must_have_cap": 40.0,
    "nice_to_have": 5.0,
    "nice_to_have_cap": 20.0,
    "weak_positive": 3.0,
    "weak_positive_cap": 10.0,
    "deal_breaker": -10.0,
    "seniority": 8.0,
    "seniority_cap": 15.0,
}


def make_profile() -> Profile:
    return Profile(
        name="Example Candidate",
        headline="Example headline.",
        focus_areas=["example focus"],
        highlights=["example highlight"],
        keywords_must_have=["defi", "lending", "credit risk"],
        keywords_nice_to_have=["ai", "api", "analytics"],
        keywords_weak_positive=["automation"],
        keywords_deal_breaker=["commission-only"],
        keywords_seniority=["senior"],
        locations_acceptable=["remote"],
        min_salary_eur=None,
        weights=dict(WEIGHTS),
        track_a_threshold=50,
        track_b_threshold=30,
    )


def make_job(description: str, title: str = "Coordinator") -> dict:
    return {"title": title, "description": description, "location": ""}


def test_negative_substring_traps():
    for kw, text in NEGATIVE_CASES:
        assert not keyword_matches(text, kw), f"{kw!r} must not match {text!r}"
        # Same behaviour embedded in a sentence.
        sentence = f"the role has {text} responsibilities"
        assert not keyword_matches(sentence, kw), f"{kw!r} must not match inside {sentence!r}"


def test_positive_whole_word_matches():
    for kw, text in POSITIVE_CASES:
        assert keyword_matches(text, kw), f"{kw!r} must match {text!r}"
        sentence = f"experience with {text} is required"
        assert keyword_matches(sentence, kw), f"{kw!r} must match inside {sentence!r}"


def test_phrase_whitespace_variation():
    assert keyword_matches("strong credit  risk background", "credit risk")
    assert keyword_matches(normalize("credit\n risk"), "credit risk")
    assert not keyword_matches("credit and risk", "credit risk")


def test_keyword_score_ignores_false_positives():
    haystack = normalize("defined email maintain available rapidly paid said")
    assert keyword_score(haystack, ["defi", "ai", "api"], 8.0, 40.0) == 0.0


def test_keyword_score_counts_and_caps_real_hits():
    haystack = normalize("AI and API work with analytics")
    assert keyword_score(haystack, ["ai", "api", "analytics"], 5.0, 20.0) == 15.0
    # Cap still applies.
    assert keyword_score(haystack, ["ai", "api", "analytics"], 8.0, 10.0) == 10.0


def test_score_job_awards_nothing_for_false_positive_text():
    job = make_job("We have defined email workflows, maintain available systems rapidly.")
    assert score_job(job, make_profile()) == 0


def test_score_job_scores_real_phrases():
    job = make_job("Work on credit risk and lending with analytics and a REST API.")
    # must_have: lending + credit risk = 16; nice_to_have: api + analytics = 10.
    assert score_job(job, make_profile()) == 26


def test_score_job_deal_breaker_word_boundary():
    profile = make_profile()
    base = make_job("Credit risk and lending role.")
    flagged = make_job("Credit risk and lending role. This is commission-only.")
    assert score_job(flagged, profile) == score_job(base, profile) - 10
    # "commission-only" must not fire on unrelated text containing "only".
    unaffected = make_job("Credit risk and lending role. Use the commission portal only.")
    assert score_job(unaffected, profile) == score_job(base, profile)


def test_title_strong_positive_boost():
    # Strong "applied ai engineer" (+18) plus medium "fullstack" (+8).
    assert title_score("Applied AI Engineer, Fullstack") >= 18
    assert title_score("Applied AI Engineer, Fullstack") > title_score("Coordinator")


def test_title_forward_deployed_agent_builder_boost():
    assert title_score("Software Engineer, Forward Deployed Agent Builder") >= 18


def test_title_negative_product_manager_penalised():
    assert title_score("Product Manager, Developer Productivity") < 0


def test_title_negative_does_not_fire_from_description():
    # Title is clean; "product manager" only in the description must NOT penalise.
    assert title_score("Senior Software Engineer", "You will partner with the product manager.") == 0


def test_title_solutions_engineer_ai_not_penalised():
    assert title_score("Solutions Engineer, AI") >= 0


def test_title_director_penalised():
    assert title_score("Director, Forward Deployed Engineering") < 0


def test_title_solutions_architect_conditional_on_ai_context():
    # No AI context -> no medium credit; with AI context -> credited.
    assert title_score("Solutions Architect") == 0
    assert title_score("Solutions Architect", "Work with Claude and LLM agents.") == 8


if __name__ == "__main__":
    # Allow running without pytest installed.
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
