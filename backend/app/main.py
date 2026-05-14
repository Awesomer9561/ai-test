"""FastAPI application entry point with lifespan management."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db, async_session
from app.ai.ollama_client import ollama
from app.seed.loader import seed_database
from app.api import health, topics, tests, results, questions, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed data, warm Ollama. Shutdown: close clients."""
    # Startup
    print("🚀 Starting Adaptive Test App (Banking + UG Entrance)...")
    await init_db()

    async with async_session() as db:
        await seed_database(db)

    # Check Ollama connectivity
    status = await ollama.health()
    if status["connected"]:
        print(f"✅ Ollama connected — models: {status['models']}")
    else:
        print(f"⚠️  Ollama not reachable at configured host. Error: {status.get('error')}")
        print("   The app will work but AI features will fail until Ollama is running.")

    yield

    # Shutdown
    await ollama.close()
    print("👋 Shutting down.")


app = FastAPI(
    title="Adaptive Test App",
    description="AI-powered adaptive test platform for Banking (IBPS/SBI) and UG Entrance (JEE/WBJEE/CUET) exams",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(topics.router)
app.include_router(tests.router)
app.include_router(results.router)
app.include_router(questions.router)
app.include_router(profile.router)
