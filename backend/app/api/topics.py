"""Subjects and topics API."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Subject
from app.schemas import SubjectOut

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("/", response_model=list[SubjectOut])
async def list_subjects(
    exam_category: Optional[str] = Query(None, description="Filter by 'banking' or 'ug_entrance'"),
    db: AsyncSession = Depends(get_db),
):
    """Return subjects with their topics, optionally filtered by exam category."""
    stmt = select(Subject).options(selectinload(Subject.topics)).order_by(Subject.id)
    if exam_category:
        stmt = stmt.where(Subject.exam_category == exam_category)
    result = await db.execute(stmt)
    return result.scalars().all()
