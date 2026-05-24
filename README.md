# Job Board Pipeline

Python automation pipeline for collecting job listings from public Greenhouse and Lever boards, scoring them against a candidate profile, producing CSV reports, and preparing draft follow-up templates.

## Status

Public portfolio version. Personal profile data, real follow-up history, and generated exports are not included.

**Sending is disabled by default.** The pipeline prepares CSV reports and draft templates on disk; the optional SMTP digest is gated behind both `DRY_RUN=false` in `.env` and an explicit `--send` flag on the CLI.

## What it does

1. **Fetch**: pulls job listings from the public Greenhouse and Lever board APIs for the companies listed in `SOURCES` inside `pipeline.py`.
2. **Score**: scores every fetched job against `profile.yaml`. Must-have keywords (capped positive), nice-to-have keywords (capped positive), weak-positive keywords (small cap), deal-breaker keywords (uncapped negative), and seniority keywords (small cap).
3. **Classify**: routes each match into one of three follow-up tracks based on score thresholds in `profile.yaml`:
   - **Track A** (`>= track_a_threshold`): tailored follow-up drafts.
   - **Track B** (`>= track_b_threshold`): light follow-up drafts.
   - **Track C** (everything else): logged in the CSV but no drafts produced.
4. **Report**: writes a timestamped CSV under `outputs/jobs-<timestamp>.csv` with score, track, company, title, location, URL, source, and ID.
5. **Draft**: for Track A and Track B matches, renders per-job email and LinkedIn drafts under `outputs/drafts-<timestamp>/` from the templates in `templates/`.
6. **Send (optional, off by default)**: when `DRY_RUN=false` and `--send` are both set, emails a digest of top matches via SMTP. Otherwise the pipeline never opens a network connection beyond the public-board APIs.

## Tech stack

- Python 3.10+
- `requests` for board API calls
- `python-dotenv` for environment loading
- `PyYAML` for the profile schema
- Standard library `smtplib` + `email.mime` for the optional digest
- Templates rendered with simple `{{placeholder}}` substitution, so no external templating engine is required

## Setup

```bash
git clone https://github.com/<your-user>/job-board-pipeline.git
cd job-board-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp profile.example.yaml profile.yaml          # then edit profile.yaml
cp .env.example .env                          # leave DRY_RUN=true unless you want to send
```

## Example workflow

```bash
# 1. Edit profile.yaml with your name, headline, keywords, weights, thresholds.
# 2. Edit SOURCES in pipeline.py with the Greenhouse/Lever company tokens you want to monitor.
# 3. Run the pipeline (defaults are dry-run, no email):
python3 pipeline.py

# Outputs land under outputs/:
#   outputs/jobs-20260524-143000Z.csv
#   outputs/drafts-20260524-143000Z/050-example-company-senior-engineer.email.txt
#   outputs/drafts-20260524-143000Z/050-example-company-senior-engineer.linkedin.txt
```

To actually send the digest email, set `DRY_RUN=false` in `.env`, populate the SMTP fields, and re-run with `--send`:

```bash
python3 pipeline.py --send
```

The pipeline still refuses to send if any SMTP credential is missing.

## Environment variables

See `.env.example`. The relevant fields are:

- `DRY_RUN`: defaults to `true`. Set `false` only if you also want to enable real sending. The CLI `--dry-run` flag forces dry-run regardless.
- `PROFILE_PATH`: path to your candidate profile YAML. Defaults to `profile.yaml`.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`: only used when `DRY_RUN=false` and `--send` are both set.

## Project layout

```
job-board-pipeline/
├── pipeline.py                       # main script
├── profile.example.yaml              # candidate profile schema with example values
├── templates/
│   ├── email_draft.txt               # email draft template
│   └── linkedin_message_draft.txt    # LinkedIn DM template
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## What is not included

- A real `profile.yaml`: only `profile.example.yaml` ships, with placeholder values.
- A real `.env`: only `.env.example` ships, with `DRY_RUN=true` and blank SMTP fields.
- Any historical job exports, CSV reports, or sent drafts (everything under `outputs/`, `artifacts/`, `*.csv`, `*.jsonl` is gitignored).
- Any specific company list. `SOURCES` ships as a 3-entry placeholder; edit it to monitor the boards you actually care about.

## Notes on design

- The pipeline is intentionally single-file (`pipeline.py`) and dependency-light. It is meant as a reference implementation for the score, classify, and draft pattern, not as a multi-tenant SaaS scaffold.
- Scoring caps are configurable per category in `profile.yaml -> weights`. Tune them to suit your job market.
- Templates use plain `{{placeholder}}` substitution, so there is no Jinja2 dependency. If you want loops or conditionals, swap in Jinja2 and update `render()` in `pipeline.py`.
