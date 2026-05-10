"""Load seed subjects, topics, and questions into the database on first run."""

import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subject, Topic, Question, User

SEED_DIR = Path(__file__).parent


async def seed_database(db: AsyncSession):
    """Populate subjects, topics, seed questions, and a default user if empty."""

    # Check if already seeded
    result = await db.execute(select(Subject).limit(1))
    if result.scalar():
        return  # already seeded

    print("🌱 Seeding database...")

    # --- Load subjects and topics ---
    with open(SEED_DIR / "subjects.json") as f:
        subjects_data = json.load(f)

    topic_map: dict[str, int] = {}  # "Subject|Topic" → topic.id

    for subj_data in subjects_data:
        subject = Subject(name=subj_data["name"])
        db.add(subject)
        await db.flush()

        for topic_name in subj_data["topics"]:
            topic = Topic(subject_id=subject.id, name=topic_name)
            db.add(topic)
            await db.flush()
            topic_map[f"{subj_data['name']}|{topic_name}"] = topic.id

    # --- Load seed questions ---
    question_files = {
        "Quantitative Aptitude": "quant.json",
        "Reasoning Ability": "reasoning.json",
        "English Language": "english.json",
        "General & Banking Awareness": "ga.json",
        "Computer Awareness": "computer.json",
    }

    total_questions = 0
    for subject_name, filename in question_files.items():
        filepath = SEED_DIR / "questions" / filename
        if not filepath.exists():
            print(f"  ⚠ Seed file not found: {filename}")
            continue

        with open(filepath) as f:
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
                total_questions += 1

    # --- Default user ---
    default_user = User(name="Parvez", exam_target="IBPS PO")
    db.add(default_user)

    await db.commit()
    print(f"✅ Seeded {len(subjects_data)} subjects, {len(topic_map)} topics, {total_questions} questions, 1 default user.")
