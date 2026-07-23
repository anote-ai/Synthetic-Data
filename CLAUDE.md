# CLAUDE.md — Synthetic Data Repository Guide

This file provides context for AI assistants working in this codebase.

---

## Project Overview

**Anote Synthetic Data** is a multi-modal synthetic dataset generation platform. It exposes a unified REST API and Python SDK to generate synthetic text, image, video, audio, and PII datasets using LLMs and diffusion models.

**Primary components:**
- `server/` — Flask REST API + core generation logic
- `server/sdk/` — Installable Python client package (`anote-generate`)
- `frontend/` — React UI for interactive generation
- `other/api/` — Experimental FastAPI re-implementation (WIP)

---

## Repository Structure

```
Synthetic-Data/
├── server/
│   ├── app.py                        # Flask entrypoint — POST /public/generate
│   ├── requirements.txt              # Python dependencies
│   ├── api_endpoints/
│   │   └── handler.py                # Routes by task_type → modality generator
│   ├── database/
│   │   ├── db.py                     # DB helpers (incomplete stubs)
│   │   └── schema.sql                # MySQL schema (synthetic_requests table)
│   ├── generators/                   # One file per modality
│   │   ├── text.py                   # Stub — returns mock data
│   │   ├── image.py                  # DALL-E 3 + YOLO11 object detection
│   │   ├── video.py                  # Replicate API (Cog model) + OpenCV labeling
│   │   ├── audio.py                  # faster-whisper transcription
│   │   ├── PII.py                    # Async LLM-enhanced PII generation (most complex)
│   │   ├── Language.py               # Japanese Q&A from Wikipedia via GPT-4
│   │   └── agent.py                  # Multi-turn agent tool-call trace generation (OpenAI function calling)
│   ├── tests/
│   │   └── test_generate.py          # pytest for /public/generate endpoint
│   └── sdk/
│       ├── setup.py                  # Package: anote-generate v0.20
│       └── anote-generate/
│           ├── __init__.py           # Exports Anote class
│           ├── core.py               # AnoteGenerate client (requests-based)
│           └── examples/             # Usage examples + sample datasets
│               └── dataset/          # CSV, audio, video sample files
├── frontend/
│   ├── package.json                  # React 18.2, react-scripts 5.0
│   └── src/
│       ├── App.js                    # Form UI → calls http://localhost:5000/public/generate
│       ├── index.js
│       └── docs/                     # MkDocs documentation source
│           ├── mkdocs.yml
│           └── docs/                 # Markdown pages for SDK and API
├── other/
│   ├── api/                          # FastAPI alternative (experimental)
│   │   ├── main.py                   # FastAPI app with CORS middleware
│   │   ├── routes/generate.py        # /generate router
│   │   ├── schemas/generate.py       # Pydantic request model
│   │   └── generators/               # Parallel generator implementations
│   └── images/                       # Example synthetic image output datasets
├── api/                              # Empty placeholder
├── .gitignore
└── README.md
```

---

## Core Data Flow

```
HTTP POST /public/generate
    └─→ app.py           (JWT extraction, dispatch)
    └─→ handler.py       (route by task_type, log to DB)
    └─→ generators/X.py  (call external APIs, return list of dicts)
    └─→ JSON response    {"data": [{col: val, ...}, ...]}
```

### Unified Request Schema

```json
{
  "task_type": "text" | "image" | "video" | "audio" | "agent",
  "prompt": "string",
  "num_rows": 5,
  "columns": ["col1", "col2"],
  "examples": [{"col1": "val", "col2": "val"}],
  "params": {}
}
```

### Unified Response Schema

```json
{
  "data": [
    {"col1": "value", "col2": "value", "status": "succeeded"},
    ...
  ]
}
```

---

## Generators

Each generator follows this contract:

```python
def generate_{modality}_data(prompt, columns, num_rows, examples) -> list[dict]:
    ...
    # On success: {"col": val, ..., "status": "succeeded"}
    # On failure: {"status": "failed", "error": "..."}
```

| Generator | Status | External APIs | Key Notes |
|-----------|--------|---------------|-----------|
| `text.py` | Stub | None | Returns mock `"Generated col value N"` strings |
| `image.py` | Functional | OpenAI DALL-E 3, YOLO11 | Saves `generated_image_N.png` + `detected_image_N.png` |
| `video.py` | Functional | Replicate API | Polls every 10s; saves `video_N.mp4` + `video_N.json` |
| `audio.py` | Functional | faster-whisper | GPU (float16) or CPU (int8) auto-detection |
| `PII.py` | Comprehensive | OpenAI AsyncOpenAI | 14 PII types, semaphore-based concurrency (default 5) |
| `Language.py` | Comprehensive | OpenAI (gpt-4o-mini + gpt-4) | Japanese Q&A from ja.wikipedia.org |
| `agent.py` | Functional | OpenAI (gpt-4o-mini, function calling) | Generates multi-turn tool-call traces; configurable difficulty, tool set, and outcome distribution |

---

## Python SDK

