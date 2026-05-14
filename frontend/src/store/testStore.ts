import { create } from 'zustand'
import { saveProgress } from '@/api/client'

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
  lastSyncedAt: number | null
  _saveInterval: ReturnType<typeof setInterval> | null
  _debounceTimer: ReturnType<typeof setTimeout> | null

  // Actions
  initTest: (testId: number) => void
  setAnswer: (questionId: number, answerIndex: number | null) => void
  setPosition: (pos: number) => void
  startQuestionTimer: () => void
  getTimeOnCurrentQuestion: () => number
  getAllAnswers: () => Answer[]
  scheduleAutoSave: (testId: number) => void
  cancelAutoSave: () => void
  triggerSave: () => void
  reset: () => void
}

export const useTestStore = create<TestState>((set, get) => ({
  testId: null,
  answers: new Map(),
  currentPosition: 1,
  startedAt: null,
  questionStartedAt: null,
  lastSyncedAt: null,
  _saveInterval: null,
  _debounceTimer: null,

  initTest: (testId) =>
    set({
      testId,
      answers: new Map(),
      currentPosition: 1,
      startedAt: Date.now(),
      questionStartedAt: Date.now(),
      lastSyncedAt: null,
      _saveInterval: null,
      _debounceTimer: null,
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

    // Debounced save on answer change (500 ms)
    if (state._debounceTimer) clearTimeout(state._debounceTimer)
    const timer = setTimeout(() => {
      get().triggerSave()
      set({ _debounceTimer: null })
    }, 500)
    set({ _debounceTimer: timer })
  },

  setPosition: (pos) => set({ currentPosition: pos, questionStartedAt: Date.now() }),

  startQuestionTimer: () => set({ questionStartedAt: Date.now() }),

  getTimeOnCurrentQuestion: () => {
    const state = get()
    return state.questionStartedAt ? Date.now() - state.questionStartedAt : 0
  },

  getAllAnswers: () => Array.from(get().answers.values()),

  scheduleAutoSave: (testId: number) => {
    // Cancel any existing interval first
    const existing = get()._saveInterval
    if (existing) clearInterval(existing)

    set({ testId })

    const interval = setInterval(() => {
      get().triggerSave()
    }, 5000)

    set({ _saveInterval: interval })
  },

  cancelAutoSave: () => {
    const state = get()
    if (state._saveInterval) {
      clearInterval(state._saveInterval)
    }
    if (state._debounceTimer) {
      clearTimeout(state._debounceTimer)
    }
    set({ _saveInterval: null, _debounceTimer: null })
  },

  triggerSave: async () => {
    const state = get()
    if (!state.testId) return
    const answers = Array.from(state.answers.values())
    try {
      await saveProgress(state.testId, state.currentPosition, answers)
      set({ lastSyncedAt: Date.now() })
    } catch {
      // Silent failure — don't interrupt the test experience
    }
  },

  reset: () => {
    const state = get()
    if (state._saveInterval) clearInterval(state._saveInterval)
    if (state._debounceTimer) clearTimeout(state._debounceTimer)
    set({
      testId: null,
      answers: new Map(),
      currentPosition: 1,
      startedAt: null,
      questionStartedAt: null,
      lastSyncedAt: null,
      _saveInterval: null,
      _debounceTimer: null,
    })
  },
}))
