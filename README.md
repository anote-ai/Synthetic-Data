# SyntheticDataGen — API & Project Overview

**Driving Frontier AI with Expert Data**
SyntheticDataGen is Anote’s SDK + API for programmatic dataset **generation, curation, labeling, and evaluation** across **text, images, video, audio, and agent traces**. It provides a single `generate(...)` interface, modality-specific generators, built-in quality checks, and evaluation hooks so teams can go from **prompt → validated data → benchmark-ready splits** with minimal glue code.


## Resources

- **Datasets & Services:** https://anote.ai/syntheticdata
- **Anote API docs (patterns to mirror):** https://docs.anote.ai/api-anote/predict.html

## Presentations:
Synthetic Data Launch:
https://www.youtube.com/watch?v=Qj653H5hvIw

Synthetic Data and Natural Language Processing - Ishaana Rao
https://www.youtube.com/watch?v=5SpeMMJMiyk

Synthetic Data Generation (Training Dataset Curation) - Zexun Yao
https://www.youtube.com/watch?v=nuvZHkuKWgQ

Synthetic Data Generation (API) - Saumya Singh
https://www.youtube.com/watch?v=v2OSiva-s0c
---

## Why Synthetic Datasets (Train & Eval) Matter

- **Coverage & Scale.** Real-world data is sparse on edge cases; synthetic data fills long-tail gaps and supports rapid iteration at scale.
- **Speed to Insight.** New tasks/models need prototypes **now** (hours/days), not weeks of collection and labeling.
- **Controlled Difficulty.** Dial task difficulty, domain shift, noise, and adversarial patterns to stress-test models.
- **Privacy & Compliance.** Generate PII-safe surrogates or redact/templated records to avoid handling sensitive source data.
- **Reproducibility.** Seeds + manifests make experiments repeatable and auditable for research and regulated settings.

### Training vs Evaluation
- **Training sets** teach skills (breadth & diversity).
- **Evaluation sets** independently measure progress (held-out, well-specified, stable).
SyntheticDataGen supports both, plus **stress tests** (robustness, bias, safety) and **leaderboard submissions**.

---

## Today’s Manual Curation Workflow (Typical) — and Pain Points

1. Define task, schema, and label space
2. Gather raw data (scrape, export, purchase)
3. Draft labeling guide; train annotators
4. Label in tools; export; fix schema mismatches
5. QA passes (spot-check, inter-annotator agreement)
6. Dedupe, split, document, version, and store
7. Run baselines; realize you need **more edge cases** → loop back

**Pain points:** slow/expensive, inconsistent quality, drift across versions, weak long-tail coverage, privacy constraints, and poor reproducibility.

**SyntheticDataGen** automates most steps: **programmatic generation**, **schema-aware QA**, **LLM review**, **benchmark hooks**, and **versioned artifacts**.

---

## Supported Task Types (by Modality)

**Text**
- **Classification:** e.g., Amazon review sentiment (positive/negative/neutral)
- **NER:** e.g., PII tagging with labeled entities
- **Chatbot:** e.g., Japanese conversational pairs for assistants
- **Prompting/IE:** e.g., extract structured fields from 10-K filings

**Images**
- **Object Detection:** e.g., undersea imagery with bounding boxes
- **Image Generation:** prompts → synthetic images for diffusion/GenAI

**Video**
- **Video–Prompt Pairs:** `.mp4` clips + JSON metadata for Veo/Sora-style models

**Audio**
- **TTS/ASR Data:** `.wav` + transcripts, speaker/noise profiles

**Agents**
- **Agent Traces:** sequences of tool calls, actions, observations, rewards (browser/OS/multi-agent)

---

## Where to Find Datasets

Explore curated and sample datasets on the Anote site:
**https://anote.ai/syntheticdata**

You’ll find task cards, example artifacts, and links to request bespoke datasets.

---

## Repository Layout (reference)

```
anote-generate/
├─ setup.py                      # package: anote-generate
├─ requirements.txt
├─ anotegenerate/
│  ├─ __init__.py
│  ├─ core.py                    # exposes generate(...)
│  └─ Generators/
│     ├─ text.py | image.py | video.py | audio.py | agents.py
├─ api_endpoints/handler.py      # Flask routes (POST /generate)
├─ app.py                        # Flask entrypoint
├─ db.py                         # DB connections/queries
├─ schema.sql                    # jobs, artifacts, rows, metrics
├─ examples/
│  ├─ examples_data/             # CSV/JSON + media
│  ├─ text.py | image.py | video.py | audio.py | agents.py
└─ docs/
   ├─ markdown.md                # API usage, IO fields, params
   └─ synthetic/example1.md      # worked example
```

---

## Install & Run

```bash
# clone your repo (example)
git clone repo

# install
pip install -r requirements.txt
pip install -e .

# credentials (as needed)
export SYNTHETIC_DATA_API_KEY="your_api_key"
export OPENAI_API_KEY="your_openai_key"

# optional: local YOLO server for image tasks
export YOLO_SERVER_URL="http://localhost:5001"

# run API
python app.py
```

---

## API Reference

### `POST /generate`

**Request (JSON)**
```json
{
  "task_type": "text",
  "prompt": "Amazon movie review sentiment dataset",
  "num_rows": 500,
  "columns": ["text", "label"],
  "examples": [
    {"text": "I loved the cinematography.", "label": "positive"},
    {"text": "It dragged on and on.", "label": "negative"}
  ],
  "params": {
    "label_set": ["positive", "negative", "neutral"],
    "languages": ["en"],
    "domain": "movies"
  },
  "output_format": "csv",
  "media_dir": "examples/examples_data",
  "seed": 42
}
```

**Response**
```json
{
  "job_id": "gen_01H8YX...",
  "artifact": {
    "table_path": "examples/examples_data/reviews.csv",
    "media_manifest": null
  },
  "summary": {
    "rows": 500,
    "modality": "text",
    "quality_checks": ["heuristic", "llm_review", "benchmark_compare"]
  }
}
```

**Common Fields**
- `task_type`: `"text" | "image" | "video" | "audio" | "agents"`
- `prompt`: Natural language spec for generation
- `num_rows`: Number of rows/samples to generate
- `columns`: Output schema fields (e.g., `["text","label"]`)
- `examples`: Few-shot examples to steer outputs
- `params`: Modality-specific options
- `output_format`: `"csv" | "json" | "parquet"`
- `media_dir`: Where to write `.png/.mp4/.wav` and manifests
- `seed`: Integer for reproducibility

---

## Python SDK

```python
from anotegenerate import generate

result = generate(
    task_type="text",
    prompt="Amazon movie review sentiment dataset",
    num_rows=500,
    columns=["text", "label"],
    examples=[
        {"text": "I loved the cinematography.", "label": "positive"},
        {"text": "It dragged on and on.", "label": "negative"},
    ],
    params={"label_set": ["positive", "negative", "neutral"], "languages": ["en"]},
    output_format="csv",
    media_dir="examples/examples_data",
    seed=42
)

print("Dataset at:", result.path)
```

---

## Quality Assurance & Evaluation

**Multi-layer QA**
1. **Heuristics:** schema/label checks, length, dedupe, leakage guards
2. **AI Review:** LLM spot-checks for label consistency, red flags
3. **Refinement:** regenerate failures with controlled variation
4. **Benchmark Compare:** run quick baselines to gauge dataset utility

**Artifacts**
- **Tables:** CSV/JSON/Parquet with splits + metadata
- **Media:** images/video/audio linked via manifest
- **Manifests:** map row IDs ↔ files
- **Metrics:** stored per job in `metrics` table