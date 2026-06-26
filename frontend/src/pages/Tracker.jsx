import { useEffect, useState } from 'react'
import { getApplications, updateApplication } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import StatusDropdown from '../components/StatusDropdown'

export default function Tracker() {
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getApplications()
      .then(setApps)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleStatusUpdate = (updated) => {
    setApps((prev) => prev.map((a) => (a.id === updated.id ? { ...a, status: updated.status } : a)))
  }

  const handleNotesBlur = async (app, notes) => {
    if (notes === app.notes) return
    try {
      await updateApplication(app.id, { notes })
      setApps((prev) => prev.map((a) => (a.id === app.id ? { ...a, notes } : a)))
    } catch (err) {
      alert(err.message)
    }
  }

  if (loading) return <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading…</p>
  if (!apps.length) return <p className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">No applications yet. Apply to jobs from the Jobs tab.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400 font-medium">
            <th className="pb-2 pr-4">Job</th>
            <th className="pb-2 pr-4">Company</th>
            <th className="pb-2 pr-4">Applied</th>
            <th className="pb-2 pr-4">Status</th>
            <th className="pb-2 pr-4">Next step</th>
            <th className="pb-2">Notes</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((app) => (
            <tr key={app.id} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">
              <td className="py-3 pr-4 font-medium text-gray-900 dark:text-gray-100 max-w-[200px]">
                <a
                  href={app.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:underline flex items-center gap-1 truncate"
                  title={app.title}
                >
                  <span className="truncate">{app.title}</span>
                  <span className="shrink-0 text-gray-400 dark:text-gray-500 text-xs">↗</span>
                </a>
              </td>
              <td className="py-3 pr-4 text-gray-600 dark:text-gray-400">{app.company}</td>
              <td className="py-3 pr-4 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                {new Date(app.applied_at).toLocaleDateString()}
              </td>
              <td className="py-3 pr-4">
                <StatusBadge status={app.status} />
              </td>
              <td className="py-3 pr-4">
                <StatusDropdown app={app} onUpdated={handleStatusUpdate} />
              </td>
              <td className="py-3">
                <input
                  type="text"
                  defaultValue={app.notes ?? ''}
                  placeholder="Add notes…"
                  onBlur={(e) => handleNotesBlur(app, e.target.value)}
                  className="text-xs border border-transparent hover:border-gray-300 dark:hover:border-gray-600 focus:border-gray-400 dark:focus:border-gray-500 rounded px-2 py-1 w-full focus:outline-none bg-transparent text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600"
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
