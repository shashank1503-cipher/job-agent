import { updateApplication } from '../api/client'

const NEXT = {
  applied:      ['interviewing', 'rejected'],
  interviewing: ['offered', 'rejected'],
  offered:      [],
  rejected:     [],
}

export default function StatusDropdown({ app, onUpdated }) {
  const options = NEXT[app.status] ?? []
  if (!options.length) return <span className="text-xs text-gray-400 dark:text-gray-500 italic">terminal</span>

  const handleChange = async (e) => {
    const newStatus = e.target.value
    if (!newStatus) return
    try {
      const updated = await updateApplication(app.id, { status: newStatus })
      onUpdated(updated)
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <select
      defaultValue=""
      onChange={handleChange}
      className="text-xs border border-gray-300 dark:border-gray-600 rounded px-1.5 py-0.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
    >
      <option value="" disabled>Move to…</option>
      {options.map((s) => (
        <option key={s} value={s}>{s}</option>
      ))}
    </select>
  )
}
