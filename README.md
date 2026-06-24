# job-agent

An autonomous job application pipeline powered by Claude AI. It searches Greenhouse and Lever job boards, scores each posting against your preferences, tailors your resume to each role, and (optionally) fills and submits applications — all with a single command.

**Dry-run mode is on by default.** The agent will never submit a real application unless you explicitly pass both `--apply` and `--confirm`.

---

## Features

- Searches Greenhouse and Lever APIs for open roles at your target companies
- Scores each job against your preferences using Claude (0–100)
- Filters out low-match jobs and saves them to `output/rejected_jobs.csv`
- Tailors your resume for each qualifying job (rewrites summary + bullets, reorders skills)
- Fills out application forms using Playwright (supports custom questions, dropdowns, file upload)
- Takes a screenshot before any submission for review
- Logs every result to `output/applications_log.csv`
- Saves pipeline progress to `output/progress.json` so runs can be resumed

---

## Installation

### 1. Clone and set up a virtual environment

```bash
cd job-agent
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
playwright install chromium
```

---

## Configuration

### Step 1 — API key and personal info

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
DRY_RUN=true
HEADLESS=false

FIRST_NAME=Jane
LAST_NAME=Doe
EMAIL=jane@example.com
PHONE=+1-555-555-5555
LINKEDIN_URL=https://linkedin.com/in/janedoe
GITHUB_URL=https://github.com/janedoe
PORTFOLIO_URL=https://janedoe.dev
```

### Step 2 — Add your resume

Place your resume at `data/resume.pdf` (or `data/resume.docx`). You can point to a different path with `--resume`.

### Step 3 — Edit preferences

Open `data/preferences.yaml` and customise:

- `roles` — job titles you are targeting
- `locations` — acceptable locations (include "Remote" if needed)
- `keywords_must_have` — hard requirements; low score if missing
- `keywords_nice_to_have` — bonus keywords
- `min_match_score` — jobs below this score are skipped (default: 75)
- `max_applications_per_day` — safety cap on daily submissions
- `greenhouse_companies` — list of Greenhouse board slugs (the part after `boards.greenhouse.io/`)
- `lever_companies` — list of Lever slugs (the part after `jobs.lever.co/`)

Example company slugs:
```yaml
greenhouse_companies:
  - stripe
  - airbnb
lever_companies:
  - vercel
  - notion
```

---

## Usage

### Search and score only (no forms filled)

```bash
python main.py --search-only
```

### Dry run (fills forms, takes screenshots, does NOT submit)

```bash
python main.py --dry-run
```

This is also the **default** — running with no flags is equivalent to `--dry-run`.

### Dry run with a custom resume or preferences file

```bash
python main.py --resume path/to/my_resume.pdf --prefs path/to/my_prefs.yaml --dry-run
```

### Live apply — submits real applications (use with caution)

Both `--apply` AND `--confirm` are required to prevent accidental submissions:

```bash
python main.py --apply --confirm
```

If you pass `--apply` without `--confirm`, the agent prints a warning and exits without doing anything.

---

## Output files

| Path | Contents |
|------|----------|
| `output/tailored_resumes/` | PDF resume tailored for each company/role |
| `output/screenshots/` | Screenshot of each form before submission |
| `output/applications_log.csv` | All application attempts with status |
| `output/rejected_jobs.csv` | Jobs that scored below `min_match_score` |
| `output/progress.json` | Pipeline state for resuming interrupted runs |

---

## Safety notes

- `DRY_RUN=true` is the default in both `.env.example` and `config.py`.
- The agent enforces a maximum of **5 applications per platform per hour** regardless of settings.
- A random 3–7 second delay is added between each platform request.
- Screenshots are always taken before any submit button is clicked.
- The pipeline skips jobs already present in `applications_log.csv`, so it is safe to re-run.
# job-agent
