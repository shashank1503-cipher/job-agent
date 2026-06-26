import { useEffect, useState } from 'react'
import TabBar from './components/TabBar'
import Jobs from './pages/Jobs'
import Runs from './pages/Runs'
import Tracker from './pages/Tracker'

const TABS = ['Jobs', 'Tracker', 'Runs']

function useDark() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('dark')
    if (stored !== null) return stored === 'true'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('dark', dark)
  }, [dark])

  return [dark, setDark]
}

export default function App() {
  const [tab, setTab] = useState('Jobs')
  const [dark, setDark] = useDark()

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-5xl mx-auto px-4 pt-4 pb-0">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-base font-bold text-gray-800 dark:text-gray-100">Job Agent</h1>
            <button
              onClick={() => setDark((d) => !d)}
              className="text-sm px-2 py-1 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Toggle dark mode"
            >
              {dark ? '☀' : '☾'}
            </button>
          </div>
          <TabBar tabs={TABS} active={tab} onChange={setTab} />
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-6">
        {tab === 'Jobs' && <Jobs />}
        {tab === 'Tracker' && <Tracker />}
        {tab === 'Runs' && <Runs />}
      </main>
    </div>
  )
}
