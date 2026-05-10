"""Results and user skill endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import UserSkill, Topic
from app.schemas import UserSkillOut

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/skills/{user_id}", response_model=list[UserSkillOut])
async def get_user_skills(user_id: int, db: AsyncSession = Depends(get_db)):
    """Return mastery scores for all topics the user has attempted."""
    stmt = (
        select(UserSkill)
        .where(UserSkill.user_id == user_id)
        .order_by(UserSkill.mastery_score.asc())
    )
    result = await db.execute(stmt)
    skills = result.scalars().all()

    out = []
    for s in skills:
        topic = await db.get(Topic, s.topic_id)
        out.append(UserSkillOut(
            topic_id=s.topic_id,
            topic_name=topic.name if topic else "Unknown",
            mastery_score=round(s.mastery_score, 3),
            accuracy=round(s.accuracy, 2),
            avg_time_ms=s.avg_time_ms,
        ))
    return out
