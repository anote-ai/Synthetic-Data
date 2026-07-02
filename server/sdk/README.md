# anote-generate

Python SDK for the [Anote Synthetic Data API](https://anote.ai) — generate text, image, audio, video, agent trace, PII, language, tabular, and code datasets using LLMs.

## Installation

```bash
pip install anote-generate
```

## Quick Start

```python
from anote_generate import Anote

client = Anote(api_key="your-api-key")

# Generate text data
rows = client.generate(
    task_type="text",
    columns=["question", "answer", "difficulty"],
    prompt="Generate Q&A pairs about Python programming",
    num_rows=10,
    examples=[{"question": "What is a list?", "answer": "An ordered collection", "difficulty": "easy"}],
)

for row in rows:
    print(row)

# Save to CSV
client.to_file(rows, "dataset.csv")

# Convert to DataFrame
df = client.to_dataframe(rows)
```

## Supported Task Types

| task_type | Description |
|-----------|-------------|
| `text` | Structured text with any columns |
| `image` | DALL-E 3 images with YOLO detection |
| `audio` | TTS audio with Whisper transcription |
| `video` | Video clips with optional frame annotations |
| `agent` | Multi-turn agent traces with tool calls |
| `pii` | Synthetic PII records (14 types) |
| `tabular` | Typed tabular data with relational integrity |
| `language` | Translation and language-focused datasets |
| `code` | Code functions, tests, and docstrings |

## Parameters

```python
client.generate(
    task_type="audio",
    columns=["transcript", "sentiment"],
    prompt="Customer support calls for a SaaS product",
    num_rows=20,
    params={
        "voice": "nova",          # alloy | echo | fable | onyx | nova | shimmer
        "tts_model": "tts-1-hd",  # tts-1 | tts-1-hd
        "speed": 1.0,
    },
)
```

## Error Handling

```python
from anote_generate import Anote, AnoteAuthError, AnoteValidationError

try:
    rows = client.generate(task_type="text", columns=["col"], prompt="...", num_rows=5)
except AnoteAuthError:
    print("Invalid API key")
except AnoteValidationError as e:
    print("Bad request:", e.details)
```

## License

MIT
