"""Text synthetic data generator backed by OpenAI JSON-mode responses."""
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
        "You are a synthetic data generator. Generate realistic, diverse, high-quality data rows.\n"
        f"Task context: {prompt}\n"
        f"Each response must be one JSON object with exactly these keys: {column_desc}.\n"
        "Return ONLY the JSON object. Do not include markdown, comments, arrays, or extra keys.\n"
    )
    if examples:
        example_str = json.dumps(examples[:3], ensure_ascii=False)
        system += f"\nHere are example rows for reference:\n{example_str}\n"
        system += "Generate new rows with similar style but different content.\n"
    return system


def _build_user_prompt(columns: List[str], recent_rows: Optional[List[dict]] = None) -> str:
    prompt = (
        "Generate 1 new synthetic row. "
        f"The JSON object must include these keys: {', '.join(columns)}."
    )
    if recent_rows:
        prompt += (
            "\nAvoid duplicating these recently generated rows:\n"
            f"{json.dumps(recent_rows[-5:], ensure_ascii=False)}"
        )
    return prompt


def _extract_json_object(raw: str) -> dict:
    """Extract one JSON object from an LLM response, handling markdown code blocks."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return parsed


def _normalize_row(row: dict, columns: List[str]) -> dict:
    return {col: row.get(col, "") for col in columns} | {"status": "succeeded"}


async def _generate_row(
    client,
    system_prompt: str,
    columns: List[str],
    semaphore: asyncio.Semaphore,
    recent_rows: List[dict],
    model: str = MODEL,
) -> dict:
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": _build_user_prompt(columns, recent_rows)},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.9,
                )
                raw = response.choices[0].message.content.strip()
                row = _extract_json_object(raw)
                return _normalize_row(row, columns)
            except (json.JSONDecodeError, ValueError) as e:
                if attempt == MAX_RETRIES - 1:
                    return {"status": "failed", "error": f"JSON parse error after {MAX_RETRIES} attempts: {e}"}
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return {"status": "failed", "error": str(e)}
                await asyncio.sleep(2 ** attempt)
    return {"status": "failed", "error": "Unknown error"}


async def _generate_all(
    prompt: str,
    columns: List[str],
    num_rows: int,
    examples: List[dict],
    params: Optional[dict] = None,
    on_row=None,
) -> List[dict]:
    params = params or {}
    concurrency = min(params.get("concurrency", CONCURRENCY), 10)
    model_override = params.get("model", MODEL)

    client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)

    system_prompt = _build_system_prompt(columns, prompt, examples)

    results = []
    pending = set()
    with tqdm(total=num_rows, desc="Generating text rows") as pbar:
        while len(results) + len(pending) < num_rows and len(pending) < concurrency:
            pending.add(asyncio.create_task(_generate_row(client, system_prompt, columns, semaphore, results[-20:], model_override)))

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                row = task.result()
                results.append(row)
                pbar.update(1)
                if on_row:
                    on_row(row)

            while len(results) + len(pending) < num_rows and len(pending) < concurrency:
                pending.add(asyncio.create_task(_generate_row(client, system_prompt, columns, semaphore, results[-20:], model_override)))

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
