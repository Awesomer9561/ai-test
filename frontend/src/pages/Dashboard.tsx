import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchHealth, pingOllama, fetchSkills, startTest, fetchInProgressTest, type UserSkill } from '@/api/client'
import { useTestStore } from '@/store/testStore'
import { useUserStore } from '@/store/userStore'
import { useState, useEffect } from 'react'

export default function Dashboard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initTest = useTestStore(s => s.initTest)
  const user = useUserStore(s => s.user)
  const [ollamaResult, setOllamaResult] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [adaptiveLoading, setAdaptiveLoading] = useState(false)
  const [adaptiveError, setAdaptiveError] = useState('')

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
  })

  const { data: skills } = useQuery({
    queryKey: ['skills', user?.id],
    queryFn: () => fetchSkills(user!.id),
    enabled: !!user,
  })

  const { data: inProgress } = useQuery({
    queryKey: ['inProgress', user?.id],
    queryFn: () => fetchInProgressTest(user!.id),
    enabled: !!user,
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  })

  // Auto-redirect to very recent in-progress test (< 5 min ago)
  useEffect(() => {
    if (!inProgress?.has_test || !inProgress.test_id) return
    if (inProgress.remaining_ms <= 0) return
    const elapsed = (inProgress.remaining_ms > 0 && inProgress.total_questions > 0)
      ? (inProgress.total_questions > 0 ? true : false)
      : false
    // Redirect if < 5 min of session time has elapsed (remaining ≈ full duration)
    // We detect "< 5 min ago" by checking if remaining_ms is close to a typical test duration
    // The simplest proxy: if remaining_ms implies the test started less than 5 min ago
    const startedAt = inProgress.started_at ? new Date(inProgress.started_at).getTime() : 0
    const elapsedSinceStart = Date.now() - startedAt
    if (elapsedSinceStart < 5 * 60 * 1000) {
      navigate(`/test/${inProgress.test_id}`)
    }
  }, [inProgress])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefreshAll = async () => {
    setRefreshing(true)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['health'] }),
      queryClient.invalidateQueries({ queryKey: ['skills'] }),
    ])
    setRefreshing(false)
  }

  const handlePingOllama = async () => {
    setOllamaResult('Pinging...')
    try {
      const res = await pingOllama()
      setOllamaResult(res.success ? `✅ ${res.ollama_response}` : `❌ ${res.ollama_response}`)
    } catch {
      setOllamaResult('❌ Failed to reach backend')
    }
  }

  const handleStartAdaptive = async () => {
    if (!user) return
    setAdaptiveError('')
    setAdaptiveLoading(true)
    try {
      const test = await startTest({
        user_id: user.id,
        topic_ids: [],       // backend auto-selects based on weak areas
        mode: 'adaptive',
        num_questions: 10,
        duration_seconds: 600,
      })
      initTest(test.id)
      navigate(`/test/${test.id}`, { state: { test } })
    } catch {
      setAdaptiveError('Failed to generate adaptive test. Make sure Ollama is running.')
    } finally {
      setAdaptiveLoading(false)
    }
  }

  // Derive insights from skills
  const weakTopics = skills?.filter(s => s.mastery_score < 0.4) ?? []
  const slowTopics = skills?.filter(s => s.avg_time_ms > 45_000) ?? []
  const lowAccuracyTopics = skills?.filter(s => s.accuracy < 0.5) ?? []

  // High-performer detection (mirrors backend threshold)
  const isHighPerformer = skills && skills.length >= 3
    ? (skills.filter(s => s.mastery_score >= 0.7).length / skills.length) >= 0.6
    : false

  const studyNext = skills
    ? [...skills]
        .sort((a, b) => a.mastery_score - b.mastery_score || a.accuracy - b.accuracy)
        .slice(0, 3)
    : []

  return (
    <div>
      {/* ── Full-page loading overlay while adaptive test is being generated ── */}
      {adaptiveLoading && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl p-10 text-center max-w-sm mx-4">
            <div className="flex justify-center mb-6">
              <div className="w-14 h-14 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Building your adaptive test…</h2>
            <p className="text-sm text-gray-500 leading-relaxed">
              Analysing your weak areas and generating custom questions with AI.
              <br />
              This usually takes <strong>30–60 seconds</strong>.
            </p>
          </div>
        </div>
      )}

      {/* ── In-progress test banner ── */}
      {inProgress?.has_test && inProgress.test_id && inProgress.remaining_ms > 0 && (() => {
        const startedAt = inProgress.started_at ? new Date(inProgress.started_at).getTime() : 0
        const elapsedSinceStart = Date.now() - startedAt
        // Only show banner if > 5 min since start (< 5 min triggers auto-redirect above)
        if (elapsedSinceStart < 5 * 60 * 1000) return null
        const remMin = Math.ceil(inProgress.remaining_ms / 60000)
        return (
          <div className="bg-indigo-50 border border-indigo-300 rounded-xl p-4 mb-6 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="font-semibold text-indigo-800">You have an unfinished test</p>
              <p className="text-sm text-indigo-600 mt-0.5">
                {inProgress.answers_saved}/{inProgress.total_questions} answered · {remMin} min remaining
              </p>
            </div>
            <button
              onClick={() => navigate(`/test/${inProgress.test_id}`)}
              className="shrink-0 px-4 py-2 rounded-lg bg-indigo-600 text-white font-semibold text-sm hover:bg-indigo-700"
            >
              Resume
            </button>
          </div>
        )
      })()}

      {inProgress?.has_test && inProgress.test_id && inProgress.remaining_ms <= 0 && (
        <div className="bg-gray-100 border border-gray-300 rounded-xl p-4 mb-6 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-gray-600">Your previous test session expired.</p>
          <button
            onClick={() => navigate(`/result/${inProgress.test_id}`)}
            className="shrink-0 px-4 py-2 rounded-lg bg-gray-700 text-white text-sm hover:bg-gray-800"
          >
            View Results
          </button>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <button
          onClick={handleRefreshAll}
          disabled={refreshing}
          className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 flex items-center gap-2"
        >
          <span className={refreshing ? 'animate-spin inline-block' : ''}>&#8635;</span>
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {/* ── Adaptive test CTA ── */}
      <div className={`bg-gradient-to-r ${isHighPerformer ? 'from-orange-50 to-amber-50 border-orange-200' : 'from-blue-50 to-indigo-50 border-blue-200'} border rounded-xl p-5 mb-6`}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2">
              <h2 className={`text-lg font-semibold ${isHighPerformer ? 'text-orange-800' : 'text-blue-800'}`}>
                Adaptive Test
              </h2>
              {isHighPerformer && (
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 border border-orange-300">
                  🔥 Challenge Mode
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 mt-0.5">
              {!skills || skills.length === 0
                ? 'Complete a regular test first to unlock personalised generation.'
                : isHighPerformer
                  ? "You're performing at an advanced level. Your test will focus on pushing your strongest topics harder with difficulty 4–5 questions."
                  : `AI analyses your ${weakTopics.length > 0 ? weakTopics.length + ' weak area(s)' : 'skills'} and generates a personalised 10-question test.`}
            </p>
            {adaptiveError && <p className="text-sm text-red-600 mt-1">{adaptiveError}</p>}
          </div>
          <button
            onClick={handleStartAdaptive}
            disabled={adaptiveLoading}
            className={`shrink-0 px-5 py-2.5 rounded-lg text-white font-semibold disabled:opacity-50 transition ${
              isHighPerformer ? 'bg-orange-600 hover:bg-orange-700' : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {adaptiveLoading ? 'Generating…' : isHighPerformer ? 'Start Challenge Test' : 'Start Adaptive Test'}
          </button>
        </div>
      </div>

      {/* Skill heatmap */}
      {skills && skills.length > 0 && (
        <div className="bg-white rounded-lg border p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Skill Mastery</h2>
          <div className="space-y-3">
            {skills.map(skill => {
              const pct = Math.round(skill.mastery_score * 100)
              const color =
                pct >= 70 ? 'bg-green-500' :
                pct >= 40 ? 'bg-yellow-500' :
                'bg-red-500'
              const bgColor =
                pct >= 70 ? 'bg-green-50' :
                pct >= 40 ? 'bg-yellow-50' :
                'bg-red-50'
              return (
                <div key={skill.topic_id} className={`rounded-lg p-3 ${bgColor}`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-medium">{skill.topic_name}</span>
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>Accuracy: {Math.round(skill.accuracy * 100)}%</span>
                      <span>Avg: {Math.round(skill.avg_time_ms / 1000)}s</span>
                      <span className="font-semibold">{pct}%</span>
                    </div>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${color}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {(!skills || skills.length === 0) && (
        <div className="bg-white rounded-lg border p-6 mb-6">
          <h2 className="text-lg font-semibold mb-2">Skill Mastery</h2>
          <p className="text-gray-400 text-sm">Take a test and submit it to see your mastery scores here.</p>
        </div>
      )}

      {/* Areas Needing Attention */}
      {skills && skills.length > 0 && (weakTopics.length > 0 || slowTopics.length > 0 || lowAccuracyTopics.length > 0) && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-semibold text-red-800 mb-3">Areas Needing Attention</h2>
          <div className="space-y-2 text-sm">
            {weakTopics.length > 0 && (
              <div className="flex items-start gap-2">
                <span className="text-red-500 mt-0.5 shrink-0">&#9888;</span>
                <p className="text-red-700">
                  <strong>Low mastery:</strong>{' '}
                  {weakTopics.map(t => `${t.topic_name} (${Math.round(t.mastery_score * 100)}%)`).join(', ')}
                </p>
              </div>
            )}
            {lowAccuracyTopics.length > 0 && (
              <div className="flex items-start gap-2">
                <span className="text-orange-500 mt-0.5 shrink-0">&#9679;</span>
                <p className="text-orange-700">
                  <strong>Low accuracy:</strong>{' '}
                  {lowAccuracyTopics.map(t => `${t.topic_name} (${Math.round(t.accuracy * 100)}%)`).join(', ')}
                </p>
              </div>
            )}
            {slowTopics.length > 0 && (
              <div className="flex items-start gap-2">
                <span className="text-yellow-600 mt-0.5 shrink-0">&#9201;</span>
                <p className="text-yellow-800">
                  <strong>Slow response:</strong>{' '}
                  {slowTopics.map(t => `${t.topic_name} (avg ${Math.round(t.avg_time_ms / 1000)}s)`).join(', ')}
                  — aim for under 45s per question.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* What to Study Next */}
      {studyNext.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-semibold text-indigo-800 mb-3">What to Study Next</h2>
          <p className="text-sm text-indigo-600 mb-3">Focus on these topics in order of priority:</p>
          <div className="space-y-2">
            {studyNext.map((topic, i) => {
              const mastery = Math.round(topic.mastery_score * 100)
              const acc = Math.round(topic.accuracy * 100)
              const badge =
                mastery < 30 ? { text: 'Critical', cls: 'bg-red-100 text-red-700' } :
                mastery < 50 ? { text: 'Needs Work', cls: 'bg-orange-100 text-orange-700' } :
                { text: 'Improving', cls: 'bg-yellow-100 text-yellow-700' }
              return (
                <div key={topic.topic_id} className="flex items-center gap-3 bg-white rounded-lg p-3 border border-indigo-100">
                  <span className="w-6 h-6 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-bold shrink-0">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium">{topic.topic_name}</span>
                    <span className="text-xs text-gray-500 ml-2">Mastery {mastery}% · Accuracy {acc}%</span>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.cls}`}>{badge.text}</span>
                </div>
              )
            })}
          </div>
          <button
            onClick={() => navigate('/', { state: { topicIds: studyNext.map(t => t.topic_id), mode: 'quick' } })}
            className="mt-4 px-4 py-2 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
          >
            Start Practice Test on These Topics
          </button>
        </div>
      )}

      {/* System status */}
      <div className="bg-white rounded-lg border p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">System Status</h2>
        {healthLoading ? (
          <p className="text-gray-500">Checking…</p>
        ) : health ? (
          <div className="space-y-3">
            <StatusRow label="Overall" value={health.status} ok={health.status === 'ok'} />
            <StatusRow label="Database" value={health.db_ok ? 'Connected' : 'Disconnected'} ok={health.db_ok} />
            <StatusRow label="Ollama" value={health.ollama_connected ? 'Connected' : 'Not reachable'} ok={health.ollama_connected} />
            {health.loaded_models.length > 0 && (
              <div className="pl-4">
                <p className="text-sm text-gray-500 mb-1">Available models:</p>
                <div className="flex flex-wrap gap-2">
                  {health.loaded_models.map(m => (
                    <span key={m} className="text-xs bg-gray-100 px-2 py-1 rounded font-mono">{m}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-red-600">Cannot reach backend at port 8001</p>
        )}
      </div>

      {/* Ollama test */}
      <div className="bg-white rounded-lg border p-6">
        <h2 className="text-lg font-semibold mb-4">Test Ollama</h2>
        <button
          onClick={handlePingOllama}
          className="px-4 py-2 rounded bg-blue-600 text-white text-sm hover:bg-blue-700"
        >
          Ping Ollama
        </button>
        {ollamaResult && (
          <pre className="mt-3 p-3 bg-gray-50 rounded text-sm font-mono whitespace-pre-wrap">{ollamaResult}</pre>
        )}
      </div>
    </div>
  )
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
      <span className="text-sm font-medium w-24">{label}</span>
      <span className="text-sm text-gray-600">{value}</span>
    </div>
  )
}
