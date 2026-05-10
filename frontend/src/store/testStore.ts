import { create } from 'zustand'

interface Answer {
  question_id: number
  answer_index: number | null
  time_spent_ms: number
}

interface TestState {
  testId: number | null
  answers: Map<number, Answer> // keyed by question_id
  currentPosition: number
  startedAt: number | null
  questionStartedAt: number | null

  // Actions
  initTest: (testId: number) => void
  setAnswer: (questionId: number, answerIndex: number | null) => void
  setPosition: (pos: number) => void
  startQuestionTimer: () => void
  getTimeOnCurrentQuestion: () => number
  getAllAnswers: () => Answer[]
  reset: () => void
}

export const useTestStore = create<TestState>((set, get) => ({
  testId: null,
  answers: new Map(),
  currentPosition: 1,
  startedAt: null,
  questionStartedAt: null,

  initTest: (testId) =>
    set({
      testId,
      answers: new Map(),
      currentPosition: 1,
      startedAt: Date.now(),
      questionStartedAt: Date.now(),
    }),

  setAnswer: (questionId, answerIndex) => {
    const state = get()
    const elapsed = state.questionStartedAt ? Date.now() - state.questionStartedAt : 0
    const existing = state.answers.get(questionId)
    const totalTime = (existing?.time_spent_ms || 0) + elapsed

    const newAnswers = new Map(state.answers)
    newAnswers.set(questionId, {
      question_id: questionId,
      answer_index: answerIndex,
      time_spent_ms: totalTime,
    })
    set({ answers: newAnswers })
  },

  setPosition: (pos) => set({ currentPosition: pos, questionStartedAt: Date.now() }),

  startQuestionTimer: () => set({ questionStartedAt: Date.now() }),

  getTimeOnCurrentQuestion: () => {
    const state = get()
    return state.questionStartedAt ? Date.now() - state.questionStartedAt : 0
  },

  getAllAnswers: () => Array.from(get().answers.values()),

  reset: () =>
    set({
      testId: null,
      answers: new Map(),
      currentPosition: 1,
      startedAt: null,
      questionStartedAt: null,
    }),
}))
