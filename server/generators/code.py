"""
Code synthetic data generator.
Generates synthetic code datasets for ML training using GPT-4o-mini.
Supports functions, unit tests, bug-fix pairs, review comments, and docstrings.
"""
import ast
import os
import json
import asyncio
import re
from typing import List, Optional
import openai
import nest_asyncio

nest_asyncio.apply()

MODEL = "gpt-4o-mini"
CONCURRENCY = 3
MAX_RETRIES = 3

VALID_CODE_TYPES = {"function", "unittest", "bugfix", "review", "docstring"}
VALID_LANGUAGES = {"python", "javascript", "typescript", "go", "rust", "java", "cpp", "sql"}


def _get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return openai.AsyncOpenAI(api_key=api_key)


def _build_system_prompt(code_type: str, language: str, columns: List[str], prompt: str) -> str:
    col_desc = ", ".join(f'"{c}"' for c in columns)
    type_instructions = {
        "function": (
            "Generate a function with: signature, full implementation, and a brief docstring. "
            'Return a JSON object with keys: "function_signature", "implementation", "docstring", plus any other requested columns.'
        ),
        "unittest": (
            "Generate a function implementation and its corresponding unit tests. "
            'Return a JSON object with keys: "function_code", "test_code", "test_description", plus any other requested columns.'
        ),
        "bugfix": (
            "Generate a snippet of buggy code and its corrected version with an explanation. "
            'Return a JSON object with keys: "buggy_code", "fixed_code", "bug_description", "fix_explanation", plus any other requested columns.'
        ),
        "review": (
            "Generate a code snippet and realistic code review comments pointing out improvements. "
            'Return a JSON object with keys: "code_snippet", "review_comments", "severity", plus any other requested columns.'
        ),
        "docstring": (
            "Generate an undocumented function and a high-quality docstring for it. "
            'Return a JSON object with keys: "undocumented_code", "docstring", plus any other requested columns.'
        ),
    }
    return (
        f"You are a synthetic code dataset generator. Generate realistic {language} code examples.\n"
        f"Task context: {prompt}\n"
        f"Code type: {code_type}. {type_instructions.get(code_type, '')}\n"
        f"The output must include these fields: {col_desc}.\n"
        f"Return ONLY valid JSON — no markdown fences, no explanation.\n"
    )


def _validate_python(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _extract_code_from_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


async def _generate_single(
    client,
    system_prompt: str,
    columns: List[str],
    code_type: str,
    language: str,
    validate_syntax: bool,
    semaphore: asyncio.Semaphore,
    index: int,
) -> dict:
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Generate a unique {code_type} example (item {index + 1})."},
                    ],
                    temperature=0.85,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content.strip()
                parsed = _extract_code_from_json(raw)

                # Python syntax validation
                if validate_syntax and language == "python":
                    for key in ("implementation", "function_code", "buggy_code", "fixed_code",
                                "undocumented_code", "code_snippet"):
                        if key in parsed and not _validate_python(parsed[key]):
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return {"status": "failed", "error": f"Generated {key} has invalid Python syntax"}

                row = {col: parsed.get(col, "") for col in columns}
                row["status"] = "succeeded"
                row["language"] = language
                row["code_type"] = code_type
                return row

            except json.JSONDecodeError as e:
                if attempt == MAX_RETRIES - 1:
                    return {"status": "failed", "error": f"JSON parse error: {e}"}
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return {"status": "failed", "error": str(e)}
                await asyncio.sleep(2 ** attempt)
    return {"status": "failed", "error": "Max retries exceeded"}


async def _generate_all(
    prompt: str,
    columns: List[str],
    num_rows: int,
    examples: List[dict],
    params: dict,
) -> List[dict]:
    code_type = params.get("code_type", "function")
    language = params.get("language", "python")
    validate_syntax = params.get("validate_syntax", True)
    concurrency = min(int(params.get("concurrency", CONCURRENCY)), 8)

    if code_type not in VALID_CODE_TYPES:
        return [
            {"status": "failed", "error": f"Invalid code_type '{code_type}'. Must be one of: {VALID_CODE_TYPES}"}
        ] * num_rows

    if language not in VALID_LANGUAGES:
        return [
            {"status": "failed", "error": f"Invalid language '{language}'. Must be one of: {VALID_LANGUAGES}"}
        ] * num_rows

    client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)
    system_prompt = _build_system_prompt(code_type, language, columns, prompt)

    tasks = [
        _generate_single(client, system_prompt, columns, code_type, language, validate_syntax, semaphore, i)
        for i in range(num_rows)
    ]

    results = []
    for coro in asyncio.as_completed(tasks):
        results.append(await coro)

    return results[:num_rows]


def generate_code_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic code datasets.

    params keys:
        code_type: "function" | "unittest" | "bugfix" | "review" | "docstring" (default: "function")
        language: "python" | "javascript" | "typescript" | "go" | "rust" | "java" | "cpp" | "sql"
        validate_syntax: bool — validate Python syntax (default: True)
        concurrency: parallel API calls (default: 3, max: 8)
    """
    examples = examples or []
    params = params or {}
    return asyncio.get_event_loop().run_until_complete(
        _generate_all(prompt, columns, num_rows, examples, params)
    )
