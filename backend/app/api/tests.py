"""Test session API — start, fetch, and submit tests."""

import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Test, TestQuestion, Question, Attempt, UserSkill, Topic, Subject
from app.schemas import (
    TestStartRequest, TestOut, TestQuestionOut, QuestionOut,
    TestSubmitRequest, TestResultOut, QuestionResult,
    QuestionWithAnswer, TopicBreakdown,
)
from app.ai.generator import question_generator
from app.workers.skill_update import update_skills_after_test
from app.workers.adaptive_prep import prepare_adaptive_test

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tests", tags=["tests"])


async def _generate_for_topic(
    topic_id: int, subject_name: str, topic_name: str,
    count: int, existing_stems: list[str], db: AsyncSession
) -> list[Question]:
    """Generate AI questions for a topic and save them to DB."""
    try:
        generated = await question_generator.generate_questions(
            subject=subject_name,
            topic=topic_name,
            count=count,
            difficulty=3,
            avoid_stems=existing_stems,
        )
        new_questions = []
        for gq in generated:
            q = Question(
                topic_id=topic_id,
                stem=gq.stem,
                options=gq.options,
                correct_index=gq.correct_index,
                explanation=gq.explanation,
                difficulty=gq.difficulty,
                source="ai_generated",
            )
            db.add(q)
            new_questions.append(q)
        await db.flush()
        return new_questions
    except Exception as e:
        logger.warning(f"AI generation failed for {topic_name}: {e}")
        return []


