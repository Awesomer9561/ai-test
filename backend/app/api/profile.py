"""Simple user profile — login by name, no passwords."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/profile", tags=["profile"])


class LoginRequest(BaseModel):
    name: str
    exam_target: str = "IBPS PO"


class UserOut(BaseModel):
    id: int
    name: str
    exam_target: str

    model_config = {"from_attributes": True}


@router.post("/login", response_model=UserOut)
async def login_or_create(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Find user by name or create a new one. No password needed."""
    stmt = select(User).where(User.name == req.name.strip())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update exam target if changed
        if req.exam_target and req.exam_target != user.exam_target:
            user.exam_target = req.exam_target
            await db.commit()
        return user

    # Create new user
    user = User(name=req.name.strip(), exam_target=req.exam_target)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all existing users (for the profile picker)."""
    result = await db.execute(select(User).order_by(User.name))
    return result.scalars().all()
