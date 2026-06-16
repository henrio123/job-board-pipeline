"""Keyword / phrase matching primitives (pure, stdlib-only).

Moved verbatim from pipeline.py during the scaffold phase. Shared by the
scoring (score_job), title scoring (classify.title_score), and any future
classifier that needs word-boundary keyword detection.
"""

from __future__ import annotations

import re


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def keyword_matches(haystack: str, keyword: str) -> bool:
    """True if keyword occurs in haystack as a whole word or phrase.

    Case-insensitive. Multi-word keywords match as phrases with flexible
    whitespace; hyphenated keywords ("on-chain") match literally. Alphanumeric
    boundaries prevent short keywords from matching inside longer words
    ("ai" must not match "email", "defi" must not match "defined").
    """
    pattern = r"\s+".join(re.escape(part) for part in keyword.lower().split())
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", haystack.lower()) is not None


def keyword_score(haystack: str, keywords: list[str], per_hit: float, cap: float) -> float:
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if keyword_matches(haystack, kw))
    return min(hits * per_hit, cap)
