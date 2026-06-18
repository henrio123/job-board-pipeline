"""Import smoke tests for the job_pipeline package scaffold.

Verifies the module layout is importable, public names exist, the
compatibility shim still works, and the un-wired stubs raise NotImplementedError
(so nothing silently depends on placeholder output). No network, no secrets.
"""

import shortlist
from job_pipeline import (
    classify,
    location,
    matching,
    models,
    normalize,
    output,
    rank,
    recommend,
)
from job_pipeline.sources import ADAPTERS, greenhouse, lever


def test_core_modules_expose_expected_callables():
    assert callable(matching.keyword_matches)
    assert callable(matching.keyword_score)
    assert callable(matching.normalize)
    assert callable(location.derive_location_signal)
    assert callable(location.location_adjustment)
    assert callable(location.actionability_rank)
    assert callable(rank.select_company_diverse)
    assert callable(output.build_shortlist_payload)
    assert callable(output.make_job_id)
    assert callable(classify.title_score)
    assert output.SCHEMA_VERSION == "1.1"


def test_source_registry_present():
    assert set(ADAPTERS) == {"greenhouse", "lever"}
    assert ADAPTERS["greenhouse"] is greenhouse.fetch
    assert ADAPTERS["lever"] is lever.fetch


def test_shim_reexports_match_package():
    assert shortlist.derive_location_signal is location.derive_location_signal
    assert shortlist.build_shortlist_payload is output.build_shortlist_payload
    assert shortlist.select_company_diverse is rank.select_company_diverse
    assert shortlist.SCHEMA_VERSION == output.SCHEMA_VERSION


def test_models_dataclasses_instantiate():
    p = models.Pillars()
    a = models.Assessment()
    assert a.recommendation == "SKIP"
    assert p.evidence_fit == "WEAK"


def test_classifier_now_implemented():
    # classify layer is live as of the audit task.
    assert callable(classify.classify_role_family)
    assert callable(classify.compute_pillars)
    assert callable(classify.detect_hard_blockers)
    assert callable(classify.assess)
    a = classify.assess({"title": "Applied AI Engineer", "description": "", "location": ""}, "EU_ACTIONABLE")
    assert a["role_family"] in classify.ROLE_FAMILIES
    assert set(a) == {
        "role_family", "pillars", "evidence_fit",
        "positive_signals", "negative_signals", "hard_blockers",
    }


def test_remaining_stubs_not_yet_implemented():
    # recommendation + normalization are still future tasks.
    for fn, args in (
        (recommend.recommend, (None,)),
        (normalize.normalize_posting, ({},)),
    ):
        try:
            fn(*args)
        except NotImplementedError:
            continue
        raise AssertionError(f"{fn.__name__} should raise NotImplementedError")


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
