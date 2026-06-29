# Jobs Grouped by Run — Design Spec

**Date:** 2026-06-29

## Problem

The Jobs tab renders a flat list of all jobs across all pipeline runs. There is no way to tell which jobs came from which run, making it hard to compare runs or focus on the latest results.

## Goal

Partition the Jobs view by pipeline run: each run gets a collapsible section header, with its jobs listed underneath. The latest run is expanded by default; older runs are collapsed.

## Constraints

- Existing filters (score_min, source, company) must continue to work across all runs
- No new API endpoints — reshape `GET /jobs` in place
- `GET /jobs/{id}` is untouched

---

## Backend

### `job_repo.list_jobs_grouped`

New function replacing `list_jobs` for the list endpoint. Issues 2 DB queries:

1. Fetch all `Run` rows ordered `started_at DESC`
2. Fetch all `Job` rows with filters applied, ordered `score DESC`

Group jobs by `run_id` in Python, return `list[tuple[Run, list[Job]]]`.

Query params supported: `score_min` (int, default 0), `source` (str, optional), `company` (str, optional, ilike match).

### `GET /jobs` response shape

Changes from a flat `Job[]` to a grouped array:

```json
[
  {
    "run": {
      "id": 12,
      "started_at": "2026-06-28T10:00:00",
      "finished_at": "2026-06-28T10:05:00",
      "jobs_fetched": 42,
      "jobs_qualified": 18,
      "jobs_rejected": 24
    },
    "jobs": [
      { "id": 1, "title": "...", "company": "...", "score": 85, ... }
    ]
  }
]
```

Runs with no jobs (after filtering) are still included in the response; the frontend hides them.

---

## Frontend

### `client.js`

No changes. `getJobs(params)` passes query params and returns the API response as-is.

### `RunGroup.jsx` (new component)

Props: `run`, `jobs`, `appliedIds`, `onApplied`, `onJobClick`, `defaultExpanded`.

Renders:
- **Header** (clickable): chevron icon + "Run #`{id}` — `{date}`" + `N jobs` pill (count of jobs passed in) + muted stats ("42 fetched · 18 qualified")
- **Body**: list of `JobCard` components, shown when expanded, hidden when collapsed
- Collapsed by default unless `defaultExpanded` is true

### `Jobs.jsx` (updated)

- State: `groups` (`{run, jobs}[]`) instead of `jobs`
- `expandedRuns`: `Set<number>` initialized with the latest run's `id`
- `sources`: derived by flattening `groups.flatMap(g => g.jobs.map(j => j.source))`
- `filtered`: `useMemo` that filters each group's `jobs` array — groups with 0 matching jobs are excluded from render
- Renders `RunGroup` per filtered group, passing `defaultExpanded={expandedRuns.has(run.id)}`
- Job count label shows total across all visible groups

---

## Data Flow

```
GET /jobs?score_min=&source=&company=
        │
        ▼
job_repo.list_jobs_grouped()
  → 2 SQL queries (runs + filtered jobs)
  → grouped in Python
        │
        ▼
Router serializes [{run, jobs}]
        │
        ▼
Jobs.jsx receives groups
  → useMemo filters jobs within each group
  → renders RunGroup per non-empty group
        │
        ▼
RunGroup: collapsible header + JobCard list
```

---

## Out of Scope

- Pagination (acceptable at current scale)
- Persisting expanded/collapsed state across page loads
- Clicking a run in the Runs tab to navigate to its jobs
