import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { explainQuestion } from '@/api/client'
import type { TestResult } from '@/api/client'

export default function ResultPage() {
  const navigate = useNavigate()
  const [aiExplanations, setAiExplanations] = useState<Record<number, string>>({})
  const [loadingExplanation, setLoadingExplanation] = useState<number | null>(null)

  const handleExplain = async (questionId: number, userAnswerIndex: number | null) => {
    setLoadingExplanation(questionId)
    try {
      const res = await explainQuestion(questionId, userAnswerIndex)
      setAiExplanations(prev => ({ ...prev, [questionId]: res.explanation }))
    } catch {
      setAiExplanations(prev => ({ ...prev, [questionId]: 'Failed to generate explanation. Is Ollama running?' }))
    } finally {
      setLoadingExplanation(null)
    }
  }
  const location = useLocation()
  const result = location.state?.result as TestResult | undefined

  if (!result) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500 mb-4">No results found.</p>
        <button onClick={() => navigate('/')} className="text-brand-600 underline">
          Start a new test
        </button>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Test Results</h1>

      {/* Score summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <ScoreCard label="Score" value={`${result.score}%`} color="blue" />
        <ScoreCard label="Correct" value={`${result.correct}/${result.total_questions}`} color="green" />
        <ScoreCard label="Wrong" value={String(result.wrong)} color="red" />
        <ScoreCard label="Skipped" value={String(result.skipped)} color="gray" />
      </div>

      {/* Accuracy & time */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        <div className="bg-white rounded-lg border p-4">
          <p className="text-sm text-gray-500">Accuracy (attempted)</p>
          <p className="text-2xl font-bold">{result.accuracy}%</p>
        </div>
        <div className="bg-white rounded-lg border p-4">
          <p className="text-sm text-gray-500">Total Time</p>
          <p className="text-2xl font-bold">{Math.round(result.total_time_ms / 1000)}s</p>
        </div>
      </div>

      {/* Topic breakdown */}
      {result.topic_breakdown.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-3">Topic Breakdown</h2>
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left p-3">Topic</th>
                  <th className="text-center p-3">Correct</th>
                  <th className="text-center p-3">Accuracy</th>
                  <th className="text-center p-3">Avg Time</th>
                </tr>
              </thead>
              <tbody>
                {result.topic_breakdown.map(tb => (
                  <tr key={tb.topic_id} className="border-t">
                    <td className="p-3 font-medium">{tb.topic_name}</td>
                    <td className="p-3 text-center">{tb.correct}/{tb.total}</td>
                    <td className="p-3 text-center">
                      <span className={tb.accuracy >= 60 ? 'text-green-600' : 'text-red-600'}>
                        {tb.accuracy}%
                      </span>
                    </td>
                    <td className="p-3 text-center text-gray-500">{Math.round(tb.avg_time_ms / 1000)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Question-by-question review */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Question Review</h2>
        <div className="space-y-4">
          {result.questions.map(qr => (
            <div key={qr.position} className={`bg-white rounded-lg border p-4 ${
              qr.was_correct ? 'border-l-4 border-l-green-500' :
              qr.user_answer_index === null ? 'border-l-4 border-l-gray-300' :
              'border-l-4 border-l-red-500'
            }`}>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-gray-400">Q{qr.position}</span>
                  {qr.question.subject_name && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                      {qr.question.subject_name}
                    </span>
                  )}
                  {qr.question.topic_name && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">
                      {qr.question.topic_name}
                    </span>
                  )}
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  qr.was_correct ? 'bg-green-100 text-green-700' :
                  qr.user_answer_index === null ? 'bg-gray-100 text-gray-500' :
                  'bg-red-100 text-red-700'
                }`}>
                  {qr.was_correct ? 'Correct' : qr.user_answer_index === null ? 'Skipped' : 'Wrong'}
                </span>
              </div>
              <p className="mb-3">{qr.question.stem}</p>
              <div className="space-y-1 text-sm mb-3">
                {qr.question.options.map((opt, idx) => (
                  <div key={idx} className={`px-3 py-1.5 rounded ${
                    idx === qr.question.correct_index ? 'bg-green-50 text-green-800 font-medium' :
                    idx === qr.user_answer_index ? 'bg-red-50 text-red-700' :
                    'text-gray-600'
                  }`}>
                    {String.fromCharCode(65 + idx)}. {opt}
                    {idx === qr.question.correct_index && ' ✓'}
                    {idx === qr.user_answer_index && idx !== qr.question.correct_index && ' ✗'}
                  </div>
                ))}
              </div>
              {(qr.question.explanation || aiExplanations[qr.question.id]) && (
                <div className="bg-blue-50 rounded p-3 text-sm text-blue-800">
                  <strong>Explanation:</strong> {aiExplanations[qr.question.id] || qr.question.explanation}
                </div>
              )}
              {!qr.was_correct && !aiExplanations[qr.question.id] && (
                <button
                  onClick={() => handleExplain(qr.question.id, qr.user_answer_index)}
                  disabled={loadingExplanation === qr.question.id}
                  className="mt-2 px-3 py-1.5 text-xs rounded bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {loadingExplanation === qr.question.id ? '⏳ Generating explanation...' : '🤖 Get AI Explanation'}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Weak areas + adaptive suggestion */}
      {result.topic_breakdown.some(tb => tb.accuracy < 60) && (
        <div className="mb-8 bg-orange-50 border border-orange-200 rounded-lg p-5">
          <h2 className="text-lg font-semibold text-orange-800 mb-2">Weak Areas Detected</h2>
          <p className="text-sm text-orange-700 mb-3">
            You scored below 60% in:{' '}
            {result.topic_breakdown
              .filter(tb => tb.accuracy < 60)
              .map(tb => tb.topic_name)
              .join(', ')}
          </p>
          <p className="text-sm text-gray-600">
            An adaptive test targeting these areas is being prepared. Check your Dashboard in a moment!
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-4">
        <button
          onClick={() => navigate('/')}
          className="flex-1 py-3 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700"
        >
          Start New Test
        </button>
        <button
          onClick={() => navigate('/dashboard')}
          className="flex-1 py-3 rounded-lg border border-gray-300 text-gray-700 font-semibold hover:bg-gray-50"
        >
          View Dashboard
        </button>
      </div>
    </div>
  )
}

function ScoreCard({ label, value, color }: { label: string; value: string; color: string }) {
  const bgMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    red: 'bg-red-50 text-red-700',
    gray: 'bg-gray-50 text-gray-700',
  }
  return (
    <div className={`rounded-lg p-4 ${bgMap[color] || bgMap.gray}`}>
      <p className="text-sm opacity-75">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  )
}
