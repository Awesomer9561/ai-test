"""Thin async wrapper around the Ollama HTTP API."""

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from app.config import settings


class OllamaClient:
    """Async client for Ollama's REST API on localhost."""

    def __init__(self):
        self.base_url = settings.ollama_host
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Core generation ──

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str = "",
        temperature: float = 0.7,
        format_json: bool = False,
    ) -> str:
        """Send a prompt to Ollama and return the full response text."""
        client = await self._get_client()
        payload = {
            "model": model or settings.model_live,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"

        resp = await client.post("/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["response"]

    # ── Embeddings ──

    async def embed(self, text: str) -> list[float]:
        """Get an embedding vector for a single text."""
        client = await self._get_client()
        resp = await client.post(
            "/api/embed",
            json={"model": settings.model_embed, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]

    # ── Health check ──

    async def health(self) -> dict:
        """Check Ollama connectivity and return loaded models."""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            tags = resp.json()
            model_names = [m["name"] for m in tags.get("models", [])]
            return {"connected": True, "models": model_names}
        except Exception as e:
            return {"connected": False, "models": [], "error": str(e)}


# Singleton instance
ollama = OllamaClient()