```python
from anote_generate import Anote

client = Anote(api_key="your-key")
result = client.generate(
    task_type="text",
    columns=["question", "answer"],
    prompt="Generate Q&A pairs about Python",
    num_rows=10,
    examples=[{"question": "What is a list?", "answer": "An ordered collection"}]
)
```

- Base URL: `https://api.anote.ai`
- Auth: `Authorization: Bearer {api_key}`
- Raises exception on non-200 response
- Package version: `0.20` (in `server/sdk/setup.py`)

---

## Development Setup

### Backend (Flask)

```bash
cd server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Copy and fill in required env vars
cp .env.example .env  # (file does not exist yet — create manually)
python app.py
```

Required environment variables:
```
OPENAI_API_KEY=sk-...
REPLICATE_API_TOKEN=r8_...
```

### Frontend (React)

```bash
cd frontend
npm install
npm start   # Starts at http://localhost:3000
            # Calls Flask API at http://localhost:5000
```

### SDK Installation

```bash
cd server/sdk
pip install -e .
```

---

## Running Tests

```bash
cd server
pytest tests/
```

- Framework: `pytest`
- Only one test exists (`test_generate_text` in `tests/test_generate.py`)
- Tests the `/public/generate` endpoint via Flask test client
- No mocking of external APIs — tests with real API calls or need API keys

---

## Key Conventions

### Naming
- Functions: `snake_case` (e.g., `generate_image_data`, `store_generate_request`)
- Classes: `PascalCase` (e.g., `AnoteGenerate`, `GenerateRequest`)
- Constants: `UPPER_CASE` (e.g., `MODEL = "gpt-4o-mini"`)
- Files: `snake_case` for modules, `PascalCase` for some generators (e.g., `PII.py`, `Language.py`)

### Error Handling
- Generators use try-except and return `{"status": "failed", "error": str(e)}` rather than raising
- This allows partial success (some rows succeed, some fail) in batch generation
- Do not let exceptions propagate out of generator functions

### Async Pattern (PII.py, Language.py)
- Use `AsyncOpenAI` for concurrent LLM calls
- Use `asyncio.Semaphore` for rate limiting (default concurrency: 5)
- Use `tqdm` for progress bars on long-running batch operations

### Adding a New Generator
1. Create `server/generators/{modality}.py`
2. Implement `generate_{modality}_data(prompt, columns, num_rows, examples) -> list[dict]`
3. Import and wire into `server/api_endpoints/handler.py`
4. Add test case in `server/tests/test_generate.py`
5. Update `README.md` and this file

---

## Known Issues & Technical Debt

| Issue | Location | Severity |
|-------|----------|----------|
| Replicate API token hardcoded | `server/generators/video.py:24` | High |
| OpenAI key fallback to local file path | `server/generators/Language.py:9-10` | Medium |
| JWT auth decorator commented out | `server/app.py` | High |
| `setup.py` has hardcoded local developer path | `server/sdk/setup.py` | Medium |
| `db.py` has incomplete stubs | `server/database/db.py` | Medium |
| `schema.sql` marked TODO | `server/database/schema.sql` | Medium |
| `text.py` returns mock data only | `server/generators/text.py` | High |
| `.env.example` does not exist | repo root | Low |
| No CI/CD configuration | repo root | Medium |
| Only 1 test, no mocking of external APIs | `server/tests/` | Medium |

### Security Notes
- **Never hardcode API keys** — always use `os.getenv("KEY_NAME")` with python-dotenv
- `.env` is correctly gitignored
- The JWT auth decorator in `app.py` should be re-enabled before production use
- Add rate limiting before exposing the API publicly

---

## Architecture Notes

### Dual API Implementations
- `server/` (Flask): The primary/deployed implementation
- `other/api/` (FastAPI): Experimental rewrite with Pydantic schemas and cleaner structure
- The FastAPI version is **not** currently wired to the deployed system

### Database
- MySQL schema defined in `server/database/schema.sql`
- Logs each generation request (user, task_type, prompt, columns, num_rows)
- `db.py` helper functions are stubs — database integration is incomplete
- No ORM or migration tooling present

### Frontend → Backend
- React frontend hardcodes `http://localhost:5000` as the backend URL
- API key entered in the UI is passed as `Authorization: Bearer {key}`
- No authentication enforcement currently (commented out in `app.py`)

---

## File Size Notes

Several generator files are very large (auto-generated or evolved organically):
- `PII.py`: ~12,000 lines — includes extensive prompt templates and field generators
- `Language.py`: ~8,600 lines — includes Wikipedia content and Q&A examples
- `video.py`: ~5,400 lines — includes frame labeling logic and polling code

When editing these files, search for the specific function rather than reading the entire file.

---

## External Services Used

| Service | Used In | Purpose |
|---------|---------|---------|
| OpenAI (GPT-4o-mini, GPT-4, DALL-E 3) | image.py, PII.py, Language.py, other/api/ | LLM generation, image synthesis |
| Replicate API | video.py | Video generation (Cog model) |
| faster-whisper | audio.py | Audio transcription |
| Ultralytics YOLO11 | image.py | Object detection on generated images |
| Faker | PII.py | Synthetic PII value generation |
| ja.wikipedia.org | Language.py | Source content for Japanese Q&A |
