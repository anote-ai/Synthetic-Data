"""
Tabular synthetic data generator.
Generates typed, structured tabular data with optional relational integrity.
Supports schema hints for column types: id, int, float, email, date, enum, string, bool, uuid.
"""
import os
import json
import asyncio
import re
from typing import List, Optional
from openai import AsyncOpenAI
from tqdm.auto import tqdm
import nest_asyncio

nest_asyncio.apply()

MODEL = "gpt-4o-mini"
CONCURRENCY = 5

SUPPORTED_TYPES = {"id", "int", "float", "string", "email", "date", "datetime",
                   "enum", "bool", "uuid", "phone", "url", "name", "address"}


def _get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return AsyncOpenAI(api_key=api_key)


def _build_schema_description(schema: dict) -> str:
    if not schema:
        return ""
    lines = ["Column type constraints:"]
    for col, spec in schema.items():
        if isinstance(spec, dict):
            type_name = spec.get("type", "string")
            constraints = {k: v for k, v in spec.items() if k != "type"}
            constraint_str = ", ".join(f"{k}={v}" for k, v in constraints.items())
            lines.append(f"  - {col}: type={type_name}" + (f" ({constraint_str})" if constraint_str else ""))
        else:
            lines.append(f"  - {col}: type={spec}")
    return "\n".join(lines)


def _build_system_prompt(prompt: str, columns: List[str], schema: dict, examples: List[dict]) -> str:
    column_desc = ", ".join(f'"{c}"' for c in columns)
    system = (
        f"You are a synthetic tabular data generator. Generate realistic, diverse, type-correct data.\n"
        f"Dataset context: {prompt}\n"
        f"Each row must be a JSON object with exactly these keys: {column_desc}.\n"
        f"Return ONLY a JSON array of objects — no markdown, no explanation.\n"
    )
    if schema:
        system += "\n" + _build_schema_description(schema) + "\n"
        system += "\nIMPORTANT: Strictly follow the type constraints above.\n"
    if examples:
        system += f"\nFew-shot examples:\n{json.dumps(examples[:3], ensure_ascii=False)}\n"
    return system


async def _generate_batch(
    client: AsyncOpenAI,
    system_prompt: str,
    columns: List[str],
    schema: dict,
    batch_size: int,
    semaphore: asyncio.Semaphore,
) -> List[dict]:
    async with semaphore:
        for attempt in range(3):
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Generate exactly {batch_size} diverse rows as a JSON array."},
                    ],
                    temperature=0.7,
                )
                raw = response.choices[0].message.content.strip()
                # Extract JSON array
                cleaned = re.sub(r"```(?:json)?", "", raw).strip()
                match = re.search(r"\[.*\]", cleaned, re.DOTALL)
                rows = json.loads(match.group() if match else cleaned)

                normalized = []
                for row in rows[:batch_size]:
                    normalized.append({col: row.get(col, "") for col in columns} | {"status": "succeeded"})
                return normalized
            except Exception as e:
                if attempt == 2:
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
    system_prompt = _build_system_prompt(prompt, columns, schema, examples)

    batches = []
    remaining = num_rows
    while remaining > 0:
        b = min(batch_size, remaining)
        batches.append(b)
        remaining -= b

    results = []
    with tqdm(total=num_rows, desc="Generating tabular rows") as pbar:
        tasks = [_generate_batch(client, system_prompt, columns, schema, b, semaphore) for b in batches]
        for coro in asyncio.as_completed(tasks):
            batch_result = await coro
            results.extend(batch_result)
            pbar.update(len(batch_result))

    return results[:num_rows]


def generate_tabular_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic tabular data with optional type constraints.

    Args:
        prompt: Dataset context description
        columns: Column names for the output rows
        num_rows: Number of rows to generate
        examples: Optional few-shot example rows
        params: Optional dict with keys:
            - schema: dict mapping column names to type specs
              e.g. {"age": {"type": "int", "min": 18, "max": 90},
                    "email": {"type": "email"},
                    "plan": {"type": "enum", "values": ["free", "pro"]}}
            - batch_size: rows per LLM call (default: 10, max: 20)
            - concurrency: parallel API calls (default: 5, max: 10)

    Returns:
        List of dicts with requested columns + status

    Example::

        rows = generate_tabular_data(
            prompt="User accounts for a SaaS product",
            columns=["user_id", "name", "email", "plan", "age"],
            num_rows=20,
            params={
                "schema": {
                    "user_id": {"type": "uuid"},
                    "age": {"type": "int", "min": 18, "max": 75},
                    "plan": {"type": "enum", "values": ["free", "pro", "enterprise"]},
                    "email": {"type": "email"},
                }
            }
        )
    """
    examples = examples or []
    params = params or {}
    return asyncio.get_event_loop().run_until_complete(
        _generate_all(prompt, columns, num_rows, examples, params)
    )
