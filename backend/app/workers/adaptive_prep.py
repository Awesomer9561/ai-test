"""Adaptive test preparation — builds a targeted next test based on weak areas."""

import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Test, TestQuestion, Question, UserSkill, Topic, Subject
from app.ai.generator import question_generator

logger = logging.getLogger(__name__)

# Test composition mix
WEAK_RATIO = 0.60      # 60% from weak topics
MEDIUM_RATIO = 0.25    # 25% from medium topics
STRONG_RATIO = 0.15    # 15% maintenance from strong topics

# Mastery thresholds
WEAK_THRESHOLD = 0.4
STRONG_THRESHOLD = 0.7

DEFAULT_QUESTIONS = 10
DEFAULT_DURATION = 600  # 10 min


async def prepare_adaptive_test(user_id: int, db: AsyncSession) -> int | None:
    """
    Build and stage the next adaptive test for a user.
    Returns the test ID if successful, None otherwise.
    """
    # Get all user skills
    stmt = select(UserSkill).where(UserSkill.user_id == user_id).order_by(UserSkill.mastery_score)
    result = await db.execute(stmt)
    skills = result.scalars().all()

    if not skills:
        logger.info(f"No skills data for user {user_id} — can't build adaptive test yet.")
        return None

    # Categorize topics
    weak_topics = [s for s in skills if s.mastery_score < WEAK_THRESHOLD]
    medium_topics = [s for s in skills if WEAK_THRESHOLD <= s.mastery_score < STRONG_THRESHOLD]
    strong_topics = [s for s in skills if s.mastery_score >= STRONG_THRESHOLD]

    logger.info(
        f"User {user_id} skill breakdown: "
        f"{len(weak_topics)} weak, {len(medium_topics)} medium, {len(strong_topics)} strong"
    )

    # If no weak topics, pull from medium; if no medium either, just mix everything
    if not weak_topics:
        weak_topics = medium_topics[:3]
    if not medium_topics:
        medium_topics = strong_topics[:2]

    # Calculate question distribution
    total_questions = DEFAULT_QUESTIONS
    n_weak = max(1, round(total_questions * WEAK_RATIO))
    n_medium = max(1, round(total_questions * MEDIUM_RATIO))
    n_strong = total_questions - n_weak - n_medium

    # Collect questions for each category
    all_questions: list[Question] = []

    # --- Weak topic questions (prefer AI generation for these) ---
    for skill in weak_topics[:4]:  # Limit to top 4 weakest
        topic = await db.get(Topic, skill.topic_id)
        if not topic:
            continue
        subject = await db.get(Subject, topic.subject_id)
        subject_name = subject.name if subject else ""

        # Target difficulty just above where they struggle
        target_difficulty = 3  # middle difficulty for weak topics

        # Try to get existing questions first
        stmt = (
            select(Question)
            .where(Question.topic_id == skill.topic_id)
            .where(Question.difficulty <= target_difficulty + 1)
            .order_by(func.random())
            .limit(2)
        )
        result = await db.execute(stmt)
        existing = list(result.scalars().all())

        # Generate more if needed
        needed = max(0, (n_weak // min(len(weak_topics), 4)) - len(existing))
        if needed > 0:
            try:
                existing_stems = [q.stem for q in existing]
                generated = await question_generator.generate_questions(
                    subject=subject_name,
                    topic=topic.name,
                    count=needed,
                    difficulty=target_difficulty,
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
            except Exception as e:
                logger.warning(f"AI gen failed for weak topic {topic.name}: {e}")

        all_questions.extend(existing)

    # --- Medium topic questions (pull from DB) ---
    for skill in medium_topics[:3]:
        stmt = (
            select(Question)
            .where(Question.topic_id == skill.topic_id)
            .order_by(func.random())
            .limit(n_medium // min(len(medium_topics), 3) + 1)
        )
        result = await db.execute(stmt)
        all_questions.extend(result.scalars().all())

    # --- Strong topic questions (maintenance, easy-medium only) ---
    for skill in strong_topics[:2]:
        stmt = (
            select(Question)
            .where(Question.topic_id == skill.topic_id)
            .where(Question.difficulty <= 3)
            .order_by(func.random())
            .limit(n_strong // min(len(strong_topics), 2) + 1)
        )
        result = await db.execute(stmt)
        all_questions.extend(result.scalars().all())

    await db.flush()

    # Trim and shuffle
    import random
    random.shuffle(all_questions)
    all_questions = all_questions[:total_questions]

    if not all_questions:
        logger.warning(f"Could not assemble adaptive test for user {user_id}")
        return None

    # Create the staged adaptive test
    topic_ids = list(set(q.topic_id for q in all_questions))
    test = Test(
        user_id=user_id,
        mode="adaptive",
        topic_ids=topic_ids,
        duration_seconds=DEFAULT_DURATION,
    )
    db.add(test)
    await db.flush()

    for i, q in enumerate(all_questions):
        tq = TestQuestion(test_id=test.id, question_id=q.id, position=i + 1)
        db.add(tq)

    await db.commit()

    logger.info(
        f"Staged adaptive test #{test.id} for user {user_id}: "
        f"{len(all_questions)} questions across {len(topic_ids)} topics"
    )
    return test.id
