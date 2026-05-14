import { useState, useEffect } from 'react'
import { loginOrCreate, fetchExamList, type ExamList } from '@/api/client'
import { useUserStore } from '@/store/userStore'

const CATEGORY_LABELS: Record<string, string> = {
  banking: 'Banking Exams',
  ug_entrance: 'UG Entrance Exams',
}

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  banking: 'IBPS PO, SBI PO, RRB & more',
  ug_entrance: 'JEE Main, JEE Advanced, WBJEE, CUET',
}

const CATEGORY_COLORS: Record<string, string> = {
  banking: 'blue',
  ug_entrance: 'emerald',
}

export default function Login() {
  const setUser = useUserStore(s => s.setUser)
  const [name, setName] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<'banking' | 'ug_entrance'>('banking')
  const [examTarget, setExamTarget] = useState('IBPS PO')
  const [examList, setExamList] = useState<ExamList>({ banking: [], ug_entrance: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchExamList().then(setExamList).catch(() => {
      setExamList({
        banking: ['IBPS PO', 'IBPS Clerk', 'IBPS RRB', 'SBI PO', 'SBI Clerk'],
        ug_entrance: ['JEE Main', 'JEE Advanced', 'WBJEE', 'CUET'],
      })
    })
  }, [])

  // When category changes, reset exam target to the first option in that category
  const handleCategoryChange = (cat: 'banking' | 'ug_entrance') => {
    setSelectedCategory(cat)
    const options = examList[cat]
    if (options.length > 0) setExamTarget(options[0])
  }

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

  const currentOptions = examList[selectedCategory] ?? []
  const blueActive = selectedCategory === 'banking'
  const greenActive = selectedCategory === 'ug_entrance'

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Adaptive Test Platform</h1>
          <p className="text-gray-500 mt-2">AI-powered practice for Banking & UG Entrance exams</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          {/* Exam category toggle */}
          <div className="mb-5">
            <p className="text-sm font-semibold text-gray-500 uppercase mb-3">Choose Exam Category</p>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleCategoryChange('banking')}
                className={`flex flex-col items-center p-4 rounded-xl border-2 transition text-left ${
                  blueActive
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                }`}
              >
                <span className="text-2xl mb-1">🏦</span>
                <span className={`font-semibold text-sm ${blueActive ? 'text-blue-700' : 'text-gray-700'}`}>
                  Banking Exams
                </span>
                <span className={`text-xs mt-0.5 ${blueActive ? 'text-blue-500' : 'text-gray-400'}`}>
                  IBPS, SBI, RRB
                </span>
              </button>

              <button
                onClick={() => handleCategoryChange('ug_entrance')}
                className={`flex flex-col items-center p-4 rounded-xl border-2 transition text-left ${
                  greenActive
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                }`}
              >
                <span className="text-2xl mb-1">🎓</span>
                <span className={`font-semibold text-sm ${greenActive ? 'text-emerald-700' : 'text-gray-700'}`}>
                  UG Entrance
                </span>
                <span className={`text-xs mt-0.5 ${greenActive ? 'text-emerald-500' : 'text-gray-400'}`}>
                  JEE, WBJEE, CUET
                </span>
              </button>
            </div>
          </div>

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

          {/* Exam target dropdown filtered to selected category */}
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-1.5">
              {CATEGORY_LABELS[selectedCategory]} — {CATEGORY_DESCRIPTIONS[selectedCategory]}
            </p>
            <select
              value={examTarget}
              onChange={e => setExamTarget(e.target.value)}
              className={`w-full px-4 py-2.5 rounded-lg border text-sm ${
                blueActive
                  ? 'border-blue-200 text-blue-800 bg-blue-50'
                  : 'border-emerald-200 text-emerald-800 bg-emerald-50'
              }`}
            >
              {currentOptions.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>

          <button
            onClick={handleLogin}
            disabled={loading || !name.trim()}
            className={`w-full mt-4 py-3 rounded-lg text-white font-semibold disabled:opacity-50 transition ${
              blueActive
                ? 'bg-blue-600 hover:bg-blue-700'
                : 'bg-emerald-600 hover:bg-emerald-700'
            }`}
          >
            {loading ? 'Loading...' : 'Continue →'}
          </button>

          {error && <p className="mt-3 text-red-600 text-sm">{error}</p>}
        </div>

      </div>
    </div>
  )
}
