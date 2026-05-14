"""Test session API — start, fetch, and submit tests."""

import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Test, TestQuestion, Question, Attempt, UserSkill, Topic, Subject
from app.schemas import (
    TestStartRequest, TestOut, TestQuestionOut, QuestionOut,
    TestSubmitRequest, TestResultOut, QuestionResult,
    QuestionWithAnswer, TopicBreakdown,
    SaveProgressRequest, InProgressTestResponse,
)
from app.workers.skill_update import update_skills_after_test

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tests", tags=["tests"])


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _build_topic_name_map(questions: list[Question], db: AsyncSession) -> dict[int, tuple[str, str]]:
    """Return {topic_id: (topic_name, subject_name)} for a list of questions."""
    cache: dict[int, tuple[str, str]] = {}
    for q in questions:
        if q.topic_id not in cache:
            topic = await db.get(Topic, q.topic_id)
            subject = await db.get(Subject, topic.subject_id) if topic else None
            cache[q.topic_id] = (topic.name if topic else "", subject.name if subject else "")
    return cache


def _make_test_out(
    test: Test,
    questions: list[Question],
    test_questions: list[TestQuestion],
    topic_name_map: dict[int, tuple[str, str]],
    *,
    challenge_mode: bool = False,
    include_saved_answers: bool = False,
    remaining_ms: int | None = None,
) -> TestOut:
    return TestOut(
        id=test.id,
        mode=test.mode,
        duration_seconds=test.duration_seconds,
        started_at=test.started_at,
        challenge_mode=challenge_mode,
        remaining_ms=remaining_ms,
        current_position=test.current_position if include_saved_answers else 1,
        questions=[
            TestQuestionOut(
                position=tq.position,
                saved_answer_index=tq.user_answer_index if include_saved_answers else None,
                question=QuestionOut(
                    id=q.id,
                    stem=q.stem,
                    options=q.options,
                    difficulty=q.difficulty,
                    topic_id=q.topic_id,
                    topic_name=topic_name_map.get(q.topic_id, ("", ""))[0],
                    subject_name=topic_name_map.get(q.topic_id, ("", ""))[1],
                ),
            )
            for tq, q in zip(test_questions, questions)
        ],
    )


async def _create_test_record(
    db: AsyncSession,
    user_id: int,
    mode: str,
    questions: list[Question],
    duration_seconds: int,
) -> tuple[Test, list[TestQuestion]]:
    topic_ids = list({q.topic_id for q in questions})
    test = Test(user_id=user_id, mode=mode, topic_ids=topic_ids, duration_seconds=duration_seconds)
    db.add(test)
    await db.flush()

    tqs: list[TestQuestion] = []
    for i, q in enumerate(questions):
        tq = TestQuestion(test_id=test.id, question_id=q.id, position=i + 1)
        db.add(tq)
        tqs.append(tq)

    await db.commit()
    await db.refresh(test)
    return test, tqs


# ── Normal test start (quick / standard / custom) ────────────────────────────

async def _start_normal_test(req: TestStartRequest, db: AsyncSession) -> TestOut:
    """Create a test from questions already in the DB — no AI generation."""
    stmt = (
        select(Question)
        .where(Question.topic_id.in_(req.topic_ids))
        .order_by(func.random())
        .limit(req.num_questions)
    )
    result = await db.execute(stmt)
    questions = list(result.scalars().all())

    if not questions:
        raise HTTPException(404, "No questions found for the selected topics.")

    test, tqs = await _create_test_record(db, req.user_id, req.mode, questions, req.duration_seconds)
    topic_name_map = await _build_topic_name_map(questions, db)
    return _make_test_out(test, questions, tqs, topic_name_map)


# ── Adaptive test start ───────────────────────────────────────────────────────

