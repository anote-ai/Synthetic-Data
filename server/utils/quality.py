"""Data quality utilities: deduplication, completeness scoring, LLM coherence review."""
import hashlib
import json
import os
import random
from typing import List, Optional


def deduplicate(data: List[dict]) -> List[dict]:
    """Remove exact duplicate rows based on MD5 hash of JSON-serialized content."""
    seen = set()
    result = []
    for row in data:
        key = hashlib.md5(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def score_completeness(data: List[dict]) -> dict:
    """Return per-column completeness (fraction of non-null/non-empty values)."""
    if not data:
        return {}
    columns = list(data[0].keys())
    scores = {}
    for col in columns:
        filled = sum(
            1 for row in data
            if row.get(col) is not None and row.get(col) != "" and row.get(col) != "failed"
        )
        scores[col] = round(filled / len(data), 4)
    return scores


def llm_coherence_review(data: List[dict], prompt: str) -> dict:
    """
    Use GPT-4o-mini to review up to 5 sampled rows for realism and coherence.
    Returns {"score": 1-10, "issues": [...], "suggestions": [...]}.
    """
    import openai

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    sample = random.sample(data, min(5, len(data)))
    sample_str = json.dumps(sample, indent=2, ensure_ascii=False)

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a data quality evaluator. Review synthetic dataset rows for realism, "
                    "coherence, and diversity. Return a JSON object with keys: "
                    '"score" (integer 1-10), "issues" (list of strings), "suggestions" (list of strings).'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Dataset context: {prompt}\n\nSample rows:\n{sample_str}\n\n"
                    "Evaluate quality. Return ONLY valid JSON."
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"score": 0, "issues": ["Could not parse LLM response"], "suggestions": []}


def score_dataset(data: List[dict], prompt: str = "", run_llm_review: bool = False) -> dict:
    """Run all quality checks and return a consolidated report."""
    unique = deduplicate(data)
    completeness = score_completeness(data)
    avg_completeness = round(sum(completeness.values()) / len(completeness), 4) if completeness else 0.0

    report = {
        "total_rows": len(data),
        "unique_rows": len(unique),
        "duplicates_removed": len(data) - len(unique),
        "completeness": completeness,
        "avg_completeness": avg_completeness,
    }

    if run_llm_review and data:
        try:
            report["llm_review"] = llm_coherence_review(data, prompt)
        except Exception as e:
            report["llm_review"] = {"error": str(e)}

    return report
