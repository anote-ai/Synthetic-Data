# Anote Synthetic Data

[![CI](https://github.com/anote-ai/Synthetic-Data/actions/workflows/ci.yml/badge.svg)](https://github.com/anote-ai/Synthetic-Data/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/anote-generate)](https://pypi.org/project/anote-generate/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A multi-modal synthetic dataset generation platform. Generate text, image, audio, video, agent traces, and PII datasets through a unified REST API and Python SDK.

---

## Quick Start

### Option 1 — Docker (recommended)

```bash
git clone https://github.com/anote-ai/Synthetic-Data.git
cd Synthetic-Data

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and REPLICATE_API_TOKEN

# Start all services
make docker-up

# API is running at http://localhost:5000
# Frontend is running at http://localhost:3000
```

### Option 2 — Local

```bash
git clone https://github.com/anote-ai/Synthetic-Data.git
cd Synthetic-Data

cp .env.example .env
# Edit .env with your API keys

make install
make dev           # Flask API on :5000
make frontend      # React UI on :3000 (separate terminal)
```

---

## Python SDK

```bash
pip install anote-generate
```

```python
from anote_generate import Anote

client = Anote(api_key="your-key")

# Generate text data
rows = client.generate(
    task_type="text",
    columns=["question", "answer", "difficulty"],
    prompt="Generate Q&A pairs about Python programming",
    num_rows=10,
    examples=[{"question": "What is a list?", "answer": "An ordered collection", "difficulty": "easy"}],
)

# Save to file
client.to_file(rows, "dataset.csv")      # CSV
client.to_file(rows, "dataset.jsonl")    # JSONL (fine-tuning format)

# Convert to DataFrame
df = client.to_dataframe(rows)
```

---

## Supported Modalities

| `task_type` | Description | External API |
|-------------|-------------|--------------|
| `text` | Structured text with any columns | OpenAI GPT-4o-mini |
| `image` | DALL-E 3 images with YOLO object detection | OpenAI DALL-E 3 |
| `audio` | TTS audio with Whisper transcription | OpenAI TTS + Whisper |
| `video` | Video clips with optional GPT-4o frame annotations | Replicate API |
| `agent` | Multi-turn agent traces with tool calls | OpenAI GPT-4o-mini |
| `pii` | Synthetic PII records (14 types) | OpenAI GPT-4o-mini |
| `tabular` | Typed tabular data with relational integrity | OpenAI GPT-4o-mini |
| `code` | Code functions, tests, docstrings, bug fixes | OpenAI GPT-4o-mini |

---

## API Reference

### POST /public/generate

**Request:**
```json
{
  "task_type": "text",
  "prompt": "Generate product reviews for a coffee maker",
  "num_rows": 5,
  "columns": ["review_text", "sentiment", "rating"],
  "examples": [{"review_text": "Great!", "sentiment": "positive", "rating": "5"}],
  "params": {}
}
```

**Response:**
```json
{
  "data": [
    {"review_text": "Best coffee ever!", "sentiment": "positive", "rating": "5", "status": "succeeded"},
    {"review_text": "Not worth it.", "sentiment": "negative", "rating": "2", "status": "succeeded"}
  ]
}
```

**Auth:** `Authorization: Bearer <token>`

### POST /public/generate/export

Same as `/public/generate` plus:
- `"format"`: `"csv"` | `"jsonl"` | `"parquet"` | `"json"` (default: `"json"`)
- `"filename"`: output filename without extension

Returns a file download.

### GET /health

```json
{"status": "ok", "version": "1.0.0"}
```

---

## Modality Parameters

### Text
```json
{"params": {"model": "gpt-4o-mini", "batch_size": 10}}
```

### Image
```json
{"params": {"image_size": "1024x1024", "style": "vivid", "run_detection": true, "detection_confidence": 0.25}}
```

### Audio
```json
{"params": {"voice": "nova", "tts_model": "tts-1", "speed": 1.0, "language": "en"}}
```

### Video
```json
{"params": {"fps": 6, "width": 576, "height": 320, "annotate_frames": false, "num_keyframes": 5}}
```

### Agent
```json
{
  "params": {
    "scenario": "Customer support for SaaS billing",
    "difficulty": "medium",
    "tools": [
      {"name": "lookup_account", "description": "Look up account by email", "parameters": {"email": "string"}}
    ],
    "outcome_distribution": {"success": 0.7, "failure": 0.2, "partial": 0.1}
  }
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for text, image, audio, PII generation |
| `REPLICATE_API_TOKEN` | Yes (video only) | — | Replicate API token for video generation |
| `SECRET_KEY` | Yes (production) | `dev-secret` | Flask JWT secret key |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | CORS allowed origins (comma-separated) |
| `SYNTHETIC_OUTPUT_DIR` | No | `./outputs` | Directory for generated files |
| `MAX_ROWS_PER_REQUEST` | No | `100` | Max rows per API request |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `PORT` | No | `5000` | Flask server port |
| `DB_HOST` | No | — | MySQL host (omit to disable DB logging) |
| `DB_PORT` | No | `3306` | MySQL port |
| `DB_USER` | No | — | MySQL user |
| `DB_PASSWORD` | No | — | MySQL password |
| `DB_NAME` | No | — | MySQL database name |

---

## Repository Structure

```
Synthetic-Data/
├── server/
│   ├── app.py                    # Flask entrypoint
│   ├── auth_utils.py             # JWT authentication
│   ├── validators.py             # Pydantic request validation
│   ├── logging_config.py         # Structured JSON logging
│   ├── requirements.txt
│   ├── api_endpoints/
│   │   └── handler.py            # Routes task_type → generator
│   ├── database/
│   │   ├── db.py                 # MySQL connection pool + helpers
│   │   └── schema.sql            # Table definitions
│   ├── generators/               # One file per modality
│   │   ├── text.py               # GPT-4o-mini async generation
│   │   ├── image.py              # DALL-E 3 + YOLO11
│   │   ├── audio.py              # TTS + Whisper pipeline
│   │   ├── video.py              # Replicate async polling
│   │   ├── agent.py              # Multi-turn tool-use traces
│   │   ├── PII.py                # 14 PII types via Faker + LLM
│   │   └── Language.py           # Wikipedia Q&A
│   ├── utils/
│   │   └── export.py             # CSV/JSONL/Parquet export
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_generate.py
│   │   └── test_examples.py
│   └── sdk/                      # PyPI package: anote-generate
│       ├── pyproject.toml
│       ├── README.md
│       └── anote_generate/
│           ├── __init__.py
│           └── core.py
├── frontend/
│   ├── package.json
│   └── src/
│       └── App.js                # React UI
├── docker-compose.yml
├── server/Dockerfile
├── frontend/Dockerfile
├── Makefile
├── .env.example
└── README.md
```

---

## Development

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Lint
make lint

# Docker commands
make docker-up        # Start all services
make docker-logs      # Follow API logs
make docker-down      # Stop all services
```

---

## Troubleshooting

**`ImportError: No module named 'auth_utils'`**
→ Make sure you're running from the `server/` directory: `cd server && python app.py`

**CORS error in browser**
→ Set `ALLOWED_ORIGINS=http://localhost:3000` in `.env`

**`RuntimeError: OPENAI_API_KEY environment variable is not set`**
→ Add your key to `.env`: `OPENAI_API_KEY=sk-...`

**YOLO model not found**
→ Download the model: `cd server && python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"`

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Run `make test` — all tests must pass
5. Submit a PR targeting `main`

---

## License

MIT — see [LICENSE](LICENSE)
