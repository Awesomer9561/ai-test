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

# ── Standard composition (default) ───────────────────────────────────────────
WEAK_RATIO = 0.60      # 60% from weak topics (may be AI-generated)
MEDIUM_RATIO = 0.25    # 25% from medium topics (DB only)
STRONG_RATIO = 0.15    # 15% maintenance from strong topics (DB only)

# ── High-performer challenge composition ──────────────────────────────────────
HP_WEAK_RATIO = 0.20      # 20% — just the critical gaps
HP_MEDIUM_RATIO = 0.30    # 30% — consolidation
HP_STRONG_RATIO = 0.50    # 50% — hard/expert challenge on strong topics

WEAK_THRESHOLD = 0.4
STRONG_THRESHOLD = 0.7
HP_MIN_TOPICS = 3          # need at least this many tracked topics to judge HP
HP_STRONG_RATIO_TRIGGER = 0.60  # 60%+ of topics must be strong


def is_high_performer(skills: list[UserSkill]) -> bool:
    """Return True if ≥ 60% of tracked topics are at strong mastery (≥ 0.70).

    Requires at least HP_MIN_TOPICS data points to avoid false positives
    on users who have only completed one or two topics.
    """
    if len(skills) < HP_MIN_TOPICS:
        return False
    strong = sum(1 for s in skills if s.mastery_score >= STRONG_THRESHOLD)
    return (strong / len(skills)) >= HP_STRONG_RATIO_TRIGGER


async def _fetch_or_generate_questions(
    db: AsyncSession,
    skill: UserSkill,
    topic: Topic,
    subject_name: str,
    slots: int,
    *,
    min_difficulty: int = 1,
    max_difficulty: int = 4,
    target_ai_difficulty: int | None = None,
    generate_if_short: bool = True,
) -> list[Question]:
    """Fetch existing questions for a topic and optionally generate AI ones for the shortfall."""
    stmt = (
        select(Question)
        .where(Question.topic_id == skill.topic_id)
        .where(Question.difficulty >= min_difficulty)
        .where(Question.difficulty <= max_difficulty)
        .order_by(func.random())
        .limit(slots)
    )
    result = await db.execute(stmt)
    existing = list(result.scalars().all())

    if not generate_if_short:
        return existing

    needed = max(0, slots - len(existing))
    if needed > 0:
        ai_diff = target_ai_difficulty or min(5, max(1, round(skill.mastery_score * 5) + 1))
        try:
            existing_stems = [q.stem for q in existing]
            generated = await question_generator.generate_questions(
                subject=subject_name,
                topic=topic.name,
                count=needed,
                difficulty=ai_diff,
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
            logger.info(f"Generated {len(generated)} AI questions for topic '{topic.name}' (diff={ai_diff})")
        except Exception as e:
            logger.warning(f"AI gen failed for topic '{topic.name}': {e}")

    return existing


async def build_adaptive_questions(
    user_id: int,
    num_questions: int,
    db: AsyncSession,
    *,
    force_challenge: bool = False,
) -> list[Question]:
    """
    Build a personalised question list for an adaptive test.

    Standard mode:  60% weak, 25% medium, 15% strong (easy maintenance).
    Challenge mode: 20% weak, 30% medium, 50% strong at difficulty ≥4.
                    Activated automatically for HP users OR via force_challenge=True.

    For weak topics AI questions are always generated for the shortfall.
    For strong topics in challenge mode, AI questions at difficulty 5 are also generated.
    Generated questions are saved to DB and enter the normal seed rotation.

    Returns up to num_questions Question ORM objects (already flushed to DB).
    Returns empty list if the user has no skill data yet.
    """
    stmt = select(UserSkill).where(UserSkill.user_id == user_id).order_by(UserSkill.mastery_score)
    result = await db.execute(stmt)
    skills = result.scalars().all()

    if not skills:
        logger.info(f"No skill data for user {user_id} — falling back to random questions.")
        return []

    hp = force_challenge or is_high_performer(list(skills))

    weak = [s for s in skills if s.mastery_score < WEAK_THRESHOLD]
    medium = [s for s in skills if WEAK_THRESHOLD <= s.mastery_score < STRONG_THRESHOLD]
    strong = [s for s in skills if s.mastery_score >= STRONG_THRESHOLD]

    # Ensure buckets are non-empty by cascading fallbacks
    if not weak:
        weak = medium[:3]
    if not medium:
        medium = strong[:2] if strong else weak[:2]

    if hp:
        n_weak = max(1, round(num_questions * HP_WEAK_RATIO))
        n_medium = max(1, round(num_questions * HP_MEDIUM_RATIO))
        n_strong = num_questions - n_weak - n_medium
        weak_limit = 2
        strong_limit = 5
    else:
        n_weak = max(1, round(num_questions * WEAK_RATIO))
        n_medium = max(1, round(num_questions * MEDIUM_RATIO))
        n_strong = num_questions - n_weak - n_medium
        weak_limit = 4
        strong_limit = 2

    collected: list[Question] = []

    # ── Weak topics ────────────────────────────────────────────────────────────
    weak_pool = weak[:weak_limit]
    weak_slots = max(1, n_weak // max(len(weak_pool), 1)) + 1
    for skill in weak_pool:
        topic = await db.get(Topic, skill.topic_id)
        if not topic:
            continue
        subject = await db.get(Subject, topic.subject_id)
        qs = await _fetch_or_generate_questions(
            db, skill, topic, subject.name if subject else "",
            slots=weak_slots,
            min_difficulty=1,
            max_difficulty=4,
            generate_if_short=True,
        )
        collected.extend(qs)

    # ── Medium topics: DB only ─────────────────────────────────────────────────
    medium_pool = medium[:3]
    med_slots = max(1, n_medium // max(len(medium_pool), 1))
    for skill in medium_pool:
        topic = await db.get(Topic, skill.topic_id)
        if not topic:
            continue
        subject = await db.get(Subject, topic.subject_id)
        qs = await _fetch_or_generate_questions(
            db, skill, topic, subject.name if subject else "",
            slots=med_slots + 1,
            min_difficulty=1,
            max_difficulty=5,
            generate_if_short=False,  # no AI gen for medium topics
        )
        collected.extend(qs)

    # ── Strong topics ─────────────────────────────────────────────────────────
    strong_pool = strong[:strong_limit]
    str_slots = max(1, n_strong // max(len(strong_pool), 1))
    for skill in strong_pool:
        topic = await db.get(Topic, skill.topic_id)
        if not topic:
            continue
        subject = await db.get(Subject, topic.subject_id)

        if hp:
            # Challenge mode: hard questions only (difficulty ≥ 4), AI-generate if needed
            qs = await _fetch_or_generate_questions(
                db, skill, topic, subject.name if subject else "",
                slots=str_slots + 1,
                min_difficulty=4,
                max_difficulty=5,
                target_ai_difficulty=5,
                generate_if_short=True,
            )
        else:
            # Standard mode: easy maintenance only (difficulty ≤ 3)
            qs = await _fetch_or_generate_questions(
                db, skill, topic, subject.name if subject else "",
                slots=str_slots + 1,
                min_difficulty=1,
                max_difficulty=3,
                generate_if_short=False,
            )
        collected.extend(qs)

    random.shuffle(collected)
    return collected[:num_questions]