async def _start_adaptive_test(req: TestStartRequest, db: AsyncSession) -> TestOut:
    """
    Build a personalised adaptive test by generating AI questions for weak topics.
    Generated questions are stored in DB and enter the normal rotation for future tests.
    This endpoint is intentionally slow (30–60s) — the frontend shows a loading screen.
    """
    from app.workers.adaptive_prep import build_adaptive_questions, is_high_performer
    from app.models import UserSkill

    # Determine if user is a high performer (needed for mode label + composition)
    skills_stmt = select(UserSkill).where(UserSkill.user_id == req.user_id)
    skills_result = await db.execute(skills_stmt)
    skills = skills_result.scalars().all()
    challenge = is_high_performer(list(skills))

    questions = await build_adaptive_questions(
        user_id=req.user_id,
        num_questions=req.num_questions,
        db=db,
    )

    # Fall back to random DB questions if no skill data yet
    if not questions:
        logger.info(f"No skill data for user {req.user_id} — using random questions for adaptive test.")
        stmt = (
            select(Question)
            .order_by(func.random())
            .limit(req.num_questions)
        )
        result = await db.execute(stmt)
        questions = list(result.scalars().all())

    if not questions:
        raise HTTPException(404, "No questions available. Please seed the database first.")

    mode = "adaptive_challenge" if challenge else "adaptive"
    test, tqs = await _create_test_record(db, req.user_id, mode, questions, req.duration_seconds)
    topic_name_map = await _build_topic_name_map(questions, db)
    return _make_test_out(test, questions, tqs, topic_name_map, challenge_mode=challenge)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=TestOut)
async def start_test(req: TestStartRequest, db: AsyncSession = Depends(get_db)):
    """
    Start a new test session.
    - mode=adaptive  → generates AI questions tailored to user weak areas (slow, ~30–60s)
    - any other mode → serves existing DB questions only (fast)
    """
    if req.mode == "adaptive":
        return await _start_adaptive_test(req, db)
    return await _start_normal_test(req, db)


@router.post("/{test_id}/submit", response_model=TestResultOut)
async def submit_test(test_id: int, req: TestSubmitRequest, db: AsyncSession = Depends(get_db)):
    """Submit answers for a test and compute results."""
    test = await db.get(Test, test_id)
    if not test:
        raise HTTPException(404, "Test not found.")
    if test.submitted_at:
        raise HTTPException(400, "Test already submitted.")

    test.submitted_at = datetime.utcnow()
    answer_map = {a.question_id: a for a in req.answers}

    stmt = (
        select(TestQuestion)
        .where(TestQuestion.test_id == test_id)
        .order_by(TestQuestion.position)
    )
    result = await db.execute(stmt)
    tqs = result.scalars().all()

    question_results = []
    topic_stats: dict[int, dict] = {}
    topic_name_cache: dict[int, tuple[str, str]] = {}
    total_time = 0
    correct_count = 0
    attempted = 0
    wrong_count = 0

    for tq in tqs:
        q = await db.get(Question, tq.question_id)
        topic = await db.get(Topic, q.topic_id)

        if q.topic_id not in topic_name_cache:
            subject = await db.get(Subject, topic.subject_id) if topic else None
            topic_name_cache[q.topic_id] = (
                topic.name if topic else "",
                subject.name if subject else "",
            )

        ans = answer_map.get(q.id)
        user_answer = ans.answer_index if ans else None
        time_ms = ans.time_spent_ms if ans else 0
        was_correct = user_answer == q.correct_index if user_answer is not None else False

        tq.user_answer_index = user_answer
        tq.time_spent_ms = time_ms

        if user_answer is not None:
            attempted += 1
            db.add(Attempt(
                user_id=test.user_id,
                question_id=q.id,
                was_correct=was_correct,
                time_spent_ms=time_ms,
            ))
            if was_correct:
                correct_count += 1
            else:
                wrong_count += 1

        total_time += time_ms

        tid = q.topic_id
        if tid not in topic_stats:
            topic_stats[tid] = {"name": topic.name if topic else "", "total": 0, "correct": 0, "time": 0}
        topic_stats[tid]["total"] += 1
        if was_correct:
            topic_stats[tid]["correct"] += 1
        topic_stats[tid]["time"] += time_ms

        question_results.append(QuestionResult(
            position=tq.position,
            question=QuestionWithAnswer(
                id=q.id,
                stem=q.stem,
                options=q.options,
                difficulty=q.difficulty,
                topic_id=q.topic_id,
                topic_name=topic_name_cache.get(q.topic_id, ("", ""))[0],
                subject_name=topic_name_cache.get(q.topic_id, ("", ""))[1],
                correct_index=q.correct_index,
                explanation=q.explanation or "",
            ),
            user_answer_index=user_answer,
            was_correct=was_correct,
            time_spent_ms=time_ms,
        ))

    await db.commit()

    # Update skill scores in background (non-blocking)
    asyncio.create_task(_update_skills_bg(test_id, test.user_id))

    total_q = len(tqs)
    skipped = total_q - attempted

    return TestResultOut(
        test_id=test_id,
        total_questions=total_q,
        attempted=attempted,
        correct=correct_count,
        wrong=wrong_count,
        skipped=skipped,
        score=round(correct_count / total_q * 100, 2) if total_q else 0,
        accuracy=round(correct_count / attempted * 100, 2) if attempted else 0,
        total_time_ms=total_time,
        topic_breakdown=[
            TopicBreakdown(
                topic_id=tid,
                topic_name=stats["name"],
                total=stats["total"],
                correct=stats["correct"],
                accuracy=round(stats["correct"] / stats["total"] * 100, 2) if stats["total"] else 0,
                avg_time_ms=round(stats["time"] / stats["total"]) if stats["total"] else 0,
            )
            for tid, stats in topic_stats.items()
        ],
        questions=question_results,
    )


