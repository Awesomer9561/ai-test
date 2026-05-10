import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation, useParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { submitTest, type TestSession } from '@/api/client'
import { useTestStore } from '@/store/testStore'

export default function TestPage() {
  const { testId } = useParams<{ testId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const test = location.state?.test as TestSession | undefined

  const {
    currentPosition, setPosition, setAnswer, answers,
    startQuestionTimer, getAllAnswers,
  } = useTestStore()

  const [timeLeft, setTimeLeft] = useState(test?.duration_seconds ?? 600)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)

  // Timer countdown
  useEffect(() => {
    if (timeLeft <= 0) {
      handleSubmit()
      return
    }
    const interval = setInterval(() => setTimeLeft(t => t - 1), 1000)
    return () => clearInterval(interval)
  }, [timeLeft])

  // Sync selected option when navigating questions
  useEffect(() => {
    if (!test) return
    const q = test.questions.find(tq => tq.position === currentPosition)
    if (q) {
      const existing = answers.get(q.question.id)
      setSelectedOption(existing?.answer_index ?? null)
    }
    startQuestionTimer()
  }, [currentPosition, test])

  const submitMutation = useMutation({
    mutationFn: () => submitTest(Number(testId), getAllAnswers()),
    onSuccess: (result) => {
      navigate(`/result/${testId}`, { state: { result } })
    },
  })

  const handleSubmit = useCallback(() => {
    // Save current answer before submitting
    const q = test?.questions.find(tq => tq.position === currentPosition)
    if (q) setAnswer(q.question.id, selectedOption)
    submitMutation.mutate()
  }, [selectedOption, currentPosition, test])

  if (!test) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500 mb-4">Test data not found. Please start a new test.</p>
        <button onClick={() => navigate('/')} className="text-brand-600 underline">
          Go back
        </button>
      </div>
    )
  }

  const currentQ = test.questions.find(tq => tq.position === currentPosition)
  const totalQuestions = test.questions.length
  const minutes = Math.floor(timeLeft / 60)
  const seconds = timeLeft % 60
  const isWarning = timeLeft <= 60
  const isUrgent = timeLeft <= 300

  const saveAndNavigate = (newPos: number) => {
    if (currentQ) setAnswer(currentQ.question.id, selectedOption)
    setPosition(newPos)
  }

  return (
    <div className="flex gap-6">
      {/* Main question area */}
      <div className="flex-1">
        {/* Timer bar */}
        <div className={`flex items-center justify-between mb-6 p-3 rounded-lg ${
          isWarning ? 'bg-red-50 text-red-700' : isUrgent ? 'bg-yellow-50 text-yellow-700' : 'bg-gray-100 text-gray-700'
        }`}>
          <span className="text-sm font-medium">
            Question {currentPosition} of {totalQuestions}
          </span>
          <span className="font-mono font-bold text-lg">
            {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
          </span>
        </div>

        {/* Question */}
        {currentQ && (
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            {/* Subject / Topic badge */}
            <div className="flex items-center gap-2 mb-3">
              {currentQ.question.subject_name && (
                <span className="text-xs px-2.5 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">
                  {currentQ.question.subject_name}
                </span>
              )}
              {currentQ.question.topic_name && (
                <span className="text-xs px-2.5 py-1 rounded-full bg-purple-100 text-purple-700 font-medium">
                  {currentQ.question.topic_name}
                </span>
              )}
            </div>
            <p className="text-lg mb-6 leading-relaxed">{currentQ.question.stem}</p>

            <div className="space-y-3">
              {currentQ.question.options.map((option, idx) => (
                <label
                  key={idx}
                  className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition ${
                    selectedOption === idx
                      ? 'border-brand-500 bg-brand-50'
                      : 'border-gray-200 hover:border-gray-400'
                  }`}
                >
                  <input
                    type="radio"
                    name="answer"
                    checked={selectedOption === idx}
                    onChange={() => setSelectedOption(idx)}
                    className="mt-0.5"
                  />
                  <span className="text-sm font-medium text-gray-500 mr-1">
                    {String.fromCharCode(65 + idx)}.
                  </span>
                  <span>{option}</span>
                </label>
              ))}
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between mt-8">
              <button
                onClick={() => saveAndNavigate(Math.max(1, currentPosition - 1))}
                disabled={currentPosition === 1}
                className="px-4 py-2 text-sm rounded border border-gray-300 disabled:opacity-30"
              >
                Previous
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => { setSelectedOption(null); if (currentQ) setAnswer(currentQ.question.id, null) }}
                  className="px-4 py-2 text-sm text-gray-500 hover:text-red-600"
                >
                  Clear
                </button>
                {currentPosition < totalQuestions && (
                  <button
                    onClick={() => {
                      if (currentQ) setAnswer(currentQ.question.id, null)
                      setSelectedOption(null)
                      setPosition(Math.min(totalQuestions, currentPosition + 1))
                    }}
                    className="px-4 py-2 text-sm rounded border border-orange-300 text-orange-600 hover:bg-orange-50"
                  >
                    Skip
                  </button>
                )}
              </div>

              {currentPosition < totalQuestions ? (
                <button
                  onClick={() => saveAndNavigate(currentPosition + 1)}
                  className="px-6 py-2 text-sm rounded bg-brand-600 text-white hover:bg-brand-700"
                >
                  Save & Next
                </button>
              ) : (
                <button
                  onClick={handleSubmit}
                  disabled={submitMutation.isPending}
                  className="px-6 py-2 text-sm rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                >
                  {submitMutation.isPending ? 'Submitting...' : 'Submit Test'}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Question palette sidebar */}
      <div className="w-48 shrink-0 hidden md:block">
        <div className="bg-white rounded-lg border border-gray-200 p-4 sticky top-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Questions</h3>
          <div className="grid grid-cols-5 gap-2">
            {test.questions.map(tq => {
              const entry = answers.get(tq.question.id)
              const answered = entry && entry.answer_index !== null
              const skipped = entry && entry.answer_index === null
              const isCurrent = tq.position === currentPosition
              return (
                <button
                  key={tq.position}
                  onClick={() => saveAndNavigate(tq.position)}
                  className={`w-8 h-8 rounded text-xs font-medium ${
                    isCurrent
                      ? 'bg-brand-600 text-white'
                      : answered
                        ? 'bg-green-100 text-green-800 border border-green-300'
                        : skipped
                          ? 'bg-orange-100 text-orange-700 border border-orange-300'
                          : 'bg-gray-100 text-gray-600 border border-gray-200'
                  }`}
                >
                  {tq.position}
                </button>
              )
            })}
          </div>

          {/* Palette legend */}
          <div className="mt-3 space-y-1 text-[10px] text-gray-500">
            <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-green-300 inline-block" /> Answered</div>
            <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-orange-300 inline-block" /> Skipped</div>
            <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-gray-200 inline-block" /> Not visited</div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={submitMutation.isPending}
            className="w-full mt-4 py-2 text-sm rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  )
}
