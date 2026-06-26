import { useState } from 'react'
import { createApplication } from '../api/client'

function ScoreBadge({ score }) {
  const cls =
    score >= 80 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' :
    score >= 60 ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300' :
                  'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
  return (
    <span className={`text-sm font-bold px-2 py-0.5 rounded ${cls}`}>{score}</span>
  )
}

export default function JobCard({ job, appliedIds, onApplied, onClick }) {
  const applied = appliedIds.has(job.id)
  const [applying, setApplying] = useState(false)

  const handleApply = async (e) => {
    e.stopPropagation()
    setApplying(true)
    try {
      await createApplication(job.id)
      onApplied(job.id)
    } catch (err) {
      if (err.status !== 409) alert(err.message)
      else onApplied(job.id)
    } finally {
      setApplying(false)
      window.open(job.apply_url, '_blank', 'noopener')
    }
  }

  return (
    <article
      onClick={onClick}
      className="flex items-center gap-4 py-4 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer px-2 -mx-2 rounded transition-colors"
    >
      <ScoreBadge score={job.score} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">{job.title}</span>
          <span className="text-xs text-gray-500 dark:text-gray-400">{job.company}</span>
        </div>
        <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 truncate">
          {[job.location, job.source, job.salary].filter(Boolean).join(' · ')}
        </div>
      </div>
      {applied ? (
        <a
          href={job.apply_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-xs font-medium text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900 px-2 py-1 rounded whitespace-nowrap hover:underline"
        >
          Applied ↗
        </a>
      ) : (
        <button
          onClick={handleApply}
          disabled={applying}
          className="text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded whitespace-nowrap disabled:opacity-50"
        >
          {applying ? '…' : 'Apply →'}
        </button>
      )}
    </article>
  )
}