@router.get("/in-progress", response_model=InProgressTestResponse)
async def get_in_progress_test(user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    """Return the most recent unsubmitted test for a user (for session recovery)."""
    stmt = (
        select(Test)
        .where(Test.user_id == user_id, Test.submitted_at.is_(None))
        .order_by(Test.started_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    test = result.scalar_one_or_none()

    if not test:
        return InProgressTestResponse(has_test=False)

    now = datetime.now(timezone.utc)
    started = test.started_at.replace(tzinfo=timezone.utc) if test.started_at.tzinfo is None else test.started_at
    elapsed_ms = int((now - started).total_seconds() * 1000)
    remaining_ms = max(0, test.duration_seconds * 1000 - elapsed_ms)

    # Count saved answers
    tq_stmt = select(TestQuestion).where(TestQuestion.test_id == test.id)
    tq_result = await db.execute(tq_stmt)
    tqs = tq_result.scalars().all()
    answers_saved = sum(1 for tq in tqs if tq.user_answer_index is not None)

    return InProgressTestResponse(
        has_test=True,
        test_id=test.id,
        started_at=test.started_at.isoformat(),
        remaining_ms=remaining_ms,
        answers_saved=answers_saved,
        total_questions=len(tqs),
        last_position=test.current_position or 1,
    )


@router.get("/{test_id}", response_model=TestOut)
async def get_test(test_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch a test by ID with saved answers — used for session recovery."""
    test = await db.get(Test, test_id)
    if not test:
        raise HTTPException(404, "Test not found.")

    # Compute remaining time
    now = datetime.now(timezone.utc)
    started = test.started_at.replace(tzinfo=timezone.utc) if test.started_at.tzinfo is None else test.started_at
    elapsed_ms = int((now - started).total_seconds() * 1000)
    remaining_ms = max(0, test.duration_seconds * 1000 - elapsed_ms)

    stmt = (
        select(TestQuestion)
        .where(TestQuestion.test_id == test_id)
        .order_by(TestQuestion.position)
    )
    result = await db.execute(stmt)
    tqs = list(result.scalars().all())

    questions = []
    for tq in tqs:
        q = await db.get(Question, tq.question_id)
        if q:
            questions.append(q)

    topic_name_map = await _build_topic_name_map(questions, db)
    challenge = test.mode == "adaptive_challenge"
    return _make_test_out(
        test, questions, tqs, topic_name_map,
        challenge_mode=challenge,
        include_saved_answers=True,
        remaining_ms=remaining_ms,
    )


@router.patch("/{test_id}/progress")
async def save_progress(test_id: int, req: SaveProgressRequest, db: AsyncSession = Depends(get_db)):
    """Save mid-test progress (answers + current position) to the DB."""
    test = await db.get(Test, test_id)
    if not test:
        raise HTTPException(404, "Test not found.")
    if test.submitted_at:
        raise HTTPException(400, "Test already submitted.")

    test.current_position = req.position

    answer_map = {a.question_id: a for a in req.answers}
    stmt = select(TestQuestion).where(TestQuestion.test_id == test_id)
    result = await db.execute(stmt)
    tqs = result.scalars().all()

    for tq in tqs:
        if tq.question_id in answer_map:
            a = answer_map[tq.question_id]
            tq.user_answer_index = a.answer_index
            tq.time_spent_ms = a.time_spent_ms

    await db.commit()
    return {"ok": True}


async def _update_skills_bg(test_id: int, user_id: int):
    """Background task: update skill scores after test submission."""
    from app.db import async_session
    async with async_session() as db:
        try:
            await update_skills_after_test(test_id, db)
        except Exception as e:
            logger.error(f"[BG] Skill update failed for test {test_id}: {e}")
