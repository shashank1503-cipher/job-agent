# job-agent

An automated job search pipeline powered by Claude AI. It scrapes job boards, scores each listing against your preferences, and surfaces the best matches through a web dashboard — so you spend time applying, not searching.

---

## How it works

1. **Search** — scrapes LinkedIn, Indeed, Greenhouse, and Lever for open roles matching your titles and location filters.
2. **Match & Score** — filters out hard disqualifiers (excluded companies, missing required skills, wrong location/salary), then scores the rest 0–100 using keyword matching and industry bonuses.
3. **Persist** — writes qualifying jobs to a local SQLite database (`output/jobs.db`).
4. **Review** — a React dashboard lets you browse scored jobs, track application status, and view past pipeline runs.

---

## Features

- Searches LinkedIn, Indeed, Greenhouse API, and Lever API
- Hard pre-filters: excluded companies, required keywords, location, salary range
- Tiered keyword scoring: must-have skills + tier-1/tier-2 nice-to-haves
- Industry bonus scoring (Cybersecurity, AI/ML, FinTech, etc.)
- Local SQLite job database with a FastAPI backend
- React + Tailwind dashboard (Jobs, Tracker, Runs views)
- Resume PDF parser — feeds Claude your resume and proposes `preferences.yaml` updates
- Local JSON job cache with configurable TTL to avoid redundant scrapes
- Pre-commit hooks (ruff lint + format, YAML/JSON checks)

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/shashank1503-cipher/job-agent.git
cd job-agent
uv sync                        # install Python deps
cd frontend && npm install && cd ..
```

### 2. Configure secrets

```bash
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY
```

### 3. Edit preferences

Open `data/preferences.yaml` and set your target roles, locations, salary range, required skills, and resume paths. See [USAGE.md](USAGE.md) for the full reference.

### 4. Run the pipeline

```bash
just search          # scrape + score + persist
just api             # start the API on :8000
just ui              # start the dashboard on :5173
just dev             # api + ui together
```

---

## Commands

| Command | Description |
|---|---|
| `just search` | Run the pipeline (uses cache if available) |
| `just search refresh` | Force a fresh scrape |
| `uv run python main.py --mock` | Test the pipeline with one fake job |
| `just parse-resume <path>` | Parse a resume PDF and update preferences |
| `just api` | Start FastAPI backend on port 8000 |
| `just ui` | Start Vite/React frontend on port 5173 |
| `just dev` | Start both together |

---

## Project layout

```
job-agent/
├── main.py                  # pipeline entry point
├── config.py                # global defaults
├── data/
│   └── preferences.yaml     # your job search config
├── agents/
│   ├── search_agent.py      # scrapes job boards
│   └── match_agent.py       # scores and filters listings
├── platforms/
│   ├── greenhouse_client.py
│   └── lever_client.py
├── api/                     # FastAPI backend + SQLModel ORM
├── frontend/                # Vite + React + Tailwind dashboard
├── utils/
│   ├── resume_parser.py     # PDF → preferences updater (Claude)
│   ├── job_cache.py         # local JSON job cache
│   └── text_utils.py
└── tests/
```

---

## Documentation

See [USAGE.md](USAGE.md) for full setup instructions, configuration reference, and environment variable documentation.
