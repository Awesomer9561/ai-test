import { useState, useEffect } from 'react'
import { loginOrCreate, listUsers, type UserProfile } from '@/api/client'
import { useUserStore } from '@/store/userStore'

const EXAM_OPTIONS = ['IBPS PO', 'IBPS Clerk', 'IBPS RRB', 'SBI PO', 'SBI Clerk', 'Custom']

export default function Login() {
  const setUser = useUserStore(s => s.setUser)
  const [name, setName] = useState('')
  const [examTarget, setExamTarget] = useState('IBPS PO')
  const [existingUsers, setExistingUsers] = useState<UserProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listUsers().then(setExistingUsers).catch(() => {})
  }, [])

  const handleLogin = async () => {
    if (!name.trim()) {
      setError('Please enter your name')
      return
    }
    setLoading(true)
    setError('')
    try {
      const user = await loginOrCreate(name.trim(), examTarget)
      setUser(user)
    } catch {
      setError('Failed to connect. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const handleQuickLogin = async (user: UserProfile) => {
    setUser(user)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">IBPS Adaptive Test</h1>
          <p className="text-gray-500 mt-2">AI-powered practice for banking exams</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Enter your name to start</h2>

          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            placeholder="Your name"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none text-lg"
            autoFocus
          />

          <select
            value={examTarget}
            onChange={e => setExamTarget(e.target.value)}
            className="w-full mt-3 px-4 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-700"
          >
            {EXAM_OPTIONS.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>

          <button
            onClick={handleLogin}
            disabled={loading || !name.trim()}
            className="w-full mt-4 py-3 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {loading ? 'Loading...' : 'Continue'}
          </button>

          {error && <p className="mt-3 text-red-600 text-sm">{error}</p>}
        </div>

        {/* Quick login for existing users */}
        {existingUsers.length > 0 && (
          <div className="mt-6">
            <p className="text-xs text-gray-400 uppercase font-semibold mb-2 text-center">
              Or continue as
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {existingUsers.map(user => (
                <button
                  key={user.id}
                  onClick={() => handleQuickLogin(user)}
                  className="px-4 py-2 rounded-full border border-gray-200 bg-white text-sm text-gray-700 hover:border-blue-400 hover:text-blue-600 transition"
                >
                  {user.name}
                  <span className="text-xs text-gray-400 ml-1">({user.exam_target})</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