@router.post("/start", response_model=TestOut)
async def start_test(req: TestStartRequest, db: AsyncSession = Depends(get_db)):
    """Create a new test session — uses seed questions + AI-generated fill."""

    # Fetch existing questions for the requested topics
    stmt = (
        select(Question)
        .where(Question.topic_id.in_(req.topic_ids))
        .order_by(func.random())
    )
    result = await db.execute(stmt)
    all_available = list(result.scalars().all())

    questions = all_available[:req.num_questions]
    shortfall = req.num_questions - len(questions)

    # If we don't have enough questions, generate more with AI
    if shortfall > 0:
        logger.info(f"Need {shortfall} more questions — generating with AI...")
        existing_stems = [q.stem for q in all_available]

        # Distribute generation across the requested topics
        topics_to_gen = []
        for tid in req.topic_ids:
            topic = await db.get(Topic, tid)
            if topic:
                subject = await db.get(Subject, topic.subject_id)
                topics_to_gen.append((tid, subject.name if subject else "", topic.name))

        if topics_to_gen:
            per_topic = max(1, shortfall // len(topics_to_gen))
            for tid, subj_name, topic_name in topics_to_gen:
                if shortfall <= 0:
                    break
                gen_count = min(per_topic + 1, shortfall)
                new_qs = await _generate_for_topic(
                    tid, subj_name, topic_name, gen_count, existing_stems, db
                )
                questions.extend(new_qs)
                existing_stems.extend(q.stem for q in new_qs)
                shortfall -= len(new_qs)

    if not questions:
        raise HTTPException(404, "No questions found and AI generation failed for the selected topics.")

    # Trim to requested count
    questions = questions[:req.num_questions]

    # Create the test
    test = Test(
        user_id=req.user_id,
        mode=req.mode,
        topic_ids=req.topic_ids,
        duration_seconds=req.duration_seconds,
    )
    db.add(test)
    await db.flush()

    # Attach questions
    test_questions = []
    for i, q in enumerate(questions):
        tq = TestQuestion(test_id=test.id, question_id=q.id, position=i + 1)
        db.add(tq)
        test_questions.append(tq)

    await db.commit()
    await db.refresh(test)

    # Build topic/subject name lookup for badges
    topic_name_map: dict[int, tuple[str, str]] = {}
    for q in questions:
        if q.topic_id not in topic_name_map:
            topic = await db.get(Topic, q.topic_id)
            subject = await db.get(Subject, topic.subject_id) if topic else None
            topic_name_map[q.topic_id] = (
                topic.name if topic else "",
                subject.name if subject else "",
            )

    # Build response
    return TestOut(
        id=test.id,
        mode=test.mode,
        duration_seconds=test.duration_seconds,
        started_at=test.started_at,
        questions=[
            TestQuestionOut(
                position=tq.position,
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


async def _post_submit_work(test_id: int, user_id: int):
    """Background task: update skills + prepare adaptive test (runs after response is sent)."""
    from app.db import async_session
    async with async_session() as db:
        try:
            logger.info(f"[BG] Updating skills for test {test_id}...")
            await update_skills_after_test(test_id, db)
        except Exception as e:
            logger.error(f"[BG] Skill update failed: {e}")

        try:
            logger.info(f"[BG] Preparing next adaptive test for user {user_id}...")
            adaptive_id = await prepare_adaptive_test(user_id, db)
            if adaptive_id:
                logger.info(f"[BG] Next adaptive test staged: #{adaptive_id}")
        except Exception as e:
            logger.error(f"[BG] Adaptive prep failed: {e}")


@router.post("/{test_id}/submit", response_model=TestResultOut)
async def submit_test(test_id: int, req: TestSubmitRequest, db: AsyncSession = Depends(get_db)):
    """Submit answers for a test and compute results."""
    test = await db.get(Test, test_id)
    if not test:
        raise HTTPException(404, "Test not found.")
    if test.submitted_at:
        raise HTTPException(400, "Test already submitted.")

    # Mark submitted
    test.submitted_at = datetime.utcnow()

    # Build answer lookup
    answer_map = {a.question_id: a for a in req.answers}

    # Load test questions with their questions
    stmt = (
        select(TestQuestion)
        .where(TestQuestion.test_id == test_id)
        .order_by(TestQuestion.position)
    )
    result = await db.execute(stmt)
    tqs = result.scalars().all()

    question_results = []
    topic_stats: dict[int, dict] = {}
    topic_name_cache: dict[int, tuple[str, str]] = {}  # topic_id -> (topic_name, subject_name)
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

        # Update test_question
        tq.user_answer_index = user_answer
        tq.time_spent_ms = time_ms

        # Record attempt
        if user_answer is not None:
            attempted += 1
            attempt = Attempt(
                user_id=test.user_id,
                question_id=q.id,
                was_correct=was_correct,
                time_spent_ms=time_ms,
            )
            db.add(attempt)
            if was_correct:
                correct_count += 1
            else:
                wrong_count += 1

        total_time += time_ms

        # Topic stats accumulation
        tid = q.topic_id
        if tid not in topic_stats:
            topic_stats[tid] = {"name": topic.name, "total": 0, "correct": 0, "time": 0}
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

    # --- Kick off skill update + adaptive prep in background (non-blocking) ---
    asyncio.create_task(_post_submit_work(test_id, test.user_id))

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


@router.get("/next-adaptive")
async def get_next_adaptive(user_id: int, db: AsyncSession = Depends(get_db)):
    """Check if an adaptive test is ready for the user."""
    stmt = (
        select(Test)
        .where(Test.user_id == user_id)
        .where(Test.mode == "adaptive")
        .where(Test.submitted_at.is_(None))
        .order_by(Test.started_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    test = result.scalar_one_or_none()

    if not test:
        return {"ready": False, "test_id": None}

    # Load its questions
    stmt = (
        select(TestQuestion)
        .where(TestQuestion.test_id == test.id)
        .order_by(TestQuestion.position)
    )
    result = await db.execute(stmt)
    tqs = result.scalars().all()

    questions = []
    topic_name_map: dict[int, tuple[str, str]] = {}
    for tq in tqs:
        q = await db.get(Question, tq.question_id)
        if q:
            if q.topic_id not in topic_name_map:
                topic = await db.get(Topic, q.topic_id)
                subject = await db.get(Subject, topic.subject_id) if topic else None
                topic_name_map[q.topic_id] = (
                    topic.name if topic else "",
                    subject.name if subject else "",
                )
            t_name, s_name = topic_name_map.get(q.topic_id, ("", ""))
            questions.append(TestQuestionOut(
                position=tq.position,
                question=QuestionOut(
                    id=q.id,
                    stem=q.stem,
                    options=q.options,
                    difficulty=q.difficulty,
                    topic_id=q.topic_id,
                    topic_name=t_name,
                    subject_name=s_name,
                ),
            ))

    return {
        "ready": True,
        "test": TestOut(
            id=test.id,
            mode=test.mode,
            duration_seconds=test.duration_seconds,
            started_at=test.started_at,
            questions=questions,
        ),
    }
