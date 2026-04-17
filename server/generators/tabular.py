"""
Tabular synthetic data generator.
Generates typed, structured tabular data using GPT-4o-mini with optional schema hints.
"""
import os
import json
import asyncio
import re
from typing import List, Optional
import openai
import nest_asyncio

nest_asyncio.apply()

MODEL = "gpt-4o-mini"
CONCURRENCY = 5
MAX_RETRIES = 3

SUPPORTED_TYPES = {
    "id", "int", "float", "string", "email", "date", "datetime",
    "enum", "bool", "uuid", "phone", "url", "name", "address",
}


def _get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return openai.AsyncOpenAI(api_key=api_key)


def _build_system_prompt(columns: List[str], prompt: str, schema: dict, examples: List[dict]) -> str:
    column_desc = ", ".join(f'"{c}"' for c in columns)
    schema_hints = ""
    if schema:
        hints = []
        for col, hint in schema.items():
            col_type = hint.get("type", "string")
            extras = {k: v for k, v in hint.items() if k != "type"}
            hints.append(f'  "{col}": type={col_type}' + (f", {extras}" if extras else ""))
        schema_hints = "\nColumn type hints:\n" + "\n".join(hints)

    system = (
        f"You are a synthetic tabular data generator. Generate realistic, diverse, typed data rows.\n"
        f"Context: {prompt}\n"
        f"Each row must be a JSON object with exactly these keys: {column_desc}.{schema_hints}\n"
        f"Respect the column types strictly. Return ONLY a JSON array — no markdown, no explanation.\n"
    )
    if examples:
        system += f"\nReference examples:\n{json.dumps(examples[:3], ensure_ascii=False)}\n"
    return system


def _extract_json(raw: str) -> list:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(cleaned)


async def _generate_batch(
    client,
    system_prompt: str,
    columns: List[str],
    batch_size: int,
    semaphore: asyncio.Semaphore,
) -> List[dict]:
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Generate exactly {batch_size} diverse rows. Return a JSON array."},
                    ],
                    temperature=0.8,
                )
                raw = response.choices[0].message.content.strip()
                rows = _extract_json(raw)
                return [
                    {col: row.get(col, "") for col in columns} | {"status": "succeeded"}
                    for row in rows[:batch_size]
                ]
            except json.JSONDecodeError as e:
                if attempt == MAX_RETRIES - 1:
                    return [{"status": "failed", "error": f"JSON parse error: {e}"} for _ in range(batch_size)]
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
    params: dict,
) -> List[dict]:
    schema = params.get("schema", {})
    batch_size = min(params.get("batch_size", 10), 20)
    concurrency = min(params.get("concurrency", CONCURRENCY), 10)

    client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)
    system_prompt = _build_system_prompt(columns, prompt, schema, examples)

    batches = []
    remaining = num_rows
    while remaining > 0:
        b = min(batch_size, remaining)
        batches.append(b)
        remaining -= b

    tasks = [_generate_batch(client, system_prompt, columns, b, semaphore) for b in batches]
    results = []
    for coro in asyncio.as_completed(tasks):
        results.extend(await coro)

    return results[:num_rows]


def generate_tabular_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic tabular data with optional column type hints.

    params keys:
        schema: dict mapping column name → {"type": ..., "min": ..., "max": ..., "values": [...]}
        batch_size: rows per LLM call (default 10, max 20)
        concurrency: parallel calls (default 5, max 10)
    """
    examples = examples or []
    params = params or {}
    return asyncio.get_event_loop().run_until_complete(
        _generate_all(prompt, columns, num_rows, examples, params)
    )
