import { useEffect, useMemo, useState } from 'react'
import { getApplications, getJobs } from '../api/client'
import JobCard from '../components/JobCard'
import JobDetail from '../components/JobDetail'

export default function Jobs() {
  const [jobs, setJobs] = useState([])
  const [appliedIds, setAppliedIds] = useState(new Set())
  const [selectedId, setSelectedId] = useState(null)
  const [filters, setFilters] = useState({ score_min: '', source: '', company: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getJobs(), getApplications()]).then(([j, apps]) => {
      setJobs(j)
      setAppliedIds(new Set(apps.map((a) => a.job_id)))
    }).catch(console.error).finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    return jobs.filter((j) => {
      if (filters.score_min && j.score < Number(filters.score_min)) return false
      if (filters.source && j.source !== filters.source) return false
      if (filters.company && !j.company.toLowerCase().includes(filters.company.toLowerCase())) return false
      return true
    })
  }, [jobs, filters])

  const sources = useMemo(() => [...new Set(jobs.map((j) => j.source).filter(Boolean))], [jobs])

  const handleApplied = (jobId) => setAppliedIds((prev) => new Set([...prev, jobId]))

  return (
    <div>
      {/* Filters */}
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
        <span className="text-xs text-gray-400 dark:text-gray-500 self-center ml-auto">{filtered.length} jobs</span>
      </div>

      {loading && <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading…</p>}
      {!loading && filtered.length === 0 && (
        <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">No jobs found. Run <code>just search</code> to fetch jobs.</p>
      )}

      {filtered.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          appliedIds={appliedIds}
          onApplied={handleApplied}
          onClick={() => setSelectedId(job.id)}
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
