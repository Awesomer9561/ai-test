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
            onClick={logout}
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
    </div>
  )
}
