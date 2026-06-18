# CLAUDE.md — job-board-pipeline

> This repository is PUBLIC. Keep this file public-safe: no personal contact details, no private job-search strategy, no private repo links, no real profile data, no secrets, no API keys, no employer-specific notes, no application targets.

## 1. Project purpose
Public portfolio version of a job-search pipeline: fetch -> score -> classify -> draft -> (optional) send. Pulls postings from official public board APIs, scores them against a keyword profile, classifies into Track A/B, and writes a CSV, per-job draft messages, and a machine-readable shortlist. Sending is disabled by default; portfolio behavior is to write files to disk only.

## 2. Current implementation
- Python 3.10+ (developed on 3.14), pip. Deps: requests, python-dotenv, PyYAML. No lockfile; pytest not installed locally.
- Run: `python3 pipeline.py` (dry-run default). Flags: `--limit N`, `--dry-run`, `--send` (gated; requires DRY_RUN=false in .env).
- pipeline.py — single-file main: load_sources() (reads gitignored sources.yaml; SOURCES_PATH override; exits with an error if the file is missing, the `sources` list is empty, or an entry lacks type/token/company — no fallback sources), fetch, score_job(), classify_track(), write_outputs(), optional SMTP digest. sources.example.yaml is the tracked placeholder template.
- shortlist.py — pure stdlib helpers (no third-party imports): make_job_id() for stable job IDs, build_shortlist_payload() for the JSON payload. MUST stay dependency-free so it is testable without network, creds, or profile.yaml.
- Keyword matching is word-boundary based via keyword_matches() (case-insensitive, phrase- and hyphen-aware; substring false positives like "ai" inside "email" do not score). Used by both keyword_score() and the deal-breaker check.
- test_shortlist.py — 5 tests; test_scoring.py — 8 tests for word-boundary keyword matching. Both run under pytest or directly via `python3 <file>` (stdlib fallback).
- Sources: Greenhouse public board APIs, Lever public board APIs, and explicitly approved public/no-auth job APIs such as Agentic Engineering Jobs. No authenticated scraping, cookies, sessions, credentials, private APIs, or automated application submission. No HTML scraping, RSS, or CSV input.
  - Approved public/no-auth source ids: `greenhouse`, `lever`, `agentic_engineering_jobs` (Agentic Engineering Jobs public REST API).
- Latest public commit: bdc3d8f "Move watched company sources to local config" on origin/main (word-boundary scoring fix lands in the commit after it).

## 3. Safety and privacy rules
- Sending stays disabled by default. `--send` requires DRY_RUN=false; never flip the default.
- Never commit: .env, profile.yaml, sources.yaml, state.json, outputs/, *.csv, drafts, or any real personal data. Only .env.example, profile.example.yaml, and sources.example.yaml are committed examples.
- Keep this repo's content public-safe. profile.example.yaml and sources.example.yaml are illustrative placeholder data only; real company tokens never go in tracked files.
- No new job sources, and no auto-apply or automated sending, without an explicit request.
- Do not change scoring logic, source fetching, or SMTP behavior as a side effect of unrelated work.

## 4. Verification commands
- `python3 -m py_compile pipeline.py shortlist.py test_shortlist.py test_scoring.py`
- `python3 test_shortlist.py`
- `python3 test_scoring.py`
- `grep -rn "SMTP_PASSWORD\|EMAIL_PASSWORD\|API_KEY\|SECRET\|TOKEN" . --exclude-dir=.git --exclude=.env.example` (expect no matches)

## 5. Output contract
- outputs/jobs-<ts>.csv — timestamped; columns: score,track,company,title,location,url,source,id
- outputs/drafts-<ts>/NNN-company-title.{email,linkedin}.txt
- outputs/shortlisted_jobs.json — fixed filename (overwritten each run), schema_version 1.0, Track A/B only, sorted score-descending. Each job: job_id, source, source_id, company, title, location, url, score, track, status="shortlisted", raw.
- All of outputs/ is gitignored.
- shortlisted_jobs.json is the bridge output intended for a separate downstream application-generation project; treat its shape as a stable contract.

## 6. Known gaps / next steps
- Source config lives in gitignored sources.yaml. The tracked sources.example.yaml documents the schema. The pipeline will not return real jobs until a local sources.yaml with real, verified tokens exists.
- Deduplication: not implemented (re-runs re-emit everything).
- State tracking: state.json is gitignored and currently unused; no seen/applied/rejected lifecycle. job_id is intentionally stable so a future state layer can key off it.
- Hard filters for location, visa, relocation, timezone, and salary are not implemented (profile keys exist but are not read by the scorer; only soft keyword scoring applies).
- No CI.

## 7. Checkpoint protocol
At the end of any task that changes the repo, update this file: record what shipped (with commit hash) in section 2, and revise section 6. Keep it public-safe. Stop before irreversible actions (commit, push, send) unless explicitly told to proceed.
