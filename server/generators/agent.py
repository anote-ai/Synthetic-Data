"""
Agent trace synthetic data generator.
Generates realistic multi-turn conversations where an AI agent uses tools to complete tasks.
Uses OpenAI function-calling API to produce structurally valid tool call sequences.
"""
import os
import json
import asyncio
import re
from typing import List, Optional, Any
from openai import AsyncOpenAI
from tqdm.auto import tqdm
import nest_asyncio

nest_asyncio.apply()

MODEL = "gpt-4o-mini"
CONCURRENCY = 3
MAX_RETRIES = 3

DIFFICULTY_PROMPTS = {
    "easy": "The task is straightforward. The agent should complete it in 1-3 tool calls with no complications.",
    "medium": "The task requires 3-6 tool calls. Include one minor complication (missing info, clarification needed).",
    "hard": "The task is complex. Requires 5-10 tool calls. Include edge cases, error recovery, and multi-step reasoning.",
}

DEFAULT_TOOLS = [
    {"name": "search_knowledge_base", "description": "Search internal documentation or FAQs", "parameters": {"query": "string"}},
    {"name": "lookup_record", "description": "Look up a record by ID or email", "parameters": {"identifier": "string", "type": "string"}},
    {"name": "update_record", "description": "Update a record field", "parameters": {"id": "string", "field": "string", "value": "any"}},
    {"name": "send_notification", "description": "Send email or message notification", "parameters": {"recipient": "string", "message": "string"}},
    {"name": "escalate", "description": "Escalate to human agent with reason", "parameters": {"reason": "string", "priority": "string"}},
]


def _get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return AsyncOpenAI(api_key=api_key)


def _format_tools_for_prompt(tools: List[dict]) -> str:
    lines = []
    for t in tools:
        params = json.dumps(t.get("parameters", {}))
        lines.append(f"- {t['name']}({params}): {t['description']}")
    return "\n".join(lines)


def _build_generation_prompt(
    scenario: str,
    tools: List[dict],
    difficulty: str,
    outcome: str,
    columns: List[str],
    examples: List[dict],
    index: int,
) -> str:
    difficulty_desc = DIFFICULTY_PROMPTS.get(difficulty, DIFFICULTY_PROMPTS["medium"])
    tools_desc = _format_tools_for_prompt(tools)

    prompt = f"""Generate a realistic agent trace for the following scenario.

Scenario: {scenario}
Difficulty: {difficulty} — {difficulty_desc}
Required outcome: {outcome}

Available tools:
{tools_desc}

Generate a JSON object with this exact structure:
{{
  "task": "<specific user task/request as a string>",
  "tools_available": [<list of tool names>],
  "turns": [
    {{"role": "user", "content": "<initial user message>"}},
    {{"role": "assistant", "content": null, "tool_calls": [{{"name": "<tool>", "args": {{<args>}}}}]}},
    {{"role": "tool", "tool_name": "<tool>", "content": "<realistic tool response>"}},
    {{"role": "assistant", "content": "<response or null if more tool calls>", "tool_calls": []}}
  ],
  "outcome": "{outcome}",
  "num_tool_calls": <integer>,
  "resolution": "<brief description of how the task was resolved>"
}}

Rules:
- Turns must alternate: user → assistant (with tool_call) → tool → assistant → ...
- Tool calls must reference tools from the available list
- Tool args must match the tool's parameter schema
- The trace must feel realistic and natural
- Make this trace DIFFERENT from any previous traces (this is index {index})
- Return ONLY valid JSON, no markdown, no explanation
"""
    if examples:
        ex = examples[index % len(examples)]
        prompt += f"\n\nExample trace for reference (generate something DIFFERENT):\n{json.dumps(ex, indent=2)}"
    return prompt


async def _generate_single_trace(
    client: AsyncOpenAI,
    scenario: str,
    tools: List[dict],
    difficulty: str,
    outcome: str,
    columns: List[str],
    examples: List[dict],
    index: int,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                prompt = _build_generation_prompt(scenario, tools, difficulty, outcome, columns, examples, index)
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a synthetic dataset generator specializing in AI agent traces. "
                                "Always return valid JSON matching the requested schema exactly."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.85,
                    response_format={"type": "json_object"},
                )

                raw = response.choices[0].message.content.strip()
                trace = json.loads(raw)

                # Validate required fields
                required = {"task", "turns", "outcome", "num_tool_calls"}
                if not required.issubset(trace.keys()):
                    raise ValueError(f"Missing required fields: {required - trace.keys()}")

                # Ensure tools_available is set
                if "tools_available" not in trace:
                    trace["tools_available"] = [t["name"] for t in tools]

                # Build the output row with requested columns
                row = {"status": "succeeded"}
                for col in columns:
                    row[col] = trace.get(col, "")

                # Always include core trace fields
                for key in ["task", "turns", "outcome", "num_tool_calls", "tools_available", "resolution"]:
                    if key not in row:
                        row[key] = trace.get(key, "")

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


def _plan_outcomes(num_rows: int, outcome_distribution: dict) -> List[str]:
    """Plan outcome labels for each row based on distribution."""
    outcomes = []
    totals = {k: max(1, round(v * num_rows)) for k, v in outcome_distribution.items()}
    for outcome, count in totals.items():
        outcomes.extend([outcome] * count)
    outcomes = outcomes[:num_rows]
    while len(outcomes) < num_rows:
        outcomes.append("success")
    return outcomes


async def _generate_all_traces(
    prompt: str,
    columns: List[str],
    num_rows: int,
    examples: List[dict],
    params: dict,
) -> List[dict]:
    scenario = params.get("scenario", prompt)
    tools = params.get("tools", DEFAULT_TOOLS)
    difficulty = params.get("difficulty", "medium")
    concurrency = min(int(params.get("concurrency", CONCURRENCY)), 5)
    outcome_distribution = params.get("outcome_distribution", {"success": 0.7, "failure": 0.2, "partial": 0.1})

    if difficulty not in DIFFICULTY_PROMPTS:
        return [{"status": "failed", "error": f"Invalid difficulty '{difficulty}'. Must be: easy, medium, hard"}] * num_rows

    planned_outcomes = _plan_outcomes(num_rows, outcome_distribution)

    client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _generate_single_trace(client, scenario, tools, difficulty, planned_outcomes[i], columns, examples, i, semaphore)
        for i in range(num_rows)
    ]

    results = []
    with tqdm(total=num_rows, desc="Generating agent traces") as pbar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            pbar.update(1)

    return results


def generate_agent_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 5,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic agent traces with multi-turn tool-use conversations.

    Args:
        prompt: Scenario description (e.g. "customer support for a SaaS product")
        columns: Columns for the output (task, turns, outcome, num_tool_calls, etc.)
        num_rows: Number of traces to generate
        examples: Optional example traces
        params: Optional dict with keys:
            - scenario: domain context (defaults to prompt)
            - tools: list of tool defs [{name, description, parameters}]
            - difficulty: "easy" | "medium" | "hard" (default: "medium")
            - outcome_distribution: {"success": 0.7, "failure": 0.2, "partial": 0.1}
            - concurrency: parallel LLM calls (default: 3, max: 5)

    Returns:
        List of dicts with task, turns, outcome, num_tool_calls, status
    """
    examples = examples or []
    params = params or {}
    return asyncio.get_event_loop().run_until_complete(
        _generate_all_traces(prompt, columns, num_rows, examples, params)
    )
