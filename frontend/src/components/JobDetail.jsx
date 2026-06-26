import { useEffect, useState } from 'react'
import { createApplication, getJob } from '../api/client'

function ScoreBadge({ score }) {
  const cls =
    score >= 80 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' :
    score >= 60 ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300' :
                  'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
  return <span className={`font-bold px-2 py-0.5 rounded text-sm ${cls}`}>{score}</span>
}

function ScoreBar({ label, value, max }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  const barColor =
    value === max ? 'bg-green-500 dark:bg-green-400' :
    value > 0     ? 'bg-yellow-400 dark:bg-yellow-300' :
                    'bg-red-300 dark:bg-red-600'
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-32 shrink-0 text-gray-600 dark:text-gray-400">{label}</span>
      <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 shrink-0 text-right tabular-nums text-gray-500 dark:text-gray-400">
        {value}/{max}
      </span>
    </div>
  )
}

export default function JobDetail({ jobId, appliedIds, onApplied, onClose }) {
  const [job, setJob] = useState(null)
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    getJob(jobId).then(setJob).catch(console.error)
  }, [jobId])

  const applied = appliedIds.has(jobId)

  const handleApply = async () => {
    setApplying(true)
    try {
      await createApplication(jobId)
      onApplied(jobId)
    } catch (err) {
      if (err.status !== 409) alert(err.message)
      else onApplied(jobId)
    } finally {
      setApplying(false)
      window.open(job.apply_url, '_blank', 'noopener')
    }
  }

  const ma = job?.score_breakdown

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between p-6 border-b border-gray-100 dark:border-gray-700">
          <div>
            <h2 className="font-bold text-lg text-gray-900 dark:text-gray-100">{job?.title ?? '…'}</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{job?.company} · {job?.location}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none ml-4">✕</button>
        </div>

        {job && (
          <div className="overflow-y-auto flex-1 p-6 space-y-5">
            <div className="flex items-center gap-2">
              <ScoreBadge score={job.score} />
            </div>

            {job.salary && (
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Salary: {job.salary}</p>
            )}

            <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed border-t border-gray-100 dark:border-gray-700 pt-4">
              {job.description}
            </div>

            {/* Section 1: Score Breakdown */}
            {ma && (
              <div className="border-t border-gray-100 dark:border-gray-700 pt-4 space-y-2.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-3">Score Breakdown</p>
                <ScoreBar label="BM25 Recall"   value={ma.bm25_score}      max={30} />
                <ScoreBar label="JobBERT"        value={ma.jobbert_score}   max={40} />
                <ScoreBar label="Title match"    value={ma.title_score}    max={10} />
                <ScoreBar label="Industry"       value={ma.industry_score} max={10} />
                <ScoreBar label="Location"       value={ma.location_score} max={10} />
              </div>
            )}

            {/* Section 2: Keywords */}
            {ma && (ma.strengths?.length > 0 || ma.missing_keywords?.length > 0) && (
              <div className="border-t border-gray-100 dark:border-gray-700 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-3">Keywords</p>
                <div className="flex flex-wrap gap-2">
                  {ma.strengths?.map((s) => (
                    <span key={s} className="text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-0.5 rounded">{s}</span>
                  ))}
                  {ma.missing_keywords?.map((k) => (
                    <span key={k} className="text-xs bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-400 px-2 py-0.5 rounded">✗ {k}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="p-4 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 px-3 py-1.5">Close</button>
          {applied ? (
            <span className="text-sm font-medium text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900 px-3 py-1.5 rounded">Applied</span>
          ) : (
            <button
              onClick={handleApply}
              disabled={applying || !job}
              className="text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 px-4 py-1.5 rounded disabled:opacity-50"
            >
              {applying ? 'Opening…' : 'Apply →'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
