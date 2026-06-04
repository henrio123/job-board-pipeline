#!/usr/bin/env python3
"""job-board-pipeline: fetch, score, classify, and draft job-search follow-ups.

The pipeline:
  1. Fetches job listings from the public Greenhouse and Lever board APIs
     for the companies listed in `SOURCES` in this file.
  2. Scores each job against the candidate profile in `profile.yaml`.
  3. Classifies matches into follow-up tracks (A = tailored, B = light, C = log only).
  4. Writes a CSV report and per-job draft files under `outputs/`.
  5. Optionally sends a digest email when `DRY_RUN=false` AND `--send` is passed.

By default the pipeline is dry-run: no email is sent. CSV reports and draft
templates are written to disk and that is the public portfolio behaviour.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import smtplib
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

from shortlist import build_shortlist_payload

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("job-board-pipeline")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
TEMPLATES_DIR = BASE_DIR / "templates"
STATE_PATH = BASE_DIR / "state.json"


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
# Trim this to the companies you actually want to monitor.
# `type` is one of {"greenhouse", "lever"}. `token` is the company slug
# in the board URL (boards.greenhouse.io/<token> or jobs.lever.co/<token>).
SOURCES: list[dict[str, str]] = [
    {"type": "greenhouse", "token": "example_company_one", "company": "Example Company One"},
    {"type": "greenhouse", "token": "example_company_two", "company": "Example Company Two"},
    {"type": "lever", "token": "example_company_three", "company": "Example Company Three"},
]


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

@dataclass
class Profile:
    name: str
    headline: str
    focus_areas: list[str]
    highlights: list[str]
    keywords_must_have: list[str]
    keywords_nice_to_have: list[str]
    keywords_weak_positive: list[str]
    keywords_deal_breaker: list[str]
    keywords_seniority: list[str]
    locations_acceptable: list[str]
    min_salary_eur: int | None
    weights: dict[str, float]
    track_a_threshold: int
    track_b_threshold: int

    @classmethod
    def load(cls, path: Path) -> "Profile":
        if not path.exists():
            log.error("Profile YAML not found at %s. Copy profile.example.yaml to %s and edit.", path, path)
            sys.exit(2)
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        try:
            return cls(**data)
        except TypeError as exc:
            log.error("profile.yaml schema mismatch: %s", exc)
            sys.exit(2)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{token}?mode=json"


def fetch_jobs(sources: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for src in sources:
        company = src["company"]
        try:
            if src["type"] == "greenhouse":
                resp = requests.get(GREENHOUSE_URL.format(token=src["token"]), timeout=20)
                resp.raise_for_status()
                jobs = resp.json().get("jobs", [])
                for j in jobs:
                    out.append(
                        {
                            "company": company,
                            "title": j.get("title", ""),
                            "location": (j.get("location") or {}).get("name", ""),
                            "url": j.get("absolute_url", ""),
                            "description": j.get("content", "") or "",
                            "source": "greenhouse",
                            "id": str(j.get("id", "")),
                        }
                    )
            elif src["type"] == "lever":
                resp = requests.get(LEVER_URL.format(token=src["token"]), timeout=20)
                resp.raise_for_status()
                jobs = resp.json() or []
                for j in jobs:
                    out.append(
                        {
                            "company": company,
                            "title": j.get("text", ""),
                            "location": (j.get("categories") or {}).get("location", ""),
                            "url": j.get("hostedUrl", ""),
                            "description": j.get("descriptionPlain", "") or "",
                            "source": "lever",
                            "id": str(j.get("id", "")),
                        }
                    )
            else:
                log.warning("Unknown source type %r for %s; skipping", src["type"], company)
        except requests.RequestException as exc:
            log.warning("Fetch failed for %s (%s): %s", company, src["type"], exc)
        time.sleep(0.2)  # gentle pacing
    log.info("Fetched %d jobs across %d sources", len(out), len(sources))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def keyword_score(haystack: str, keywords: list[str], per_hit: float, cap: float) -> float:
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw.lower() in haystack)
    return min(hits * per_hit, cap)


def score_job(job: dict[str, Any], profile: Profile) -> int:
    blob = normalize(" ".join([job.get("title", ""), job.get("description", ""), job.get("location", "")]))

    w = profile.weights
    score = 0.0
    score += keyword_score(blob, profile.keywords_must_have, w["must_have"], w["must_have_cap"])
    score += keyword_score(blob, profile.keywords_nice_to_have, w["nice_to_have"], w["nice_to_have_cap"])
    score += keyword_score(blob, profile.keywords_weak_positive, w["weak_positive"], w["weak_positive_cap"])
    score += keyword_score(blob, profile.keywords_seniority, w["seniority"], w["seniority_cap"])

    # deal breakers: no cap, fully subtractive
    for db in profile.keywords_deal_breaker:
        if db.lower() in blob:
            score += w["deal_breaker"]

    return int(round(score))


def classify_track(score: int, profile: Profile) -> str:
    if score >= profile.track_a_threshold:
        return "A"  # tailored follow-up
    if score >= profile.track_b_threshold:
        return "B"  # light follow-up
    return "C"  # log only


# ---------------------------------------------------------------------------
# Templating
# ---------------------------------------------------------------------------

def load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


def render(template_text: str, variables: dict[str, str]) -> str:
    out = template_text
    for key, value in variables.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def render_drafts(job: dict[str, Any], profile: Profile, track: str) -> dict[str, str]:
    bullet_lines = "\n".join(f"- {h}" for h in profile.highlights[:3])
    focus_areas_block = "\n".join(f"- {f}" for f in profile.focus_areas)
    brief = ", ".join(profile.focus_areas[:2])
    track_bit = "Open to a short call this week. " if track == "A" else ""

    variables = {
        "name": profile.name,
        "headline": profile.headline,
        "title": job["title"],
        "company": job["company"],
        "bullet_lines": bullet_lines,
        "focus_areas_block": focus_areas_block,
        "brief": brief,
        "track_bit": track_bit,
    }
    return {
        "email": render(load_template("email_draft.txt"), variables),
        "linkedin": render(load_template("linkedin_message_draft.txt"), variables),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def write_outputs(jobs_scored: list[dict[str, Any]], profile: Profile) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    csv_path = OUTPUTS_DIR / f"jobs-{stamp}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["score", "track", "company", "title", "location", "url", "source", "id"],
        )
        writer.writeheader()
        for row in jobs_scored:
            writer.writerow(
                {k: row.get(k, "") for k in writer.fieldnames}
            )

    drafts_dir = OUTPUTS_DIR / f"drafts-{stamp}"
    drafts_dir.mkdir(exist_ok=True)
    for row in jobs_scored:
        if row["track"] in {"A", "B"}:
            base = drafts_dir / f"{row['score']:03d}-{slug(row['company'])}-{slug(row['title'])}"
            (base.with_suffix(".email.txt")).write_text(row["email_draft"], encoding="utf-8")
            (base.with_suffix(".linkedin.txt")).write_text(row["linkedin_draft"], encoding="utf-8")

    # Machine-readable shortlist of Track A/B jobs, reusing the already-scored,
    # already-sorted rows. Fixed filename (overwritten each run), unlike the CSV.
    shortlist_path = OUTPUTS_DIR / "shortlisted_jobs.json"
    payload = build_shortlist_payload(jobs_scored, datetime.now(timezone.utc).isoformat())
    shortlist_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log.info("Wrote %s, %s and %s", csv_path, drafts_dir, shortlist_path)
    return csv_path


# ---------------------------------------------------------------------------
# SMTP (gated)
# ---------------------------------------------------------------------------

def maybe_send_digest(csv_path: Path, top_rows: list[dict[str, Any]], dry_run: bool, send_flag: bool) -> None:
    if dry_run or not send_flag:
        log.info("Dry-run: digest not sent (DRY_RUN=%s, --send=%s)", dry_run, send_flag)
        return

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    email_to = os.getenv("EMAIL_TO", "")

    if not all([smtp_host, smtp_user, smtp_pass, email_to]):
        log.error("SMTP credentials incomplete in .env; refusing to send. Falling back to dry-run.")
        return

    body_lines = ["Top job matches:\n"]
    for r in top_rows[:10]:
        body_lines.append(f"  [{r['score']:>3}] {r['company']}: {r['title']} ({r['location']})\n    {r['url']}")
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg["Subject"] = "job-board-pipeline digest"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [email_to], msg.as_string())
        log.info("Digest sent to %s", email_to)
    except smtplib.SMTPException as exc:
        log.error("SMTP send failed: %s", exc)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    load_dotenv()
    profile_path = Path(os.getenv("PROFILE_PATH", "profile.yaml"))
    profile = Profile.load(profile_path)

    jobs = fetch_jobs(SOURCES)
    if args.limit:
        jobs = jobs[: args.limit]

    scored: list[dict[str, Any]] = []
    for job in jobs:
        score = score_job(job, profile)
        track = classify_track(score, profile)
        row: dict[str, Any] = {**job, "score": score, "track": track}
        if track in {"A", "B"}:
            drafts = render_drafts(job, profile, track)
            row["email_draft"] = drafts["email"]
            row["linkedin_draft"] = drafts["linkedin"]
        scored.append(row)

    scored.sort(key=lambda r: r["score"], reverse=True)

    csv_path = write_outputs(scored, profile)

    top = [r for r in scored if r["track"] in {"A", "B"}]
    dry_run_env = os.getenv("DRY_RUN", "true").lower() in {"1", "true", "yes"}
    maybe_send_digest(csv_path, top, dry_run=dry_run_env or args.dry_run, send_flag=args.send)

    log.info(
        "Done. %d jobs scored. Track A: %d, Track B: %d, Track C: %d",
        len(scored),
        sum(1 for r in scored if r["track"] == "A"),
        sum(1 for r in scored if r["track"] == "B"),
        sum(1 for r in scored if r["track"] == "C"),
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="job-board-pipeline")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of jobs scored (0 = no limit).")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run regardless of .env.")
    parser.add_argument("--send", action="store_true", help="Send the digest email (requires DRY_RUN=false in .env).")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
