"""Backward-compatibility shim.

The pure helpers that used to live here were moved into the ``job_pipeline``
package during the scaffold phase (location.py / rank.py / output.py). This
module re-exports the public names so existing imports keep working. Prefer
importing from ``job_pipeline.*`` in new code; this shim may be removed once the
output split lands.
"""

from __future__ import annotations

from job_pipeline.location import (  # noqa: F401
    ACTIONABILITY_RANK,
    LOCATION_ADJUSTMENT,
    SIG_EU_ACTIONABLE,
    SIG_ESTONIA_REMOTE_EU,
    SIG_HYBRID_EU,
    SIG_NON_EU,
    SIG_REMOTE_GLOBAL,
    SIG_UNCLEAR,
    actionability_rank,
    derive_location_signal,
    location_adjustment,
)
from job_pipeline.output import (  # noqa: F401
    SCHEMA_VERSION,
    build_shortlist_payload,
    make_job_id,
    shortlist_job,
)
from job_pipeline.rank import select_company_diverse  # noqa: F401

__all__ = [
    "ACTIONABILITY_RANK",
    "LOCATION_ADJUSTMENT",
    "SCHEMA_VERSION",
    "SIG_ESTONIA_REMOTE_EU",
    "SIG_EU_ACTIONABLE",
    "SIG_HYBRID_EU",
    "SIG_NON_EU",
    "SIG_REMOTE_GLOBAL",
    "SIG_UNCLEAR",
    "actionability_rank",
    "build_shortlist_payload",
    "derive_location_signal",
    "location_adjustment",
    "make_job_id",
    "select_company_diverse",
    "shortlist_job",
]
