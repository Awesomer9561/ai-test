import { useState } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import { useUserStore } from './store/userStore'
import Login from './pages/Login'
import TopicSelect from './pages/TopicSelect'
import TestPage from './pages/TestPage'
import ResultPage from './pages/ResultPage'
import Dashboard from './pages/Dashboard'

export default function App() {
  const user = useUserStore(s => s.user)
  const logout = useUserStore(s => s.logout)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)

  if (!user) {
    return <Login />
  }

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
        <Link to="/" className="text-xl font-bold text-blue-700">
          Adaptive Test
        </Link>
        <Link to="/" className="text-sm text-gray-600 hover:text-blue-600">
          New Test
        </Link>
        <Link to="/dashboard" className="text-sm text-gray-600 hover:text-blue-600">
          Dashboard
        </Link>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-sm text-gray-500">
            {user.name} <span className="text-xs text-gray-400">({user.exam_target})</span>
          </span>
          <button
            onClick={() => setShowLogoutConfirm(true)}
            className="text-xs text-gray-400 hover:text-red-500 transition"
          >
            Switch
          </button>
        </div>
      </nav>

      {/* Pages */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<TopicSelect />} />
          <Route path="/test/:testId" element={<TestPage />} />
          <Route path="/result/:testId" element={<ResultPage />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </main>

      {/* Logout confirmation modal */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4">
            <h2 className="text-base font-semibold text-gray-800 mb-2">Switch user?</h2>
            <p className="text-sm text-gray-500 mb-5">
              Your progress is saved. You can resume this session by logging back in.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="px-4 py-2 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Stay
              </button>
              <button
                onClick={() => { logout(); setShowLogoutConfirm(false) }}
                className="px-4 py-2 text-sm rounded bg-red-600 text-white hover:bg-red-700"
              >
                Switch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
