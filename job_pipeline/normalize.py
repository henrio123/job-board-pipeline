"""Normalization: RawPosting -> canonical Job (minimal helpers / STUB).

Scaffold phase ships only the small, pure `clean_html` helper. The full
`normalize_posting()` (stable id, dedup key, cleaned text into models.Job) is
implemented in a later task; it is not wired into the pipeline yet, which still
consumes the plain dicts produced by the source adapters.
"""

from __future__ import annotations

import html
import re
from typing import Any


def clean_html(text: str) -> str:
    """Unescape HTML entities and strip tags to plain text (case preserved).

    Note: location._clean lowercases for matching; this variant preserves case
    for display/storage of the cleaned description.
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()


def normalize_posting(raw: dict[str, Any]) -> dict[str, Any]:
    """TODO (next task): map a raw source posting into a canonical models.Job
    (stable id, cleaned description, dedup key). Not implemented yet."""
    raise NotImplementedError("normalize_posting: implemented in the normalization task")
