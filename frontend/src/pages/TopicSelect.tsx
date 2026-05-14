import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchSubjects, startTest } from '@/api/client'
import { useTestStore } from '@/store/testStore'
import { useUserStore } from '@/store/userStore'

const MODES = [
  { key: 'quick', label: 'Quick (10Q / 10min)', questions: 10, seconds: 600 },
  { key: 'standard', label: 'Standard (30Q / 30min)', questions: 30, seconds: 1800 },
  { key: 'custom', label: 'Custom', questions: 10, seconds: 600 },
]

const CATEGORY_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  banking: { bg: 'bg-blue-100', text: 'text-blue-700', label: '🏦 Banking' },
  ug_entrance: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: '🎓 UG Entrance' },
}

export default function TopicSelect() {
  const navigate = useNavigate()
  const location = useLocation()
  const initTest = useTestStore(s => s.initTest)
  const user = useUserStore(s => s.user)

  const examCategory = user?.exam_category ?? 'banking'

  const preselected = (location.state as { topicIds?: number[]; mode?: string } | null)
  const [selectedTopics, setSelectedTopics] = useState<number[]>(preselected?.topicIds ?? [])
  const [mode, setMode] = useState(preselected?.mode ?? 'quick')

  // Fetch only subjects that match the user's exam category
  const { data: subjects, isLoading } = useQuery({
    queryKey: ['subjects', examCategory],
    queryFn: () => fetchSubjects(examCategory),
  })

  const startMutation = useMutation({
    mutationFn: startTest,
    onSuccess: (test) => {
      initTest(test.id)
      navigate(`/test/${test.id}`, { state: { test } })
    },
  })

  const toggleTopic = (id: number) => {
    setSelectedTopics(prev =>
      prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
    )
  }

  const toggleSubject = (topicIds: number[]) => {
    const allSelected = topicIds.every(id => selectedTopics.includes(id))
    if (allSelected) {
      setSelectedTopics(prev => prev.filter(id => !topicIds.includes(id)))
    } else {
      setSelectedTopics(prev => [...new Set([...prev, ...topicIds])])
    }
  }

  const selectedMode = MODES.find(m => m.key === mode)!
  const badge = CATEGORY_BADGE[examCategory] ?? CATEGORY_BADGE.banking

  const handleStart = () => {
    if (selectedTopics.length === 0 || !user) return
    startMutation.mutate({
      user_id: user.id,
      topic_ids: selectedTopics,
      mode,
      num_questions: selectedMode.questions,
      duration_seconds: selectedMode.seconds,
    })
  }

  if (isLoading) {
    return <div className="text-center py-20 text-gray-500">Loading subjects...</div>
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold">Start a New Test</h1>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${badge.bg} ${badge.text}`}>
          {badge.label}
        </span>
        {user && (
          <span className="text-sm text-gray-400 ml-auto">{user.exam_target}</span>
        )}
      </div>

      {/* Pre-selected banner */}
      {preselected?.topicIds && preselected.topicIds.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-6 flex items-center justify-between">
          <p className="text-sm text-indigo-700">
            <strong>{preselected.topicIds.length} weak topic{preselected.topicIds.length > 1 ? 's' : ''}</strong> pre-selected from your Dashboard. Hit start or adjust below.
          </p>
          <button
            onClick={() => setSelectedTopics([])}
            className="text-xs text-indigo-500 hover:text-indigo-700 underline shrink-0 ml-4"
          >
            Clear selection
          </button>
        </div>
      )}

      {/* Mode selector */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">Test Mode</h2>
        <div className="flex gap-3 flex-wrap">
          {MODES.map(m => (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              className={`px-4 py-2 rounded-lg border text-sm font-medium transition ${
                mode === m.key
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-brand-500'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Subject/topic tree — shows only subjects for the user's exam category */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">
          Select Topics ({selectedTopics.length} selected)
        </h2>
        {subjects && subjects.length === 0 && (
          <p className="text-gray-400 text-sm">
            No subjects found for your exam category. Please check the backend is running and database is seeded.
          </p>
        )}
        <div className="space-y-4">
          {subjects?.map(subject => {
            const topicIds = subject.topics.map(t => t.id)
            const allSelected = topicIds.length > 0 && topicIds.every(id => selectedTopics.includes(id))
            const someSelected = topicIds.some(id => selectedTopics.includes(id))

            return (
              <div key={subject.id} className="bg-white rounded-lg border border-gray-200 p-4">
                <label className="flex items-center gap-3 cursor-pointer mb-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={el => { if (el) el.indeterminate = someSelected && !allSelected }}
                    onChange={() => toggleSubject(topicIds)}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <span className="font-semibold text-gray-900">{subject.name}</span>
                  <span className="text-xs text-gray-400">({subject.topics.length} topics)</span>
                </label>
                <div className="ml-7 flex flex-wrap gap-2">
                  {subject.topics.map(topic => (
                    <label
                      key={topic.id}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm cursor-pointer border transition ${
                        selectedTopics.includes(topic.id)
                          ? examCategory === 'ug_entrance'
                            ? 'bg-emerald-50 border-emerald-500 text-emerald-700'
                            : 'bg-brand-50 border-brand-500 text-brand-700'
                          : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTopics.includes(topic.id)}
                        onChange={() => toggleTopic(topic.id)}
                        className="sr-only"
                      />
                      {topic.name}
                    </label>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Start button */}
      <button
        onClick={handleStart}
        disabled={selectedTopics.length === 0 || startMutation.isPending}
        className={`w-full py-3 rounded-lg text-white font-semibold text-lg disabled:opacity-50 disabled:cursor-not-allowed transition ${
          examCategory === 'ug_entrance'
            ? 'bg-emerald-600 hover:bg-emerald-700'
            : 'bg-brand-600 hover:bg-brand-700'
        }`}
      >
        {startMutation.isPending
          ? 'Starting…'
          : `Start Test (${selectedMode.questions} questions, ${selectedMode.seconds / 60} min)`}
      </button>

      {startMutation.isError && (
        <p className="mt-3 text-red-600 text-sm">
          Failed to start test. Make sure the backend is running on port 8001.
        </p>
      )}
    </div>
  )
}
