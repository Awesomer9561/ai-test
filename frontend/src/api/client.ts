import axios from 'axios'

const api = axios.create({
  baseURL: '/', // proxied via Vite in dev
  timeout: 120_000, // AI generation can take up to 60s
})

export default api

// ── Types ──

export interface Topic {
  id: number
  name: string
  subject_id: number
}

export interface Subject {
  id: number
  name: string
  exam_category: string  // "banking" | "ug_entrance"
  topics: Topic[]
}

export interface Question {
  id: number
  stem: string
  options: string[]
  difficulty: number
  topic_id: number
  topic_name: string
  subject_name: string
}

export interface TestQuestion {
  position: number
  question: Question
  saved_answer_index?: number | null
}

export interface TestSession {
  id: number
  mode: string
  duration_seconds: number
  started_at: string
  questions: TestQuestion[]
  remaining_ms?: number | null
  current_position?: number
  challenge_mode?: boolean
}

export interface InProgressTestResponse {
  has_test: boolean
  test_id: number | null
  started_at: string | null
  remaining_ms: number
  answers_saved: number
  total_questions: number
  last_position: number
}

export interface QuestionWithAnswer extends Question {
  correct_index: number
  explanation: string
}

export interface QuestionResult {
  position: number
  question: QuestionWithAnswer
  user_answer_index: number | null
  was_correct: boolean
  time_spent_ms: number
}

export interface TopicBreakdown {
  topic_id: number
  topic_name: string
  total: number
  correct: number
  accuracy: number
  avg_time_ms: number
}

export interface TestResult {
  test_id: number
  total_questions: number
  attempted: number
  correct: number
  wrong: number
  skipped: number
  score: number
  accuracy: number
  total_time_ms: number
  topic_breakdown: TopicBreakdown[]
  questions: QuestionResult[]
}

export interface HealthStatus {
  status: string
  ollama_connected: boolean
  loaded_models: string[]
  db_ok: boolean
}

// ── API calls ──

export const fetchSubjects = (examCategory?: string) => {
  const params = examCategory ? { exam_category: examCategory } : {}
  return api.get<Subject[]>('/api/topics/', { params }).then(r => r.data)
}

export const startTest = (data: {
  user_id: number
  topic_ids: number[]
  mode?: string
  num_questions?: number
  duration_seconds?: number
}) =>
  api.post<TestSession>('/api/tests/start', data).then(r => r.data)

export const submitTest = (testId: number, answers: { question_id: number; answer_index: number | null; time_spent_ms: number }[]) =>
  api.post<TestResult>(`/api/tests/${testId}/submit`, { answers }).then(r => r.data)

export const fetchHealth = () =>
  api.get<HealthStatus>('/health').then(r => r.data)

export const pingOllama = () =>
  api.get<{ ollama_response: string; success: boolean }>('/ping-ollama').then(r => r.data)

export const explainQuestion = (questionId: number, userAnswerIndex: number | null) =>
  api.post<{ explanation: string }>(`/api/questions/${questionId}/explain`, {
    user_answer_index: userAnswerIndex,
  }).then(r => r.data)

export interface UserSkill {
  topic_id: number
  topic_name: string
  mastery_score: number
  accuracy: number
  avg_time_ms: number
}

export const fetchSkills = (userId: number) =>
  api.get<UserSkill[]>(`/api/results/skills/${userId}`).then(r => r.data)

// ── Profile ──

export interface UserProfile {
  id: number
  name: string
  exam_target: string
  exam_category: string  // "banking" | "ug_entrance"
}

export interface ExamList {
  banking: string[]
  ug_entrance: string[]
}

export const fetchExamList = () =>
  api.get<ExamList>('/api/profile/exams').then(r => r.data)

export const loginOrCreate = (name: string, examTarget: string = 'IBPS PO') =>
  api.post<UserProfile>('/api/profile/login', { name, exam_target: examTarget }).then(r => r.data)

export const listUsers = () =>
  api.get<UserProfile[]>('/api/profile/users').then(r => r.data)

// ── Test session ──

export const fetchTestById = (testId: number) =>
  api.get<TestSession>(`/api/tests/${testId}`).then(r => r.data)

export const fetchInProgressTest = (userId: number) =>
  api.get<InProgressTestResponse>('/api/tests/in-progress', { params: { user_id: userId } }).then(r => r.data)

export const saveProgress = (
  testId: number,
  position: number,
  answers: { question_id: number; answer_index: number | null; time_spent_ms: number }[],
) =>
  api.patch(`/api/tests/${testId}/progress`, { position, answers }).then(r => r.data)
