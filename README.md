# Anote Synthetic Data

[![CI](https://github.com/anote-ai/Synthetic-Data/actions/workflows/ci.yml/badge.svg)](https://github.com/anote-ai/Synthetic-Data/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/anote-generate)](https://pypi.org/project/anote-generate/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](server/sdk/LICENSE)

Multi-modal synthetic dataset generation platform. Generate text, image, audio, video, PII, tabular, code, and language datasets via a unified REST API or Python SDK.

If you are evaluating whether synthetic data is suitable for model training, see
[`Does synthetic data work well enough to train on?`](frontend/src/docs/docs/api-anote-generate/synthetic-data-faq.md).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/anote-ai/Synthetic-Data.git
cd Synthetic-Data

# 2. Configure
cp .env.example .env
# Fill in OPENAI_API_KEY (required) and REPLICATE_API_TOKEN (video only)

# 3. Start everything (Docker)
make docker-up

# 4. Verify
curl http://localhost:5000/health
# {"status": "ok"}
```

Or run the server manually:

```bash
cd server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py          # http://localhost:5000
```

Run the React frontend manually in a second terminal:

```bash
cd frontend
npm install
npm start              # http://localhost:3000
```

---

## Repository Structure

```
Synthetic-Data/
├── server/
│   ├── app.py                    # Flask entrypoint — all REST routes
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── api_endpoints/handler.py  # routes task_type → generator
│   ├── generators/               # one file per modality
│   │   ├── text.py               # OpenAI JSON-mode text rows
│   │   ├── image.py              # DALL-E 3 + YOLO11 detection
│   │   ├── video.py              # Replicate async + GPT-4o Vision
│   │   ├── audio.py              # faster-whisper TTS/ASR
│   │   ├── PII.py                # 14 PII types, async LLM
│   │   ├── Language.py           # multilingual Q&A, async
│   │   ├── tabular.py            # typed tabular, async
│   │   └── code.py               # code generation + validation
│   ├── utils/
│   │   ├── versioning.py         # dataset snapshot store
│   │   ├── export.py             # CSV/JSONL/Parquet export
│   │   └── quality.py            # completeness + LLM review
│   ├── database/
│   │   ├── db.py                 # MySQL pool, graceful fallback
│   │   └── schema.sql
│   └── tests/
├── server/sdk/                   # pip install anote-generate
│   ├── pyproject.toml
│   ├── anote-generate/
│   │   ├── __init__.py
│   │   └── core.py
│   └── CHANGELOG.md
├── frontend/                     # React 18 UI
│   ├── Dockerfile
│   └── src/App.js
├── docker-compose.yml
├── docker-compose.override.yml   # dev hot-reload
├── Makefile
└── .env.example
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key (text, image, PII, language, code) |
| `REPLICATE_API_TOKEN` | Video only | — | Replicate API token for video generation |
| `DB_HOST` | No | — | MySQL host; omit to disable DB logging |
| `DB_PORT` | No | `3306` | MySQL port |
| `DB_USER` | No | `root` | MySQL user |
| `DB_PASSWORD` | No | `""` | MySQL password |
| `DB_NAME` | No | `synthetic_data` | MySQL database name |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | CORS allowed origins (comma-separated) |
| `MAX_ROWS_PER_REQUEST` | No | `100` | Maximum rows per `/public/generate` call |
| `SYNTHETIC_OUTPUT_DIR` | No | `./outputs` | Directory for generated files and version snapshots |
| `REACT_APP_API_BASE_URL` | No | `http://localhost:5000` | Backend URL used by React frontend build |

---

## API Reference

All endpoints require `Content-Type: application/json` and an `Authorization: Bearer <token>` header.

### `GET /health`

Returns `{"status": "ok"}`. No auth required.

---

### `GET /public/generate/task-types`

Returns the task types supported by the generation API and the configured maximum row limit. No auth required.

---

### `POST /public/generate`

Generate a synthetic dataset.

**Request body:**
```json
{
  "task_type": "text",
  "prompt": "Generate Q&A pairs about Python programming",
  "num_rows": 10,
  "columns": ["question", "answer", "difficulty"],
  "examples": [
    {"question": "What is a list?", "answer": "An ordered collection", "difficulty": "easy"}
  ],
  "params": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_type` | string | Yes | `text` \| `image` \| `video` \| `audio` \| `agent` \| `pii` \| `language` \| `tabular` \| `code` |
| `prompt` | string | Yes | Natural language description of the dataset |
| `num_rows` | int | No | Rows to generate (default 5, max 100) |
| `columns` | list[str] | Yes | Output column names |
| `examples` | list[dict] | No | Few-shot examples to guide generation |
| `params` | dict | No | Modality-specific parameters (see below) |

**Response:**
```json
{
  "data": [
    {"question": "What is a decorator?", "answer": "A function wrapper", "difficulty": "medium", "status": "succeeded"},
    {"status": "failed", "error": "..."}
  ],
  "version_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### `POST /public/generate/stream`

Same request body as `/public/generate`. Returns `text/event-stream` (SSE) with one row per event:

```
data: {"type": "progress", "row": 0, "total": 10, "data": {...}}
data: {"type": "progress", "row": 1, "total": 10, "data": {...}}
data: {"type": "done", "total_rows": 10}
```

---

### `POST /public/generate/export`

Generate and immediately download as a file.

```json
{
  "format": "csv",
  "filename": "my_dataset",
  "task_type": "text",
  "prompt": "...",
  "columns": ["col1"],
  "num_rows": 20
}
```

Supported formats: `csv`, `jsonl`, `parquet`, `json`.

---

### `POST /public/generate/quality`

Score a dataset for completeness and optionally run an LLM coherence review.

```json
{
  "data": [{"col": "val"}, ...],
  "prompt": "optional context for LLM review",
  "run_llm_review": true,
  "deduplicate": false
}
```

---

### `GET /public/generate/versions`

List recent generation snapshots for the authenticated user.

Query params: `limit` (default 20, max 100).

---

### `GET /public/generate/versions/<version_id>`

Retrieve a full generation snapshot including result data.

---

## Task-specific `params`

| `task_type` | Key params |
|-------------|-----------|
| `language` | `language` (e.g. "Japanese"), `model`, `concurrency` |
| `video` | `fps`, `resolution`, `duration`, `annotate_frames`, `num_keyframes` |
| `audio` | `voice`, `tts_model`, `speed` |
| `image` | `image_size`, `style`, `run_detection` |
| `tabular` | `schema` (per-column type hints) |
| `code` | `code_type` (`function`\|`unittest`\|`bugfix`\|`review`\|`docstring`), `language` |
| `pii` | `pii_types`, `locale` |

---

## Python SDK

```bash
pip install anote-generate
```

```python
from anote_generate import Anote

client = Anote(api_key="your-key")  # or set ANOTE_API_KEY env var

rows = client.generate(
    task_type="text",
    columns=["question", "answer"],
    prompt="Generate Q&A pairs about Python programming",
    num_rows=10,
    examples=[{"question": "What is a list?", "answer": "An ordered collection"}],
)

# Save results
client.to_file(rows, "dataset.csv")        # CSV
client.to_file(rows, "dataset.jsonl")      # JSONL
df = client.to_dataframe(rows)             # pandas DataFrame
```

**Error handling:**
```python
from anote_generate import AnoteAuthError, AnoteValidationError

try:
    rows = client.generate(task_type="text", columns=["col"], prompt="...", num_rows=5)
except AnoteAuthError:
    print("Invalid API key")
except AnoteValidationError as e:
    print("Bad request:", e.details)
```

---

## Frontend Setup

```bash
cd frontend
npm install
npm start    # http://localhost:3000 — connects to http://localhost:5000
```

To point at a different backend:

```bash
REACT_APP_API_BASE_URL=https://api.example.com npm start
```

---

## Running Tests

```bash
make test           # pytest with short traceback
make test-cov       # pytest with HTML coverage report
```

Coverage target: 80%+ (enforced in CI).

---

## Docker

```bash
make docker-up      # start api, frontend, db, redis
make docker-down    # stop all services
make docker-logs    # tail api logs
```

For development (hot reload):

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up
```

---

## Troubleshooting

**`OPENAI_API_KEY` not set** — Copy `.env.example` to `.env` and add your key.

**CORS errors in browser** — Set `ALLOWED_ORIGINS=http://localhost:3000` in `.env` (already the default).

**`YOLO model not found`** — Image generation downloads `yolo11n.pt` on first run. Ensure write access to the working directory.

**Video generation hangs** — Set `REPLICATE_API_TOKEN` in `.env`. Video jobs can take 2–10 minutes; the async poller retries with backoff up to ~30 minutes.

**MySQL connection warnings** — Safe to ignore; the server uses file-based storage as fallback when `DB_HOST` is not set.

---

## Contributing

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make changes, add tests: `make test`
3. Push and open a PR against `main`
4. CI must pass (pytest + coverage threshold)

Branch naming: `feat/<name>`, `fix/<name>`, `chore/<name>`.

---

## License

MIT — see [server/sdk/LICENSE](server/sdk/LICENSE).
