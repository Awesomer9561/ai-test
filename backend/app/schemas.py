"""Pydantic schemas for API request/response validation and LLM output parsing."""

from datetime import datetime
from pydantic import BaseModel, Field


# ── Subjects & Topics ──

class TopicOut(BaseModel):
    id: int
    name: str
    subject_id: int

    model_config = {"from_attributes": True}


class SubjectOut(BaseModel):
    id: int
    name: str
    topics: list[TopicOut] = []

    model_config = {"from_attributes": True}


# ── Questions ──

class QuestionOut(BaseModel):
    id: int
    stem: str
    options: list[str]
    difficulty: int
    topic_id: int
    topic_name: str = ""
    subject_name: str = ""

    model_config = {"from_attributes": True}


class QuestionWithAnswer(QuestionOut):
    correct_index: int
    explanation: str


# ── Tests ──

class TestStartRequest(BaseModel):
    user_id: int
    topic_ids: list[int]
    mode: str = "custom"       # custom / adaptive / mock
    num_questions: int = 10
    duration_seconds: int = 600


class TestQuestionOut(BaseModel):
    position: int
    question: QuestionOut

    model_config = {"from_attributes": True}


class TestOut(BaseModel):
    id: int
    mode: str
    duration_seconds: int
    started_at: datetime
    questions: list[TestQuestionOut] = []

    model_config = {"from_attributes": True}


class AnswerSubmission(BaseModel):
    question_id: int
    answer_index: int | None = None  # null = skipped
    time_spent_ms: int = 0


class TestSubmitRequest(BaseModel):
    answers: list[AnswerSubmission]


# ── Results ──

class QuestionResult(BaseModel):
    position: int
    question: QuestionWithAnswer
    user_answer_index: int | None
    was_correct: bool
    time_spent_ms: int


class TopicBreakdown(BaseModel):
    topic_id: int
    topic_name: str
    total: int
    correct: int
    accuracy: float
    avg_time_ms: float


class TestResultOut(BaseModel):
    test_id: int
    total_questions: int
    attempted: int
    correct: int
    wrong: int
    skipped: int
    score: float
    accuracy: float
    total_time_ms: int
    topic_breakdown: list[TopicBreakdown]
    questions: list[QuestionResult]


# ── User Skill ──

class UserSkillOut(BaseModel):
    topic_id: int
    topic_name: str
    mastery_score: float
    accuracy: float
    avg_time_ms: int

    model_config = {"from_attributes": True}


# ── AI Generation (LLM output schema) ──

class GeneratedQuestion(BaseModel):
    """Schema for validating LLM-generated MCQs."""
    stem: str = Field(..., min_length=10)
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_index: int = Field(..., ge=0, le=3)
    explanation: str = Field(..., min_length=10)
    difficulty: int = Field(3, ge=1, le=5)


# ── Health ──

class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    loaded_models: list[str]
    db_ok: bool
