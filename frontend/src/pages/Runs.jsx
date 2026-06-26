import { useEffect, useState } from 'react'
import { getRuns } from '../api/client'

function fmt(iso) {
  if (!iso) return <span className="text-red-500 italic">crashed</span>
  return new Date(iso).toLocaleString()
}

export default function Runs() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getRuns().then(setRuns).catch(console.error).finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading…</p>
  if (!runs.length) return <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">No pipeline runs yet. Run <code>just search</code>.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400 font-medium">
            <th className="pb-2 pr-4">Started</th>
            <th className="pb-2 pr-4">Finished</th>
            <th className="pb-2 pr-4 text-right">Fetched</th>
            <th className="pb-2 pr-4 text-right">Qualified</th>
            <th className="pb-2 text-right">Rejected</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">
              <td className="py-3 pr-4 text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(run.started_at)}</td>
              <td className="py-3 pr-4 whitespace-nowrap">{fmt(run.finished_at)}</td>
              <td className="py-3 pr-4 text-right tabular-nums text-gray-700 dark:text-gray-300">{run.jobs_fetched}</td>
              <td className="py-3 pr-4 text-right tabular-nums text-green-700 dark:text-green-400 font-medium">{run.jobs_qualified}</td>
              <td className="py-3 text-right tabular-nums text-gray-500 dark:text-gray-400">{run.jobs_rejected}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
