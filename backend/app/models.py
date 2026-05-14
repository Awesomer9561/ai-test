"""SQLAlchemy ORM models — matches the data model from the plan."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    exam_target = Column(String(50), default="IBPS PO")  # IBPS PO / Clerk / RRB / SBI
    created_at = Column(DateTime, default=datetime.utcnow)

    tests = relationship("Test", back_populates="user")
    attempts = relationship("Attempt", back_populates="user")
    skills = relationship("UserSkill", back_populates="user")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    exam_category = Column(String(20), nullable=False, server_default="banking", default="banking")
    # "banking" → IBPS/SBI exams | "ug_entrance" → JEE/WBJEE/CUET

    topics = relationship("Topic", back_populates="subject")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(150), nullable=False)

    subject = relationship("Subject", back_populates="topics")
    questions = relationship("Question", back_populates="topic")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    stem = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)          # list of 4 strings
    correct_index = Column(Integer, nullable=False)  # 0-3
    explanation = Column(Text, default="")
    difficulty = Column(Integer, default=3)          # 1 (easy) to 5 (hard)
    source = Column(String(20), default="seed")      # "seed" or "ai_generated"
    embedding_id = Column(String(100), nullable=True)  # Chroma doc ID
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="questions")


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(String(20), default="custom")  # custom / adaptive / mock
    topic_ids = Column(JSON, default=list)        # list of topic IDs included
    duration_seconds = Column(Integer, default=600)
    started_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    current_position = Column(Integer, default=1)  # last viewed question (for session restore)

    user = relationship("User", back_populates="tests")
    test_questions = relationship("TestQuestion", back_populates="test")


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    position = Column(Integer, nullable=False)
    user_answer_index = Column(Integer, nullable=True)  # null = unanswered
    time_spent_ms = Column(Integer, default=0)

    test = relationship("Test", back_populates="test_questions")
    question = relationship("Question")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    was_correct = Column(Boolean, nullable=False)
    time_spent_ms = Column(Integer, default=0)
    attempted_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="attempts")
    question = relationship("Question")


class UserSkill(Base):
    __tablename__ = "user_skill"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    mastery_score = Column(Float, default=0.5)   # 0.0 to 1.0
    accuracy = Column(Float, default=0.0)
    avg_time_ms = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="skills")
    topic = relationship("Topic")
