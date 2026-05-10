"""Application configuration — reads from .env or environment variables."""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Ollama
    ollama_host: str = "http://localhost:11434"
    model_live: str = "qwen2.5:3b-instruct-q4_K_M"
    model_bg: str = "qwen2.5:7b-instruct-q4_K_M"
    model_math: str = "qwen2.5-math:7b-instruct-q4_K_M"
    model_embed: str = "mxbai-embed-large"

    # Database (PostgreSQL)
    database_url: str = "postgresql+asyncpg://postgres:9561@localhost:5432/ibps_adaptive"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # AI generation
    max_retries: int = 3
    dedupe_similarity_threshold: float = 0.92

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_model_for_subject(self, subject: str) -> str:
        """Route to the math-specialist model for Quant, general 7B for everything else."""
        if subject.lower() in ("quantitative aptitude", "quant"):
            return self.model_math
        return self.model_bg


settings = Settings()
