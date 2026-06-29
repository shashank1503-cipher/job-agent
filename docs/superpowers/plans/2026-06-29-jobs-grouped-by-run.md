# Jobs Grouped by Run — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape `GET /jobs` to return jobs nested under their pipeline runs, and update the Jobs UI to render collapsible per-run sections.

**Architecture:** The backend fetches all runs + filtered jobs in 2 SQL queries, groups in Python, and returns `[{run, jobs}]`. The frontend renders a new `RunGroup` collapsible component per group; filters remain client-side. `GET /jobs/{id}` is untouched.

**Tech Stack:** Python 3.11, FastAPI, SQLModel (SQLite), pytest — React 18, Vite, Tailwind CSS.

## Global Constraints

- `GET /jobs/{id}` must not change
- Existing query params (`score_min`, `source`, `company`) must continue to work
- No new API endpoints
- All Python code runs via `uv run`; tests run via `uv run pytest`
- Dev server: `just api` (port 8000) + `just ui` (port 5173)

---

### Task 1: Add `list_jobs_grouped` to `job_repo` with tests

**Files:**
- Create: `tests/test_job_repo.py`
- Modify: `api/repositories/job_repo.py`

**Interfaces:**
- Produces: `list_jobs_grouped(session, score_min=0, source=None, company=None) -> list[tuple[Run, list[Job]]]`

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_job_repo.py`:

```python
import pytest
from datetime import datetime
from sqlmodel import SQLModel, Session, create_engine

from api.models import Job, Run
from api.repositories.job_repo import list_jobs_grouped


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _run(session, started_at, **kwargs):
    run = Run(started_at=started_at, **kwargs)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _job(session, run_id, apply_url, **kwargs):
    job = Job(apply_url=apply_url, run_id=run_id, **kwargs)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_groups_jobs_by_run_newest_first(session):
    r1 = _run(session, datetime(2026, 6, 28))
    r2 = _run(session, datetime(2026, 6, 27))
    _job(session, r1.id, "https://a.com/1")
    _job(session, r2.id, "https://a.com/2")

    groups = list_jobs_grouped(session)

    assert len(groups) == 2
    assert groups[0][0].id == r1.id
    assert groups[1][0].id == r2.id


