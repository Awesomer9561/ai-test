"""Health and connectivity endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.ai.ollama_client import ollama
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Full health check — Ollama connectivity + DB status."""
    ollama_status = await ollama.health()

    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok" if ollama_status["connected"] and db_ok else "degraded",
        ollama_connected=ollama_status["connected"],
        loaded_models=ollama_status["models"],
        db_ok=db_ok,
    )


@router.get("/ping")
async def ping():
    """Simple liveness probe."""
    return {"pong": True}


@router.get("/ping-ollama")
async def ping_ollama():
    """Test Ollama by generating a short response with the live model."""
    try:
        response = await ollama.generate(
            prompt='Reply with exactly: {"ok": true}',
            format_json=True,
            temperature=0.0,
        )
        return {"ollama_response": response, "success": True}
    except Exception as e:
        return {"ollama_response": None, "success": False, "error": str(e)}
