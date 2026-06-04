"""Tests for the pure shortlist helpers in shortlist.py.

No network, no third-party deps, no profile.yaml. Runs under pytest if present,
or directly as a stdlib script: ``python3 test_shortlist.py``.
"""

from shortlist import build_shortlist_payload, make_job_id


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
    assert payload["schema_version"] == "1.0"
    assert payload["source"] == "job-board-pipeline"
    assert payload["generated_at"] == "2026-06-04T12:00:00+00:00"
    # Only Track A and B -> 2 jobs (Track C excluded)
    assert payload["count"] == 2
    assert len(payload["jobs"]) == 2
    for job in payload["jobs"]:
        for key in ("job_id", "source", "source_id", "company", "title",
                    "location", "url", "score", "track", "status", "raw"):
            assert key in job
        assert job["status"] == "shortlisted"
        assert job["track"] in {"A", "B"}
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
