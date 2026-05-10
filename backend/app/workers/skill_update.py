"""Mastery scoring — EWMA-based skill update after each test submission."""

import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Test, TestQuestion, Question, UserSkill, Topic

logger = logging.getLogger(__name__)

# EWMA decay factor — lower = slower adaptation (more stable)
ALPHA = 0.15

# Difficulty weight: harder questions count more toward mastery changes
DIFFICULTY_WEIGHTS = {1: 0.6, 2: 0.8, 3: 1.0, 4: 1.2, 5: 1.4}

# Time penalty: if you took too long, reduce mastery credit even if correct
# Threshold in ms — beyond this, you get partial credit
TIME_THRESHOLD_MS = 60_000  # 60 seconds


def _compute_performance_score(was_correct: bool, difficulty: int, time_ms: int) -> float:
    """
    Compute a 0-1 performance score for a single question attempt.
    Factors: correctness, difficulty weight, time taken.
    """
    if not was_correct:
        # Wrong answer: negative signal, weighted by difficulty
        # Harder questions you get wrong hurt less than easy ones
        weight = DIFFICULTY_WEIGHTS.get(difficulty, 1.0)
        return 0.0 * weight  # Still 0 but weight affects EWMA impact

    # Correct answer: base score of 1.0, penalized for excessive time
    time_factor = 1.0
    if time_ms > TIME_THRESHOLD_MS:
        # Reduce credit for slow answers (min 0.5 credit)
        time_factor = max(0.5, TIME_THRESHOLD_MS / time_ms)

    return 1.0 * time_factor


async def update_skills_after_test(test_id: int, db: AsyncSession) -> dict[int, float]:
    """
    Recompute mastery for all topics in a submitted test.
    Returns {topic_id: new_mastery_score} for use by adaptive prep.
    """
    test = await db.get(Test, test_id)
    if not test or not test.submitted_at:
        return {}

    # Load all test questions
    stmt = select(TestQuestion).where(TestQuestion.test_id == test_id)
    result = await db.execute(stmt)
    tqs = result.scalars().all()

    # Group by topic
    topic_attempts: dict[int, list[tuple[bool, int, int]]] = {}  # topic_id -> [(correct, difficulty, time_ms)]

    for tq in tqs:
        if tq.user_answer_index is None:
            continue  # skip unanswered
        question = await db.get(Question, tq.question_id)
        if not question:
            continue
        was_correct = tq.user_answer_index == question.correct_index
        tid = question.topic_id
        if tid not in topic_attempts:
            topic_attempts[tid] = []
        topic_attempts[tid].append((was_correct, question.difficulty, tq.time_spent_ms))

    # Update mastery for each topic
    updated_skills = {}

    for topic_id, attempts in topic_attempts.items():
        # Get or create UserSkill
        stmt = select(UserSkill).where(
            UserSkill.user_id == test.user_id,
            UserSkill.topic_id == topic_id,
        )
        result = await db.execute(stmt)
        skill = result.scalar_one_or_none()

        if not skill:
            skill = UserSkill(
                user_id=test.user_id,
                topic_id=topic_id,
                mastery_score=0.5,
                accuracy=0.0,
                avg_time_ms=0,
            )
            db.add(skill)
            await db.flush()

        # Compute average performance for this test session
        scores = [
            _compute_performance_score(correct, diff, time_ms)
            for correct, diff, time_ms in attempts
        ]
        session_performance = sum(scores) / len(scores) if scores else 0.5

        # EWMA update
        old_mastery = skill.mastery_score
        new_mastery = (1 - ALPHA) * old_mastery + ALPHA * session_performance
        new_mastery = max(0.0, min(1.0, new_mastery))  # clamp

        # Update accuracy (simple running stat)
        correct_count = sum(1 for c, _, _ in attempts if c)
        session_accuracy = correct_count / len(attempts) if attempts else 0
        skill.accuracy = (1 - ALPHA) * skill.accuracy + ALPHA * session_accuracy

        # Update avg time
        avg_time = sum(t for _, _, t in attempts) // len(attempts) if attempts else 0
        skill.avg_time_ms = int((1 - ALPHA) * skill.avg_time_ms + ALPHA * avg_time)

        skill.mastery_score = new_mastery
        skill.last_updated = datetime.utcnow()

        updated_skills[topic_id] = new_mastery
        logger.info(
            f"  Topic {topic_id}: mastery {old_mastery:.3f} → {new_mastery:.3f} "
            f"(session perf={session_performance:.2f}, {len(attempts)} attempts)"
        )

    await db.commit()
    logger.info(f"Updated skills for test {test_id}: {len(updated_skills)} topics")
    return updated_skills
