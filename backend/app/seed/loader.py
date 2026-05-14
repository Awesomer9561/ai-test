"""Load seed subjects, topics, and questions into the database on first run."""

import json
from pathlib import Path
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subject, Topic, Question, User

SEED_DIR = Path(__file__).parent

BANKING_QUESTION_FILES = {
    "Quantitative Aptitude": "quant.json",
    "Reasoning Ability": "reasoning.json",
    "English Language": "english.json",
    "General & Banking Awareness": "ga.json",
    "Computer Awareness": "computer.json",
}

UG_QUESTION_FILES = {
    "Physics": "physics.json",
    "Chemistry": "chemistry.json",
    "Mathematics": "mathematics_ug.json",
    "CUET English": "english_ug.json",
    "CUET General Test": "general_test.json",
}


async def _run_migration(db: AsyncSession):
    """Add exam_category column to subjects table if it doesn't already exist (PostgreSQL)."""
    try:
        await db.execute(text(
            "ALTER TABLE subjects ADD COLUMN IF NOT EXISTS exam_category VARCHAR(20) NOT NULL DEFAULT 'banking'"
        ))
        await db.execute(text(
            "UPDATE subjects SET exam_category = 'banking' WHERE exam_category IS NULL OR exam_category = ''"
        ))
        await db.commit()
    except Exception:
        await db.rollback()


async def _load_questions_for_subjects(
    db: AsyncSession,
    subjects_data: list[dict],
    question_files: dict[str, str],
    topic_map: dict[str, int],
) -> int:
    total = 0
    for subj_data in subjects_data:
        subject_name = subj_data["name"]
        filename = question_files.get(subject_name)
        if not filename:
            continue
        filepath = SEED_DIR / "questions" / filename
        if not filepath.exists():
            print(f"  ⚠ Seed file not found: {filename}")
            continue
        with open(filepath, encoding="utf-8") as f:
            topic_groups = json.load(f)
        for group in topic_groups:
            topic_name = group["topic"]
            key = f"{subject_name}|{topic_name}"
            topic_id = topic_map.get(key)
            if not topic_id:
                print(f"  ⚠ Topic not found in taxonomy: {key}")
                continue
            for q in group["questions"]:
                question = Question(
                    topic_id=topic_id,
                    stem=q["stem"],
                    options=q["options"],
                    correct_index=q["correct_index"],
                    explanation=q.get("explanation", ""),
                    difficulty=q.get("difficulty", 3),
                    source="seed",
                )
                db.add(question)
                total += 1
    return total


async def seed_database(db: AsyncSession):
    """Populate subjects, topics, seed questions, and a default user if empty."""

    await _run_migration(db)

    with open(SEED_DIR / "subjects.json", encoding="utf-8") as f:
        subjects_data = json.load(f)

    # Load existing subjects by name for idempotency
    result = await db.execute(select(Subject))
    existing_subjects = {s.name: s for s in result.scalars().all()}

    topic_map: dict[str, int] = {}  # "Subject|Topic" → topic.id
    new_subjects: list[dict] = []

    for subj_data in subjects_data:
        subj = existing_subjects.get(subj_data["name"])
        if subj:
            # Update exam_category if it was added later
            if subj.exam_category != subj_data["exam_category"]:
                subj.exam_category = subj_data["exam_category"]
            # Map existing topics
            result2 = await db.execute(select(Topic).where(Topic.subject_id == subj.id))
            for t in result2.scalars().all():
                topic_map[f"{subj.name}|{t.name}"] = t.id
        else:
            # New subject — create it
            subject = Subject(name=subj_data["name"], exam_category=subj_data["exam_category"])
            db.add(subject)
            await db.flush()
            for topic_name in subj_data["topics"]:
                topic = Topic(subject_id=subject.id, name=topic_name)
                db.add(topic)
                await db.flush()
                topic_map[f"{subj_data['name']}|{topic_name}"] = topic.id
            new_subjects.append(subj_data)

    await db.flush()

    # Check if we need a default user
    user_result = await db.execute(select(User).limit(1))
    if not user_result.scalar():
        db.add(User(name="Parvez", exam_target="IBPS PO"))

    total_questions = 0

    # Seed banking questions only on first run
    banking_seeded = any(s["name"] in BANKING_QUESTION_FILES for s in new_subjects)
    if banking_seeded or not existing_subjects:
        q_count = await _load_questions_for_subjects(
            db,
            [s for s in subjects_data if s["exam_category"] == "banking"],
            BANKING_QUESTION_FILES,
            topic_map,
        )
        total_questions += q_count

    # Seed UG questions for newly added UG subjects
    ug_new = [s for s in new_subjects if s["exam_category"] == "ug_entrance"]
    if ug_new:
        q_count = await _load_questions_for_subjects(db, ug_new, UG_QUESTION_FILES, topic_map)
        total_questions += q_count

    await db.commit()

    if new_subjects or total_questions:
        labels = [s["name"] for s in new_subjects]
        print(f"✅ Seeded new subjects: {labels}, {total_questions} questions added.")
    else:
        print("✅ Database already seeded — no changes needed.")
