"""Question-level endpoints — AI explanations, etc."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question
from app.ai.generator import question_generator

router = APIRouter(prefix="/api/questions", tags=["questions"])


class ExplainRequest(BaseModel):
    user_answer_index: int | None = None


class ExplainResponse(BaseModel):
    explanation: str


@router.post("/{question_id}/explain", response_model=ExplainResponse)
async def explain_question(
    question_id: int,
    req: ExplainRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a personalized AI explanation for a question."""
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Question not found.")

    explanation = await question_generator.generate_explanation(
        stem=question.stem,
        options=question.options,
        correct_index=question.correct_index,
        user_answer_index=req.user_answer_index,
    )

    # Cache the explanation if the question didn't have one
    if not question.explanation:
        question.explanation = explanation
        await db.commit()

    return ExplainResponse(explanation=explanation)
