"""Subjects and topics API."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Subject
from app.schemas import SubjectOut

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("/", response_model=list[SubjectOut])
async def list_subjects(db: AsyncSession = Depends(get_db)):
    """Return all subjects with their topics."""
    result = await db.execute(
        select(Subject).options(selectinload(Subject.topics)).order_by(Subject.id)
    )
    return result.scalars().all()
