#!/usr/bin/env python3
"""job-board-pipeline: fetch, score, classify, and draft job-search follow-ups.

The pipeline:
  1. Fetches job listings from the public Greenhouse and Lever board APIs
     for the companies listed in the local, gitignored `sources.yaml`
     (schema in sources.example.yaml; path override via SOURCES_PATH).
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

from job_pipeline.classify import assess, title_score
from job_pipeline.location import derive_location_signal, location_adjustment
from job_pipeline.matching import keyword_matches, keyword_score, normalize
from job_pipeline.output import build_audit_payload, build_shortlist_payload
from job_pipeline.sources import ADAPTERS

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
# The companies to monitor live in a local, gitignored `sources.yaml`
# (see sources.example.yaml for the schema; override the path with
# SOURCES_PATH). Each entry: `type` is one of {"greenhouse", "lever"},
# `token` is the company slug in the board URL
# (boards.greenhouse.io/<token> or jobs.lever.co/<token>), `company`
# is the display name used in reports and drafts.

SOURCE_REQUIRED_FIELDS = ("type", "token", "company")


def load_sources(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        log.error(
            "Sources config not found at %s. Copy sources.example.yaml to %s and edit it. "
            "sources.yaml is gitignored; never commit your real company list.",
            path,
            path,
        )
        sys.exit(2)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list) or not sources:
        log.error("%s must contain a non-empty 'sources' list. See sources.example.yaml.", path)
        sys.exit(2)
    for i, src in enumerate(sources):
        if not isinstance(src, dict) or not all(src.get(k) for k in SOURCE_REQUIRED_FIELDS):
            log.error(
                "sources[%d] in %s must have non-empty fields %s. See sources.example.yaml.",
                i,
                path,
                ", ".join(SOURCE_REQUIRED_FIELDS),
            )
            sys.exit(2)
    return sources


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
# The per-board HTTP + mapping lives in job_pipeline/sources/{greenhouse,lever}.
# This orchestrator keeps the loop, pacing, error handling, and logging.


def fetch_jobs(sources: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for src in sources:
        company = src["company"]
        adapter = ADAPTERS.get(src["type"])
        if adapter is None:
            log.warning("Unknown source type %r for %s; skipping", src["type"], company)
        else:
            try:
                out.extend(adapter(src["token"], company))
            except requests.RequestException as exc:
                log.warning("Fetch failed for %s (%s): %s", company, src["type"], exc)
        time.sleep(0.2)  # gentle pacing
    log.info("Fetched %d jobs across %d sources", len(out), len(sources))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
# normalize / keyword_matches / keyword_score now live in job_pipeline.matching;
# title_score in job_pipeline.classify (both imported above).


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
        if keyword_matches(blob, db):
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
            fieldnames=[
                "score", "original_score", "adjusted_score",
                "body_score", "title_score", "track",
                "company", "title", "location",
                "location_signal", "location_blockers", "location_notes",
                "url", "source", "id",
            ],
        )
        writer.writeheader()
        for row in jobs_scored:
            out = {k: row.get(k, "") for k in writer.fieldnames}
            # Flatten list-valued location fields for CSV cells.
            for k in ("location_blockers", "location_notes"):
                val = row.get(k, "")
                out[k] = "; ".join(val) if isinstance(val, list) else val
            writer.writerow(out)

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

    # Classifier audit output over ALL scored jobs (inspection only; does not
    # change shortlist behaviour or Track A/B/C).
    audit_path = OUTPUTS_DIR / "audit_jobs.json"
    audit_payload = build_audit_payload(jobs_scored, datetime.now(timezone.utc).isoformat())
    audit_path.write_text(
        json.dumps(audit_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log.info("Wrote %s, %s, %s and %s", csv_path, drafts_dir, shortlist_path, audit_path)
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

    sources_path = Path(os.getenv("SOURCES_PATH", "sources.yaml"))
    sources = load_sources(sources_path)

    jobs = fetch_jobs(sources)
    if args.limit:
        jobs = jobs[: args.limit]

    scored: list[dict[str, Any]] = []
    for job in jobs:
        body_score = score_job(job, profile)
        t_score = title_score(job.get("title", ""), job.get("description", ""))
        # original_score = pre-location total (body keyword score + title score).
        original_score = body_score + t_score
        loc = derive_location_signal(job.get("location", ""), job.get("description", ""))
        adjusted_score = original_score + location_adjustment(loc["location_signal"])
        # Track assignment uses the location-adjusted score; never delete a job
        # purely on location — it is downranked and the blockers recorded.
        track = classify_track(adjusted_score, profile)
        row: dict[str, Any] = {
            **job,
            "body_score": body_score,
            "title_score": t_score,
            "original_score": original_score,
            "adjusted_score": adjusted_score,
            "score": adjusted_score,
            "location_signal": loc["location_signal"],
            "location_blockers": loc["location_blockers"],
            "location_notes": loc["location_notes"],
            "track": track,
        }
        # Classifier audit layer (does not affect track/score/shortlist).
        row.update(assess(job, loc["location_signal"]))
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
