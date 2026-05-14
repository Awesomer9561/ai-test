"""Adaptive test question builder — assembles a personalised question set based on user skills.

Called synchronously from the test-start endpoint when mode="adaptive".
AI-generated questions are persisted to the DB so they enter the normal rotation for future tests.
"""

import logging
import random
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question, UserSkill, Topic, Subject
from app.ai.generator import question_generator

logger = logging.getLogger(__name__)

# Composition mix for a 10-question adaptive test
WEAK_RATIO = 0.60      # 60% from weak topics (may be AI-generated)
MEDIUM_RATIO = 0.25    # 25% from medium topics (DB only)
STRONG_RATIO = 0.15    # 15% maintenance from strong topics (DB only)

WEAK_THRESHOLD = 0.4
STRONG_THRESHOLD = 0.7


async def build_adaptive_questions(
    user_id: int,
    num_questions: int,
    db: AsyncSession,
) -> list[Question]:
    """
    Build a personalised question list for an adaptive test.

    For weak topics, new AI questions are generated and saved to DB so they
    enter the normal seed rotation for future tests.
    Returns up to num_questions Question ORM objects (already flushed to DB).
    """
    # Load skill data
    stmt = select(UserSkill).where(UserSkill.user_id == user_id).order_by(UserSkill.mastery_score)
    result = await db.execute(stmt)
    skills = result.scalars().all()

    if not skills:
        logger.info(f"No skill data for user {user_id} — falling back to random questions.")
        return []

    weak = [s for s in skills if s.mastery_score < WEAK_THRESHOLD]
    medium = [s for s in skills if WEAK_THRESHOLD <= s.mastery_score < STRONG_THRESHOLD]
    strong = [s for s in skills if s.mastery_score >= STRONG_THRESHOLD]

    # Ensure buckets are non-empty by falling back up the chain
    if not weak:
        weak = medium[:3]
    if not medium:
        medium = strong[:2]

    n_weak = max(1, round(num_questions * WEAK_RATIO))
    n_medium = max(1, round(num_questions * MEDIUM_RATIO))
    n_strong = num_questions - n_weak - n_medium

    collected: list[Question] = []

    # ── Weak topics: prefer AI generation, top up from DB ──────────────────
    weak_slots = n_weak // max(len(weak[:4]), 1) + 1
    for skill in weak[:4]:
        topic = await db.get(Topic, skill.topic_id)
        if not topic:
            continue
        subject = await db.get(Subject, topic.subject_id)
        subject_name = subject.name if subject else ""

        # Fetch what's already in DB for this topic
        stmt = (
            select(Question)
            .where(Question.topic_id == skill.topic_id)
            .where(Question.difficulty <= 4)
            .order_by(func.random())
            .limit(weak_slots)
        )
        result = await db.execute(stmt)
        existing = list(result.scalars().all())

        # Generate AI questions for the shortfall, targeting difficulty just above their struggle level
        needed = max(0, weak_slots - len(existing))
        if needed > 0:
            target_diff = min(5, max(1, round(skill.mastery_score * 5) + 1))
            try:
                existing_stems = [q.stem for q in existing]
                generated = await question_generator.generate_questions(
                    subject=subject_name,
                    topic=topic.name,
                    count=needed,
                    difficulty=target_diff,
                    avoid_stems=existing_stems,
                )
                for gq in generated:
                    new_q = Question(
                        topic_id=skill.topic_id,
                        stem=gq.stem,
                        options=gq.options,
                        correct_index=gq.correct_index,
                        explanation=gq.explanation,
                        difficulty=gq.difficulty,
                        source="ai_generated",
                    )
                    db.add(new_q)
                    existing.append(new_q)
                await db.flush()
                logger.info(f"Generated {len(generated)} questions for weak topic '{topic.name}'")
            except Exception as e:
                logger.warning(f"AI gen failed for weak topic '{topic.name}': {e}")

        collected.extend(existing)

    # ── Medium topics: DB only ──────────────────────────────────────────────
    med_slots = max(1, n_medium // max(len(medium[:3]), 1))
    for skill in medium[:3]:
        stmt = (
            select(Question)
            .where(Question.topic_id == skill.topic_id)
            .order_by(func.random())
            .limit(med_slots + 1)
        )
        result = await db.execute(stmt)
        collected.extend(result.scalars().all())

    # ── Strong topics: easy/medium maintenance only ─────────────────────────
    str_slots = max(1, n_strong // max(len(strong[:2]), 1))
    for skill in strong[:2]:
        stmt = (
            select(Question)
            .where(Question.topic_id == skill.topic_id)
            .where(Question.difficulty <= 3)
            .order_by(func.random())
            .limit(str_slots + 1)
        )
        result = await db.execute(stmt)
        collected.extend(result.scalars().all())

    random.shuffle(collected)
    return collected[:num_questions]
