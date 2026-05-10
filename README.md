# IBPS Adaptive Test App

AI-powered adaptive test platform for IBPS banking exams, running entirely on your local laptop with Ollama + Qwen models.

**Hardware:** i7 12th gen, 24GB RAM, RTX 3050 (4GB VRAM), Windows 11

---

## Setup Guide

### Step 1 — System-level prerequisites (one-time)

**NVIDIA Driver:** Install the latest driver from `nvidia.com/drivers`. Verify with `nvidia-smi` in PowerShell.

**Ollama:** Already installed. Now set these environment variables (Settings → System → About → Advanced system settings → Environment Variables → System variables):

| Variable | Value |
|---|---|
| `OLLAMA_MODELS` | `C:\AI\models` |
| `OLLAMA_MAX_LOADED_MODELS` | `2` |
| `OLLAMA_NUM_PARALLEL` | `2` |
| `OLLAMA_KEEP_ALIVE` | `5m` |

Restart the Ollama service after setting env vars (Services app → Ollama → Restart, or reboot).

**Pull the models** (PowerShell — takes 10-15 min on first download):

```powershell
ollama pull qwen2.5:3b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5-math:7b-instruct-q4_K_M
ollama pull mxbai-embed-large
ollama list   # confirm all four appear
```

**Smoke test:**

```powershell
ollama run qwen2.5:3b-instruct-q4_K_M "Reply with the JSON {\"ok\":true}"
curl http://localhost:11434/api/tags   # should return JSON with your models
```

**Other tools:** Python 3.11+ (`python.org`, check "Add to PATH"), then `pip install uv`. Node.js 20 LTS (`nodejs.org`). Git for Windows (`git-scm.com`).

---

### Step 2 — Create folder structure

```powershell
mkdir C:\AI\projects, C:\AI\shared\docs, C:\AI\shared\scripts -Force
```

Copy or move this entire `ibps-adaptive` folder into `C:\AI\projects\`.

---

### Step 3 — Backend setup

```powershell
cd C:\AI\projects\ibps-adaptive\backend

# Create .env from example
copy .env.example .env

# Create virtual environment and install dependencies
uv venv
uv pip install -r pyproject.toml
# OR if uv supports it:
# uv sync

# Start the server
uv run uvicorn app.main:app --reload --port 8001
```

On first start, the app will automatically create the SQLite database and seed it with subjects, topics, and ~50 IBPS-style questions.

**Verify:** Open `http://localhost:8001/health` — you should see `{"status":"ok", ...}`.

---

### Step 4 — Frontend setup

Open a **new PowerShell tab**:

```powershell
cd C:\AI\projects\ibps-adaptive\frontend

npm install
npm run dev
```

**Open:** `http://localhost:5173` — you should see the Topic Select page.

---

### Step 5 — End-to-end test

1. Go to `http://localhost:5173`
2. Select a few topics and click **Start Test**
3. Answer questions and submit
4. View your results with per-topic breakdown
5. Visit **Dashboard** and click **Ping Ollama** to verify AI connectivity

---

## Architecture

```
Ollama (localhost:11434) ← shared AI service
    ↑
FastAPI (localhost:8001) ← IBPS backend, SQLite + ChromaDB
    ↑
React (localhost:5173)   ← Vite dev server, proxies /api to backend
```

## What's included (Phase 0)

- Full FastAPI backend with async SQLite, all ORM models, and REST endpoints
- Seed data: 5 IBPS subjects, 43 topics, ~50 representative MCQs across all subjects
- React frontend with Topic Select, Test (with timer + palette), Result (with per-question review), and Dashboard pages
- Ollama client wrapper with retry logic and health checks
- CORS configured for Vite dev server
- Prompt templates for question generation and explanations (used in Phase 1)

## Next steps (Phase 1)

- Generate fresh questions via Ollama during test start
- Add the APScheduler background worker for adaptive question generation
- Expand seed bank with more questions per topic
- Add embedding-based deduplication via ChromaDB
