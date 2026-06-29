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
