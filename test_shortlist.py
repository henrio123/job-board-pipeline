"""Tests for the pure shortlist helpers in shortlist.py.

No network, no third-party deps, no profile.yaml. Runs under pytest if present,
or directly as a stdlib script: ``python3 test_shortlist.py``.
"""

from job_pipeline.location import derive_location_signal
from job_pipeline.output import build_shortlist_payload, make_job_id
from job_pipeline.rank import select_company_diverse


def _fake_jobs():
    return [
        {
            "company": "Example Company",
            "title": "Senior AI Engineer",
            "location": "Remote",
            "url": "https://boards.greenhouse.io/example/jobs/123456",
            "description": "Build AI automation pipelines.",
            "source": "greenhouse",
            "id": "123456",
            "score": 58,
            "track": "A",
        },
        {
            "company": "Another Co",
            "title": "Automation Engineer",
            "location": "Berlin",
            "url": "https://jobs.lever.co/another/abc",
            "description": "",
            "source": "lever",
            "id": "",  # no board id -> fallback path
            "score": 33,
            "track": "B",
        },
        {
            # Track C must be excluded from the shortlist.
            "company": "Skip Co",
            "title": "Unrelated Role",
            "location": "On-site",
            "url": "https://jobs.lever.co/skip/zzz",
            "description": "",
            "source": "lever",
            "id": "999",
            "score": 5,
            "track": "C",
        },
    ]


def test_job_id_from_source_and_id():
    assert make_job_id("greenhouse", "123456", "Co", "Title", "https://x") == "greenhouse:123456"


def test_job_id_fallback_is_deterministic_when_id_missing():
    a = make_job_id("lever", "", "Another Co", "Automation Engineer", "https://jobs.lever.co/another/abc")
    b = make_job_id("lever", "", "Another Co", "Automation Engineer", "https://jobs.lever.co/another/abc")
    assert a == b  # deterministic across calls
    assert a.startswith("lever:")
    assert a != "lever:"  # a real digest got appended
    # Different inputs -> different id
    c = make_job_id("lever", "", "Another Co", "Different Title", "https://jobs.lever.co/another/abc")
    assert a != c


def test_payload_shape_and_fields():
    payload = build_shortlist_payload(_fake_jobs(), "2026-06-04T12:00:00+00:00")
    assert payload["schema_version"] == "1.1"
    assert payload["source"] == "job-board-pipeline"
    assert payload["generated_at"] == "2026-06-04T12:00:00+00:00"
    # Only Track A and B -> 2 jobs (Track C excluded)
    assert payload["count"] == 2
    assert len(payload["jobs"]) == 2
    assert "company_diverse" in payload
    for job in payload["jobs"]:
        for key in ("job_id", "source", "source_id", "company", "title",
                    "location", "url", "score", "original_score",
                    "adjusted_score", "location_signal", "location_blockers",
                    "location_notes", "track", "status", "raw"):
            assert key in job
        assert job["status"] == "shortlisted"
        assert job["track"] in {"A", "B"}
        assert isinstance(job["location_blockers"], list)
        assert isinstance(job["location_notes"], list)
        assert "description" in job["raw"]


def test_order_is_score_descending():
    payload = build_shortlist_payload(_fake_jobs(), "2026-06-04T12:00:00+00:00")
    scores = [j["score"] for j in payload["jobs"]]
    assert scores == sorted(scores, reverse=True)
    assert scores == [58, 33]


def test_source_id_present_and_fallback_empty():
    payload = build_shortlist_payload(_fake_jobs(), "2026-06-04T12:00:00+00:00")
    by_company = {j["company"]: j for j in payload["jobs"]}
    assert by_company["Example Company"]["source_id"] == "123456"
    assert by_company["Example Company"]["job_id"] == "greenhouse:123456"
    assert by_company["Another Co"]["source_id"] == ""  # missing id -> empty string
    assert by_company["Another Co"]["job_id"].startswith("lever:")


def _sig(location, description=""):
    return derive_location_signal(location, description)["location_signal"]


def test_location_sf_nyc_is_non_eu():
    assert _sig("San Francisco, CA | New York City, NY") == "NON_EU_OR_US_ONSITE"


def test_location_remote_europe_is_estonia_remote_eu():
    assert _sig("Remote Europe") == "ESTONIA_OR_REMOTE_EU"
    assert _sig("Remote - EMEA") == "ESTONIA_OR_REMOTE_EU"


def test_location_tallinn_is_estonia_remote_eu():
    assert _sig("Tallinn, Estonia") == "ESTONIA_OR_REMOTE_EU"


def test_location_paris_is_eu_actionable():
    assert _sig("Paris") == "EU_ACTIONABLE"


def test_location_hybrid_paris_is_hybrid_eu():
    assert _sig("Hybrid - Paris (3 days in office)") == "HYBRID_EU"
    assert _sig("Hybrid - London, Berlin") == "HYBRID_EU"


def test_location_remote_with_us_only_in_description_is_non_eu():
    res = derive_location_signal("Remote", "You must be authorized to work in the United States.")
    assert res["location_signal"] == "NON_EU_OR_US_ONSITE"
    assert res["location_blockers"]  # blocker recorded


def test_location_remote_friendly_no_blocker_is_remote_global():
    assert _sig("Remote-Friendly (Travel Required)") == "REMOTE_GLOBAL_OR_UNCLEAR"


def test_location_london_is_eu_actionable_with_uk_note():
    res = derive_location_signal("London, UK", "")
    assert res["location_signal"] == "EU_ACTIONABLE"
    assert any("UK" in n for n in res["location_notes"])


def test_location_singapore_is_non_eu():
    assert _sig("Singapore") == "NON_EU_OR_US_ONSITE"


def test_location_hybrid_us_cities_is_non_eu():
    assert _sig("Hybrid - San Francisco, New York City, Austin") == "NON_EU_OR_US_ONSITE"


def test_location_multi_region_eu_and_us_is_eu_actionable_with_note():
    res = derive_location_signal("London, UK; San Francisco, CA", "")
    assert res["location_signal"] == "EU_ACTIONABLE"
    assert any("multi-region" in n for n in res["location_notes"])


def test_location_remote_friendly_with_us_city_has_confirm_note():
    res = derive_location_signal("Remote-Friendly - San Francisco, New York", "")
    assert res["location_signal"] == "REMOTE_GLOBAL_OR_UNCLEAR"
    assert any("confirm region eligibility" in n for n in res["location_notes"])


def test_company_diverse_collapses_to_best_per_company():
    jobs = [
        {"company": "Anthropic", "track": "A", "adjusted_score": 84},
        {"company": "Anthropic", "track": "A", "adjusted_score": 60},
        {"company": "Anthropic", "track": "B", "adjusted_score": 40},
        {"company": "Mistral", "track": "B", "adjusted_score": 41},
        {"company": "Mistral", "track": "B", "adjusted_score": 30},
    ]
    out = select_company_diverse(jobs)
    assert len(out) == 2  # one per company
    by_company = {j["company"]: j for j in out}
    assert by_company["Anthropic"]["adjusted_score"] == 84  # highest A
    assert by_company["Mistral"]["adjusted_score"] == 41    # best B
    assert out[0]["company"] == "Anthropic"  # sorted by adjusted_score desc


def test_company_diverse_prefers_track_a_over_higher_b():
    jobs = [
        {"company": "Co", "track": "B", "adjusted_score": 90},
        {"company": "Co", "track": "A", "adjusted_score": 50},
    ]
    out = select_company_diverse(jobs)
    assert len(out) == 1
    assert out[0]["track"] == "A"  # Track A preferred even though B scored higher


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
