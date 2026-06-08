"""
Text synthetic data generator.
Uses OpenAI GPT-4o-mini to generate structured tabular text data.
"""
import os
import json
import asyncio
import re
from typing import List, Optional
import openai
from tqdm.auto import tqdm
import nest_asyncio

nest_asyncio.apply()

MODEL = "gpt-4o-mini"
CONCURRENCY = 5
MAX_RETRIES = 3


def _get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return openai.AsyncOpenAI(api_key=api_key)


def _build_system_prompt(columns: List[str], prompt: str, examples: List[dict]) -> str:
    column_desc = ", ".join(f'"{c}"' for c in columns)
    system = (
        f"You are a synthetic data generator. Generate realistic, diverse, high-quality data rows.\n"
        f"Task context: {prompt}\n"
        f"Each row must be a JSON object with exactly these keys: {column_desc}.\n"
        f"Return ONLY a JSON array of objects — no markdown, no explanation, no code fences.\n"
    )
    if examples:
        example_str = json.dumps(examples[:3], ensure_ascii=False)
        system += f"\nHere are example rows for reference:\n{example_str}\n"
        system += "Generate new rows with similar style but different content.\n"
    return system


def _build_user_prompt(columns: List[str], batch_size: int) -> str:
    return f"Generate exactly {batch_size} diverse and realistic rows. Return a JSON array with {batch_size} objects."


def _extract_json(raw: str) -> list:
    """Extract JSON array from LLM response, handling markdown code blocks."""
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    # Find JSON array
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(cleaned)


async def _generate_batch(
    client,
    system_prompt: str,
    user_prompt: str,
    columns: List[str],
    batch_size: int,
    semaphore: asyncio.Semaphore,
    model: str = MODEL,
) -> List[dict]:
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.9,
                )
                raw = response.choices[0].message.content.strip()
                rows = _extract_json(raw)
                # Normalize: ensure all columns present
                normalized = []
                for row in rows[:batch_size]:
                    normalized.append({
                        col: row.get(col, "") for col in columns
                    } | {"status": "succeeded"})
                return normalized
            except json.JSONDecodeError as e:
                if attempt == MAX_RETRIES - 1:
                    return [{"status": "failed", "error": f"JSON parse error after {MAX_RETRIES} attempts: {e}"} for _ in range(batch_size)]
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return [{"status": "failed", "error": str(e)} for _ in range(batch_size)]
                await asyncio.sleep(2 ** attempt)
    return [{"status": "failed", "error": "Unknown error"} for _ in range(batch_size)]


async def _generate_all(
    prompt: str,
    columns: List[str],
    num_rows: int,
    examples: List[dict],
    params: Optional[dict] = None,
    on_row=None,
) -> List[dict]:
    params = params or {}
    batch_size = min(params.get("batch_size", 10), 20)
    concurrency = min(params.get("concurrency", CONCURRENCY), 10)
    model_override = params.get("model", MODEL)

    client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)

    system_prompt = _build_system_prompt(columns, prompt, examples)

    # Split into batches
    batches = []
    remaining = num_rows
    while remaining > 0:
        b = min(batch_size, remaining)
        batches.append(b)
        remaining -= b

    tasks = []
    for b in batches:
        user_prompt = _build_user_prompt(columns, b)
        tasks.append(_generate_batch(client, system_prompt, user_prompt, columns, b, semaphore, model_override))

    results = []
    with tqdm(total=num_rows, desc="Generating text rows") as pbar:
        for coro in asyncio.as_completed(tasks):
            batch_result = await coro
            results.extend(batch_result)
            pbar.update(len(batch_result))
            if on_row:
                for row in batch_result:
                    on_row(row)

    return results[:num_rows]


def generate_text_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
    on_row=None,
) -> List[dict]:
    examples = examples or []
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(
        _generate_all(prompt, columns, num_rows, examples, params, on_row)
    )
