"""job_pipeline — modular core for the Henri-fit job search pipeline.

Staged modularization (scaffold phase): pure helper logic has been moved here
out of the original single-file pipeline.py / shortlist.py. Behaviour is
unchanged — this phase only relocates code and adds (un-wired) placeholders for
the future classify / recommend / normalize layers.

Module map:
    matching   - keyword/phrase matching primitives (pure)
    location   - location_signal classification + adjustments (pure)
    rank       - ordering + per-company diversity (pure)
    output     - shortlist JSON builders (pure, PII-free)
    classify   - title scoring (live) + role_family/pillars/blockers (STUBS)
    recommend  - APPLY/ASK_FIRST/BACKUP/SKIP engine (STUB, not wired)
    normalize  - RawPosting -> Job normalization (minimal helpers / STUB)
    models     - Job / Pillars / Assessment dataclasses (not yet adopted)
    sources/   - per-board fetch adapters (greenhouse, lever)
"""