def test_jobs_within_group_ordered_by_score_desc(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/low", score=50)
    _job(session, r.id, "https://a.com/high", score=90)

    groups = list_jobs_grouped(session)
    jobs = groups[0][1]

    assert jobs[0].score == 90
    assert jobs[1].score == 50


def test_run_with_no_matching_jobs_still_included(session):
    r1 = _run(session, datetime(2026, 6, 28))
    r2 = _run(session, datetime(2026, 6, 27))
    _job(session, r1.id, "https://a.com/1", score=90)
    _job(session, r2.id, "https://a.com/2", score=30)

    groups = list_jobs_grouped(session, score_min=70)

    assert len(groups) == 2
    assert len(groups[0][1]) == 1
    assert len(groups[1][1]) == 0


def test_score_min_filter(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/low", score=30)
    _job(session, r.id, "https://a.com/high", score=80)

    groups = list_jobs_grouped(session, score_min=70)

    assert len(groups[0][1]) == 1
    assert groups[0][1][0].score == 80


def test_source_filter(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/1", source="lever")
    _job(session, r.id, "https://a.com/2", source="greenhouse")

    groups = list_jobs_grouped(session, source="lever")

    assert len(groups[0][1]) == 1
    assert groups[0][1][0].source == "lever"


def test_company_filter_case_insensitive(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/1", company="Stripe")
    _job(session, r.id, "https://a.com/2", company="Acme")

    groups = list_jobs_grouped(session, company="stripe")

    assert len(groups[0][1]) == 1
    assert groups[0][1][0].company == "Stripe"


def test_empty_db_returns_empty_list(session):
    assert list_jobs_grouped(session) == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_job_repo.py -v
```

Expected: `ImportError` or `AttributeError` — `list_jobs_grouped` does not exist yet.

- [ ] **Step 3: Implement `list_jobs_grouped`**

In `api/repositories/job_repo.py`, change the import line and add the new function:

```python
# Change this line:
from api.models import Job
# To:
from api.models import Job, Run
```

Add after the existing `list_jobs` function:

```python
def list_jobs_grouped(
    session: Session,
    score_min: int = 0,
    source: Optional[str] = None,
    company: Optional[str] = None,
) -> list[tuple[Run, list[Job]]]:
    runs = list(session.exec(select(Run).order_by(Run.started_at.desc())).all())

    q = select(Job)
    if score_min:
        q = q.where(Job.score >= score_min)
    if source:
        q = q.where(Job.source == source)
    if company:
        q = q.where(Job.company.ilike(f"%{company}%"))
    q = q.order_by(Job.score.desc())
    all_jobs = list(session.exec(q).all())

    jobs_by_run: dict[int, list[Job]] = {}
    for job in all_jobs:
        jobs_by_run.setdefault(job.run_id, []).append(job)

    return [(run, jobs_by_run.get(run.id, [])) for run in runs]
```

- [ ] **Step 4: Run tests to confirm they pass**

```
uv run pytest tests/test_job_repo.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/repositories/job_repo.py tests/test_job_repo.py
git commit -m "feat: add list_jobs_grouped to job_repo"
```

---

### Task 2: Update `GET /jobs` router to return grouped shape, with tests

**Files:**
- Create: `tests/test_jobs_router.py`
- Modify: `api/routers/jobs.py`

**Interfaces:**
- Consumes: `list_jobs_grouped(session, score_min, source, company) -> list[tuple[Run, list[Job]]]` (from Task 1)
- Produces: `GET /jobs` → `[{"run": {...}, "jobs": [{...}]}]`

---

- [ ] **Step 1: Write the failing router tests**

Create `tests/test_jobs_router.py`:

```python
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from api.main import app
from api.database import get_session
from api.models import Job, Run


@pytest.fixture
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c, engine
    app.dependency_overrides.clear()


def _seed(engine):
    with Session(engine) as s:
        r1 = Run(started_at=datetime(2026, 6, 28), jobs_fetched=2, jobs_qualified=2)
        r2 = Run(started_at=datetime(2026, 6, 27), jobs_fetched=1, jobs_qualified=1)
        s.add(r1)
        s.add(r2)
        s.commit()
        s.refresh(r1)
        s.refresh(r2)
        s.add(Job(title="Alpha", company="Acme", score=90, source="lever", apply_url="https://a.com/1", run_id=r1.id))
        s.add(Job(title="Beta", company="Stripe", score=70, source="greenhouse", apply_url="https://a.com/2", run_id=r1.id))
        s.add(Job(title="Gamma", company="Acme", score=60, source="lever", apply_url="https://a.com/3", run_id=r2.id))
        s.commit()
        return r1.id, r2.id


def test_get_jobs_returns_grouped_shape(client):
    c, engine = client
    _seed(engine)
    resp = c.get("/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert "run" in data[0]
    assert "jobs" in data[0]
    assert isinstance(data[0]["jobs"], list)


def test_get_jobs_newest_run_first(client):
    c, engine = client
    r1_id, _ = _seed(engine)
    data = c.get("/jobs").json()
    assert data[0]["run"]["id"] == r1_id


def test_get_jobs_run_has_required_fields(client):
    c, engine = client
    _seed(engine)
    run = c.get("/jobs").json()[0]["run"]
    for field in ("id", "started_at", "finished_at", "jobs_fetched", "jobs_qualified", "jobs_rejected"):
        assert field in run, f"Missing run field: {field}"


def test_get_jobs_job_has_required_fields(client):
    c, engine = client
    _seed(engine)
    job = c.get("/jobs").json()[0]["jobs"][0]
    for field in ("id", "title", "company", "score", "source", "apply_url", "run_id"):
        assert field in job, f"Missing job field: {field}"


def test_get_jobs_score_min_filter(client):
    c, engine = client
    _seed(engine)
    data = c.get("/jobs?score_min=80").json()
    all_jobs = [j for g in data for j in g["jobs"]]
    assert len(all_jobs) == 1
    assert all(j["score"] >= 80 for j in all_jobs)


def test_get_jobs_source_filter(client):
    c, engine = client
    _seed(engine)
    data = c.get("/jobs?source=lever").json()
    all_jobs = [j for g in data for j in g["jobs"]]
    assert all(j["source"] == "lever" for j in all_jobs)
    assert len(all_jobs) == 2


def test_get_jobs_company_filter_case_insensitive(client):
    c, engine = client
    _seed(engine)
    data = c.get("/jobs?company=stripe").json()
    all_jobs = [j for g in data for j in g["jobs"]]
    assert len(all_jobs) == 1
    assert all_jobs[0]["company"] == "Stripe"


def test_get_jobs_empty_db(client):
    c, _ = client
    data = c.get("/jobs").json()
    assert data == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_jobs_router.py -v
```

Expected: tests fail because `GET /jobs` still returns a flat list.

- [ ] **Step 3: Update the router**

Replace the `list_jobs` handler in `api/routers/jobs.py` (lines 13–40) with:

```python
@router.get("")
def list_jobs(
    score_min: int = 0,
    source: Optional[str] = None,
    company: Optional[str] = None,
    session: Session = Depends(get_session),
):
    groups = job_repo.list_jobs_grouped(
        session, score_min=score_min, source=source, company=company
    )
    return [
        {
            "run": {
                "id": run.id,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "jobs_fetched": run.jobs_fetched,
                "jobs_qualified": run.jobs_qualified,
                "jobs_rejected": run.jobs_rejected,
            },
            "jobs": [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "salary": j.salary,
                    "score": j.score,
                    "keyword_score": j.keyword_score,
                    "source": j.source,
                    "apply_url": j.apply_url,
                    "url": j.url,
                    "date_posted": j.date_posted,
                    "date_scraped": j.date_scraped,
                    "run_id": j.run_id,
                }
                for j in jobs
            ],
        }
        for run, jobs in groups
    ]
```

- [ ] **Step 4: Run all tests to confirm they pass**

```
uv run pytest tests/test_job_repo.py tests/test_jobs_router.py -v
```

Expected: 15 tests pass (7 from Task 1 + 8 new).

- [ ] **Step 5: Commit**

```bash
git add api/routers/jobs.py tests/test_jobs_router.py
git commit -m "feat: reshape GET /jobs to return jobs grouped by run"
```

---

### Task 3: Create `RunGroup.jsx` component

**Files:**
- Create: `frontend/src/components/RunGroup.jsx`

**Interfaces:**
- Props: `run` (object with `id`, `started_at`, `jobs_fetched`, `jobs_qualified`), `jobs` (array of job objects), `appliedIds` (Set\<number\>), `onApplied` (fn), `onJobClick` (fn taking job id), `defaultExpanded` (bool)
- Consumed by: `Jobs.jsx` (Task 4)

---

- [ ] **Step 1: Create the component**

Create `frontend/src/components/RunGroup.jsx`:

```jsx
import { useState } from 'react'
import JobCard from './JobCard'

function Chevron({ open }) {
  return (
    <svg
      className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

export default function RunGroup({ run, jobs, appliedIds, onApplied, onJobClick, defaultExpanded }) {
  const [open, setOpen] = useState(defaultExpanded)

  const date = new Date(run.started_at).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <div className="mb-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 py-2 px-2 -mx-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-left"
      >
        <Chevron open={open} />
        <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">
          Run #{run.id} — {date}
        </span>
        <span className="ml-1 text-xs font-medium bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded">
          {jobs.length} jobs
        </span>
        <span className="ml-auto text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
          {run.jobs_fetched} fetched · {run.jobs_qualified} qualified
        </span>
      </button>
      {open && (
        <div>
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              appliedIds={appliedIds}
              onApplied={onApplied}
              onClick={() => onJobClick(job.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Start the dev server and verify the component file has no syntax errors**

```
just api &
cd frontend && npm run dev
```

Open `http://localhost:5173`. The Jobs tab will not yet use `RunGroup` — confirm the page still loads without a white screen (no import errors from this new file).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/RunGroup.jsx
git commit -m "feat: add RunGroup collapsible component"
```

---

### Task 4: Update `Jobs.jsx` to consume grouped response

**Files:**
- Modify: `frontend/src/pages/Jobs.jsx`

**Interfaces:**
- Consumes: `GET /jobs` → `[{run, jobs}]` (from Task 2)
- Consumes: `RunGroup` component (from Task 3)

---

- [ ] **Step 1: Replace `Jobs.jsx`**

Overwrite `frontend/src/pages/Jobs.jsx` with:

```jsx
import { useEffect, useMemo, useState } from 'react'
import { getApplications, getJobs } from '../api/client'
import RunGroup from '../components/RunGroup'
import JobDetail from '../components/JobDetail'

export default function Jobs() {
  const [groups, setGroups] = useState([])
  const [appliedIds, setAppliedIds] = useState(new Set())
  const [selectedId, setSelectedId] = useState(null)
  const [filters, setFilters] = useState({ score_min: '', source: '', company: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getJobs(), getApplications()])
      .then(([groupData, apps]) => {
        setGroups(groupData)
        setAppliedIds(new Set(apps.map((a) => a.job_id)))
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const latestRunId = useMemo(() => groups[0]?.run?.id ?? null, [groups])

  const sources = useMemo(
    () => [...new Set(groups.flatMap((g) => g.jobs.map((j) => j.source)).filter(Boolean))],
    [groups]
  )

  const filtered = useMemo(() => {
    return groups
      .map((g) => ({
        run: g.run,
        jobs: g.jobs.filter((j) => {
          if (filters.score_min && j.score < Number(filters.score_min)) return false
          if (filters.source && j.source !== filters.source) return false
          if (filters.company && !j.company.toLowerCase().includes(filters.company.toLowerCase())) return false
          return true
        }),
      }))
      .filter((g) => g.jobs.length > 0)
  }, [groups, filters])

  const totalJobs = useMemo(
    () => filtered.reduce((sum, g) => sum + g.jobs.length, 0),
    [filtered]
  )

  const handleApplied = (jobId) => setAppliedIds((prev) => new Set([...prev, jobId]))

  return (
    <div>
      <div className="flex gap-3 mb-5 flex-wrap">
        <input
          type="number"
          placeholder="Min score"
          value={filters.score_min}
          onChange={(e) => setFilters((f) => ({ ...f, score_min: e.target.value }))}
          className="text-sm border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 w-28 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
        />
        <select
          value={filters.source}
          onChange={(e) => setFilters((f) => ({ ...f, source: e.target.value }))}
          className="text-sm border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
        >
          <option value="">All sources</option>
          {sources.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input
          type="text"
          placeholder="Company"
          value={filters.company}
          onChange={(e) => setFilters((f) => ({ ...f, company: e.target.value }))}
          className="text-sm border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 w-40 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
        />
        <span className="text-xs text-gray-400 dark:text-gray-500 self-center ml-auto">
          {totalJobs} jobs
        </span>
      </div>

      {loading && (
        <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading…</p>
      )}
      {!loading && filtered.length === 0 && (
        <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">
          No jobs found. Run <code>just search</code> to fetch jobs.
        </p>
      )}

      {filtered.map((g) => (
        <RunGroup
          key={g.run.id}
          run={g.run}
          jobs={g.jobs}
          appliedIds={appliedIds}
          onApplied={handleApplied}
          onJobClick={setSelectedId}
          defaultExpanded={g.run.id === latestRunId}
        />
      ))}

      {selectedId && (
        <JobDetail
          jobId={selectedId}
          appliedIds={appliedIds}
          onApplied={handleApplied}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify in the browser**

With `just dev` running, open `http://localhost:5173`.

Check these behaviors on the Jobs tab:
1. Jobs are grouped under run headers ("Run #N — Jun 28, 2026")
2. The latest run (highest #) is expanded; older runs are collapsed
3. Clicking a run header toggles it open/closed
4. Each header shows the correct job count pill and fetched/qualified stats
5. Setting a min score filter hides non-qualifying jobs within each group; groups with 0 matching jobs disappear
6. Setting a company filter shows only matching jobs; the job count updates
7. The source dropdown is populated from all jobs across all runs
8. Clicking a job card opens the `JobDetail` modal as before
9. The "Apply →" button still works

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Jobs.jsx
git commit -m "feat: update Jobs page to render jobs grouped by run"
```
