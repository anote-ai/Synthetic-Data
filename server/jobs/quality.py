"""
Data quality scoring for synthetic datasets.
Checks: deduplication, completeness, coherence (LLM review).
"""
import os
import json
import hashlib
from typing import List, Dict
from openai import OpenAI


def deduplicate(data: List[Dict]) -> tuple:
    """Remove exact duplicate rows. Returns (deduped_data, num_removed)."""
    seen = set()
    result = []
    for row in data:
        key = hashlib.md5(json.dumps(row, sort_keys=True).encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result, len(data) - len(result)


def score_completeness(data: List[Dict]) -> Dict:
    """Check what % of cells are non-null/non-empty per column."""
    if not data:
        return {}
    columns = list(data[0].keys())
    scores = {}
    for col in columns:
        non_empty = sum(1 for row in data if row.get(col) not in (None, "", [], {}))
        scores[col] = round(non_empty / len(data), 3)
    return scores


def llm_coherence_review(data: List[Dict], prompt: str, sample_size: int = 5) -> Dict:
    """Use GPT-4o-mini to review a sample of rows for coherence/quality."""
    sample = data[:sample_size]
    sample_json = json.dumps(sample, indent=2)

    system_message = (
        "You are a data quality expert. You will be given a sample of synthetic dataset rows "
        "and the prompt that was used to generate them. Evaluate the overall quality and coherence "
        "of the data. Respond ONLY with a valid JSON object containing exactly these keys: "
        '"score" (integer 1-10), "issues" (list of strings describing problems found), '
        'and "suggestions" (list of strings with improvement suggestions).'
    )

    user_message = (
        f"Original prompt used to generate this dataset:
{prompt}

"
        f"Sample rows (up to {sample_size}):
{sample_json}

"
        'Please evaluate the quality and coherence of this data. '
        'Respond with a JSON object: {"score": <1-10>, "issues": [...], "suggestions": [...]}'
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if content.startswith("'""""):
        lines = content.splitlines()
        content = "
".join(lines[1:-1] if lines[-1].strip() == "'"""" else lines[1:])

    parsed = json.loads(content)

    return {
        "score": int(parsed.get("score", 0)),
        "issues": list(parsed.get("issues", [])),
        "suggestions": list(parsed.get("suggestions", [])),
    }


def score_dataset(data: List[Dict], prompt: str, run_llm_review: bool = True) -> Dict:
    """Run all quality checks and return a quality report."""
    deduped, dupes_removed = deduplicate(data)
    completeness = score_completeness(deduped)
    report = {
        "total_rows": len(data),
        "unique_rows": len(deduped),
        "duplicates_removed": dupes_removed,
        "completeness": completeness,
        "avg_completeness": round(sum(completeness.values()) / len(completeness), 3) if completeness else 1.0,
    }
    if run_llm_review and os.getenv("OPENAI_API_KEY"):
        report["llm_review"] = llm_coherence_review(deduped, prompt)
    return report
