"""Tests for the Agentic Engineering Jobs adapter (job_pipeline/sources/agentic.py).

No network: exercises the pure ``normalize_jobs(payload)`` mapping against a
synthetic ``{data, meta}`` fixture. Runs under pytest or directly via
``python3 test_agentic.py`` (stdlib fallback). Synthetic data only.
"""

from job_pipeline.sources import ADAPTERS, agentic
from job_pipeline.output import shortlist_job


def _fixture():
    return {
        "meta": {"count": 2},
        "data": [
            {
                "slug": "example-co-applied-ai-engineer",
                "title": "Applied AI Engineer",
                "companyName": "Example Public Co",
                "companyWebsite": "https://example.com",
                "location": "Remote (EU)",
                "locationType": "remote",
                "remoteScope": "EU",
                "postedAt": "2026-06-18T00:00:00Z",
                "techStackTags": ["python", "langgraph"],
                "agenticFrameworks": ["langgraph"],
                "applyMethods": [{"type": "url", "url": "https://example.com/apply/1"}],
                "description": "Build agentic pipelines.",
                "viewCount": 999, "clickCount": 12, "brandColors": ["#fff"],
            },
            {
                # minimal record: only slug/title present, optional fields missing
                "slug": "another-automation-engineer",
                "title": "Automation Engineer",
            },
        ],
    }


def test_registry_has_agentic():
    assert ADAPTERS["agentic_engineering_jobs"] is agentic.fetch


def test_normalize_envelope_count():
    jobs = agentic.normalize_jobs(_fixture())
    assert len(jobs) == 2


def test_source_is_agentic_engineering_jobs():
    jobs = agentic.normalize_jobs(_fixture())
    assert all(j["source"] == "agentic_engineering_jobs" for j in jobs)


def test_field_mapping():
    j = agentic.normalize_jobs(_fixture())[0]
    assert j["id"] == "example-co-applied-ai-engineer"      # slug -> id
    assert j["company"] == "Example Public Co"               # companyName -> company
    assert j["url"] == "https://example.com/apply/1"         # applyMethods -> url
    assert j["location"] == "Remote (EU)"
    assert j["title"] == "Applied AI Engineer"


def test_missing_optional_fields_safe():
    j = agentic.normalize_jobs(_fixture())[1]
    assert j["id"] == "another-automation-engineer"
    assert j["company"] == ""        # missing companyName -> empty, no crash
    assert j["url"] == ""            # no applyMethods/website -> empty
    assert j["source"] == "agentic_engineering_jobs"


def test_malformed_payload_safe():
    assert agentic.normalize_jobs(None) == []
    assert agentic.normalize_jobs({"data": "nope"}) == []
    assert agentic.normalize_jobs({"data": [None, 1, "x"]}) == []


def test_bridge_projection_carries_source_and_no_description():
    # Through the existing shortlist_job projection, the bridge record carries
    # source == "agentic_engineering_jobs" and does NOT emit the description.
    j = agentic.normalize_jobs(_fixture())[0]
    bridge = shortlist_job(j)
    assert bridge["source"] == "agentic_engineering_jobs"
    assert bridge["job_id"].startswith("agentic_engineering_jobs:")
    assert "description" not in bridge


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
