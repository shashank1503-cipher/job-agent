# Job Agent — Usage Guide

An automated job search pipeline that scrapes listings, scores them against your preferences, and surfaces the best matches via a web UI.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Node.js](https://nodejs.org/) 18+ (for the frontend)
- An Anthropic API key (set as `ANTHROPIC_API_KEY` in `.env`)

```sh
cp .env.example .env   # then fill in your ANTHROPIC_API_KEY
uv sync                # install Python dependencies
cd frontend && npm install && cd ..
```

---

## Configuration

Edit `data/preferences.yaml` to match your job search criteria:

| Section | Description |
|---|---|
| `roles` | Job titles to search for |
| `locations` | Acceptable work locations |
| `remote_locations` | Countries/regions allowed for remote work |
| `keywords_must_have` | Skills the job description must mention |
| `keywords_nice_to_have.tier1/tier2` | Bonus skills, weighted in scoring |
| `keywords_exclude` | Keywords that disqualify a listing |
| `exclude_companies` | Companies to skip entirely |
| `industries` | Preferred industries (used for bonus scoring) |
| `min_match_score` | Minimum score (0–100) for a job to qualify |
| `experience_years` | Your years-of-experience range |
| `search.sites` | Job boards to scrape (`linkedin`, `indeed`, etc.) |
| `search.hours_old` | How fresh listings must be (in hours) |
| `personal_info` | Your name, email, and contact details |
| `resume_variants` | Paths to resume PDFs tagged by skill set |

---

## Commands

### Run the full pipeline

```sh
just search            # use cached jobs (re-scrapes if cache is empty)
just search refresh    # force a fresh scrape, ignoring the cache
```

Or directly:

```sh
uv run python main.py
uv run python main.py --refresh
uv run python main.py --mock     # run with one fake job to test the pipeline
uv run python main.py --prefs path/to/custom_prefs.yaml
```

The pipeline runs three steps:

1. **Search** — scrapes job boards and Greenhouse/Lever APIs, writes results to a local cache.
2. **Match & Score** — filters listings by hard rules (excluded companies, required keywords, salary, location) then scores the rest 0–100.
3. **Persist** — saves qualifying jobs to `output/jobs.db` (SQLite).

### Parse your resume

Feed a resume PDF to auto-update `preferences.yaml` keyword sections:

```sh
just parse-resume data/resumes/resume_backend_python.pdf
```

This calls Claude to extract skills and proposes updates to `keywords_must_have`, `keywords_nice_to_have`, and `experience_years`.

### Start the API

```sh
just api
# → http://localhost:8000
```

The FastAPI server exposes the job database. Interactive docs at `http://localhost:8000/docs`.

### Start the frontend

```sh
just ui
# → http://localhost:5173
```

A Vite/React app that displays scored jobs, lets you mark applications, and shows rejected listings.

### Start both together

```sh
just dev   # runs api + ui in parallel
```

---

## Development

### Running tests

```sh
uv run pytest
```

### Pre-commit hooks

The repo uses [pre-commit](https://pre-commit.com/) with `ruff` for linting and formatting.

```sh
pre-commit install        # one-time setup (already done if you cloned after hooks were added)
pre-commit run --all-files  # run manually against all files
```

---

## Project Layout

```
job-agent/
├── main.py                  # pipeline entry point
├── config.py                # global config / defaults
├── data/
│   └── preferences.yaml     # your job search config
├── agents/
│   ├── search_agent.py      # scrapes job boards
│   └── match_agent.py       # scores and filters listings
├── platforms/
│   ├── greenhouse_client.py # Greenhouse job board client
│   └── lever_client.py      # Lever job board client
├── api/                     # FastAPI backend
├── frontend/                # Vite + React UI
├── utils/
│   ├── resume_parser.py     # PDF → preferences updater
│   ├── job_cache.py         # local JSON job cache
│   └── text_utils.py        # shared text helpers
└── tests/
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key (used by the match agent and resume parser) |
