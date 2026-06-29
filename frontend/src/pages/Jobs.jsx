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
