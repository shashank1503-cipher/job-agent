const STYLES = {
  applied:      'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
  interviewing: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
  offered:      'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
  rejected:     'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300',
}

export default function StatusBadge({ status }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STYLES[status] ?? 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'}`}>
      {status}
    </span>
  )
}
