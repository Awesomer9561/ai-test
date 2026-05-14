"""Simple user profile — login by name, no passwords."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/profile", tags=["profile"])

BANKING_EXAMS = ["IBPS PO", "IBPS Clerk", "IBPS RRB", "SBI PO", "SBI Clerk"]
UG_EXAMS = ["JEE Main", "JEE Advanced", "WBJEE", "CUET"]
ALL_EXAMS = BANKING_EXAMS + UG_EXAMS

EXAM_CATEGORY_MAP = {exam: "banking" for exam in BANKING_EXAMS}
EXAM_CATEGORY_MAP.update({exam: "ug_entrance" for exam in UG_EXAMS})


class LoginRequest(BaseModel):
    name: str
    exam_target: str = "IBPS PO"


class UserOut(BaseModel):
    id: int
    name: str
    exam_target: str
    exam_category: str = "banking"

    model_config = {"from_attributes": True}


class ExamListOut(BaseModel):
    banking: list[str]
    ug_entrance: list[str]


@router.get("/exams", response_model=ExamListOut)
async def list_exams():
    """Return available exam targets grouped by category."""
    return ExamListOut(banking=BANKING_EXAMS, ug_entrance=UG_EXAMS)


@router.post("/login", response_model=UserOut)
async def login_or_create(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Find user by name or create a new one. No password needed."""
    stmt = select(User).where(func.lower(User.name) == req.name.strip().lower())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        if req.exam_target and req.exam_target != user.exam_target:
            user.exam_target = req.exam_target
            await db.commit()
        category = EXAM_CATEGORY_MAP.get(user.exam_target, "banking")
        return UserOut(id=user.id, name=user.name, exam_target=user.exam_target, exam_category=category)

    user = User(name=req.name.strip(), exam_target=req.exam_target)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    category = EXAM_CATEGORY_MAP.get(user.exam_target, "banking")
    return UserOut(id=user.id, name=user.name, exam_target=user.exam_target, exam_category=category)


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all existing users (for the profile picker)."""
    result = await db.execute(select(User).order_by(User.name))
    users = result.scalars().all()
    return [
        UserOut(
            id=u.id,
            name=u.name,
            exam_target=u.exam_target,
            exam_category=EXAM_CATEGORY_MAP.get(u.exam_target, "banking"),
        )
        for u in users
    ]
