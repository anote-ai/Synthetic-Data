"""
Code synthetic data generator.
Generates synthetic code datasets: functions, unit tests, bug fixes,
code reviews, and docstrings.
Validates Python output with ast.parse() for syntax correctness.
"""
import os
import json
import asyncio
import ast
import re
from typing import List, Optional
from openai import AsyncOpenAI
from tqdm.auto import tqdm
import nest_asyncio

nest_asyncio.apply()

MODEL = "gpt-4o-mini"
CONCURRENCY = 3

VALID_CODE_TYPES = {"function", "unittest", "bugfix", "review", "docstring"}
VALID_LANGUAGES = {"python", "javascript", "typescript", "go", "rust", "java", "cpp", "sql"}

CODE_TYPE_PROMPTS = {
    "function": (
        "Generate a complete, working {language} function.\n"
        "Return JSON with: function_signature, implementation, docstring, complexity (easy/medium/hard), topic."
    ),
    "unittest": (
        "Generate a {language} function AND its comprehensive unit tests.\n"
        "Return JSON with: function_signature, implementation, unit_tests, test_count (int), topic."
    ),
    "bugfix": (
        "Generate a {language} function with a subtle bug, then provide the fixed version.\n"
        "Return JSON with: buggy_code, fixed_code, bug_description, bug_type (logic/syntax/runtime/performance), topic."
    ),
    "review": (
        "Generate a {language} code snippet and a detailed code review.\n"
        "Return JSON with: code, review_comments (array of strings), severity (minor/major/critical), suggested_fix, topic."
    ),
    "docstring": (
        "Generate an undocumented {language} function and write its complete documentation.\n"
        "Return JSON with: undocumented_code, documented_code, docstring, parameters (array), return_description, topic."
    ),
}


def _get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return AsyncOpenAI(api_key=api_key)


def _validate_python_syntax(code: str) -> tuple[bool, str]:
    """Check Python code for syntax errors. Returns (is_valid, error_message)."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


def _extract_code_from_response(text: str, language: str) -> str:
    """Extract code from fenced code blocks if present."""
    pattern = rf"```(?:{language}|python|js|ts)?\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


async def _generate_single_code_row(
    client: AsyncOpenAI,
    prompt: str,
    columns: List[str],
    code_type: str,
    language: str,
    index: int,
    semaphore: asyncio.Semaphore,
    examples: List[dict],
) -> dict:
    async with semaphore:
        type_prompt = CODE_TYPE_PROMPTS[code_type].format(language=language)
        system = (
            f"You are a synthetic code dataset generator. Generate realistic, diverse {language} code examples.\n"
            f"Context: {prompt}\n"
            f"{type_prompt}\n"
            f"Make example #{index + 1} different from others — vary complexity, topic, and patterns.\n"
            f"Return ONLY valid JSON — no markdown fences around the JSON itself."
        )
        if examples:
            ex = examples[index % len(examples)]
            system += f"\n\nExample row for reference (generate something DIFFERENT):\n{json.dumps(ex)}"

        for attempt in range(3):
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"Generate one {code_type} example in {language}."},
                    ],
                    temperature=0.85,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content.strip()
                data = json.loads(raw)

                # Validate Python syntax if applicable
                syntax_errors = {}
                if language == "python":
                    for field in ["implementation", "fixed_code", "buggy_code", "documented_code", "undocumented_code", "code", "unit_tests"]:
                        if field in data and data[field]:
                            valid, err = _validate_python_syntax(data[field])
                            if not valid:
                                syntax_errors[field] = err

                row = {"language": language, "code_type": code_type, "status": "succeeded"}

                # Populate requested columns
                for col in columns:
                    row[col] = data.get(col, "")

                # Always include core fields
                for key in data:
                    if key not in row:
                        row[key] = data[key]

                if syntax_errors:
                    row["syntax_warnings"] = syntax_errors

                return row

            except json.JSONDecodeError as e:
                if attempt == 2:
                    return {"status": "failed", "error": f"JSON parse error: {e}"}
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == 2:
                    return {"status": "failed", "error": str(e)}
                await asyncio.sleep(2 ** attempt)

    return {"status": "failed", "error": "Max retries exceeded"}


async def _generate_all_code(
    prompt: str,
    columns: List[str],
    num_rows: int,
    examples: List[dict],
    params: dict,
) -> List[dict]:
    code_type = params.get("code_type", "function")
    language = params.get("language", "python")
    concurrency = min(int(params.get("concurrency", CONCURRENCY)), 5)

    if code_type not in VALID_CODE_TYPES:
        return [{"status": "failed", "error": f"Invalid code_type '{code_type}'. Must be: {VALID_CODE_TYPES}"}] * num_rows
    if language not in VALID_LANGUAGES:
        return [{"status": "failed", "error": f"Invalid language '{language}'. Must be: {VALID_LANGUAGES}"}] * num_rows

    client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _generate_single_code_row(client, prompt, columns, code_type, language, i, semaphore, examples)
        for i in range(num_rows)
    ]

    results = []
    with tqdm(total=num_rows, desc=f"Generating {code_type} ({language})") as pbar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            pbar.update(1)

    return results


def generate_code_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic code datasets.

    Args:
        prompt: Domain context (e.g. "data structure algorithms", "REST API handlers")
        columns: Column names for output rows
        num_rows: Number of examples to generate
        examples: Optional few-shot example rows
        params: Optional dict with keys:
            - code_type: "function"|"unittest"|"bugfix"|"review"|"docstring" (default: "function")
            - language: "python"|"javascript"|"typescript"|"go"|"rust"|"java" (default: "python")
            - concurrency: parallel LLM calls (default: 3, max: 5)

    Returns:
        List of dicts with code fields + status.
        Python code is syntax-validated; syntax_warnings added for any issues.

    Example::

        rows = generate_code_data(
            prompt="Sorting and searching algorithms",
            columns=["function_signature", "implementation", "docstring", "complexity"],
            num_rows=10,
            params={"code_type": "function", "language": "python"},
        )
    """
    examples = examples or []
    params = params or {}
    return asyncio.get_event_loop().run_until_complete(
        _generate_all_code(prompt, columns, num_rows, examples, params)
    )
