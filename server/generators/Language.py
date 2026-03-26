import os
import json
import asyncio
import logging
from typing import List, Optional

import nest_asyncio
from openai import AsyncOpenAI

nest_asyncio.apply()

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
DEFAULT_CONCURRENCY = 3
MAX_RETRIES = 3


def _get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please export OPENAI_API_KEY before running."
        )
    return AsyncOpenAI(api_key=api_key)


def _safe_json_parse(raw: str) -> list:
    raw = raw.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    return json.loads(raw)


def _build_system_prompt(target_language: str) -> str:
    return (
        f"You are a multilingual dataset generator. "
        f"Generate all text content in {target_language} unless the column name "
        f"explicitly requests another language. "
        f"Always respond with a valid JSON array only - no markdown, no explanation."
    )


def _build_user_prompt(
    prompt: str,
    columns: List[str],
    num_rows: int,
    target_language: str,
    examples: Optional[List[dict]] = None,
) -> str:
    col_list = ", ".join(columns)
    lines = [
        f"Generate exactly {num_rows} rows of data for the following task:",
        f"Task description: {prompt}",
        f"Target language: {target_language}",
        f"Each row must be a JSON object with these keys: {col_list}",
        "Output only a JSON array of objects with no additional text.",
    ]
    if examples:
        lines.append(
            f"Here are some example rows for reference: {json.dumps(examples, ensure_ascii=False)}"
        )
    return "\n".join(lines)


async def _generate_batch_async(
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    semaphore: asyncio.Semaphore,
) -> list:
    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=2048,
                )
                raw = response.choices[0].message.content
                return _safe_json_parse(raw)
            except Exception as exc:
                if attempt == MAX_RETRIES:
                    logger.error("All %d attempts failed: %s", MAX_RETRIES, exc)
                    raise
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %ds...",
                    attempt,
                    MAX_RETRIES,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)


async def _generate_language_data_async(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> List[dict]:
    if params is None:
        params = {}
    target_language = params.get("target_language", "Spanish")

    client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)

    system_prompt = _build_system_prompt(target_language)
    user_prompt = _build_user_prompt(prompt, columns, num_rows, target_language, examples)

    rows = await _generate_batch_async(client, system_prompt, user_prompt, semaphore)

    result: List[dict] = []
    for row in rows[:num_rows]:
        sanitized = {col: row.get(col, "") for col in columns}
        result.append(sanitized)

    while len(result) < num_rows:
        result.append({col: "" for col in columns})

    return result


def generate_language_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """Generate multilingual synthetic data rows.

    Args:
        prompt:    Natural-language description of the data to generate.
        columns:   List of column names each row must contain.
        num_rows:  Number of rows to generate (default 5).
        examples:  Optional list of example rows to guide generation.
        params:    Optional dict of extra parameters.
                   Supported keys:
                     - target_language (str): language for output text (default Spanish).
                     - concurrency (int): max parallel API calls (default 3).

    Returns:
        List of dicts, each containing all requested columns.
    """
    if params is None:
        params = {}
    concurrency = int(params.get("concurrency", DEFAULT_CONCURRENCY))

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        _generate_language_data_async(
            prompt=prompt,
            columns=columns,
            num_rows=num_rows,
            examples=examples,
            params=params,
            concurrency=concurrency,
        )
    )
