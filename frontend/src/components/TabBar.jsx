export default function TabBar({ tabs, active, onChange }) {
  return (
    <nav className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-5xl mx-auto px-4 flex gap-1">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => onChange(tab)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              active === tab
                ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>
    </nav>
  )
}
