import os
import json
import openai
import time
from difflib import get_close_matches
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")


qa_generator_model = "gpt-4o-mini"
text_polisher_model = "gpt-4"
delay_between_requests = 1.2
polish_batch_size = 10
polish_cache: dict[str, str] = {}

DEFAULT_TOPICS = [
    "Cooking", "Geography", "Astronomy", "Culture",
    "Technology", "Medicine", "Literature", "History",
    "Music", "Chemistry", "Biology", "Economy",
    "Mathematics", "Art", "Physics", "Science"
]

TOPIC_WIKI_URLS = {
    "Cooking": ["https://ja.wikipedia.org/wiki/料理"],
    "Geography": ["https://ja.wikipedia.org/wiki/地理"],
    "Astronomy": ["https://ja.wikipedia.org/wiki/天文学"],
    "Culture": ["https://ja.wikipedia.org/wiki/文化"],
    "Technology": ["https://ja.wikipedia.org/wiki/技術"],
    "Medicine": ["https://ja.wikipedia.org/wiki/医学"],
    "Literature": ["https://ja.wikipedia.org/wiki/文学"],
    "History": ["https://ja.wikipedia.org/wiki/歴史"],
    "Music": ["https://ja.wikipedia.org/wiki/音楽"],
    "Chemistry": ["https://ja.wikipedia.org/wiki/化学"],
    "Biology": ["https://ja.wikipedia.org/wiki/生物学"],
    "Economy": ["https://ja.wikipedia.org/wiki/経済"],
    "Mathematics": ["https://ja.wikipedia.org/wiki/数学"],
    "Art": ["https://ja.wikipedia.org/wiki/芸術"],
    "Physics": ["https://ja.wikipedia.org/wiki/物理学"],
    "Science": ["https://ja.wikipedia.org/wiki/科学"]
}

def safe_json_parse(raw: str):
    raw = raw.strip()
    start = raw.find('[')
    end = raw.rfind(']')
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end+1]
    return json.loads(raw)

def prompt_for_topics() -> list[str]:
    print("You can choose from the following topics (case-insensitive):")
    for t in DEFAULT_TOPICS:
        print(f"  - {t}")
    print("You may enter multiple comma-separated topics. Leave blank to use all defaults.")
    while True:
        user_input = input("Enter topics: ").strip()
        if not user_input:
            return DEFAULT_TOPICS
        raw_topics = [t.strip() for t in user_input.split(",") if t.strip()]
        if not raw_topics:
            return DEFAULT_TOPICS

        validated = []
        unknown = []
        for t in raw_topics:
            # exact match ignoring case
            matches = [d for d in DEFAULT_TOPICS if d.lower() == t.lower()]
            if matches:
                validated.append(matches[0])
            else:
                # try to suggest close match
                suggestion = get_close_matches(t, DEFAULT_TOPICS, n=1, cutoff=0.6)
                if suggestion:
                    resp = input(f"Did you mean '{suggestion[0]}' instead of '{t}'? [Y/n]: ").strip().lower()
                    if resp in ("", "y", "yes"):
                        validated.append(suggestion[0])
                    else:
                        unknown.append(t)
                else:
                    unknown.append(t)

        if unknown:
            print("The following topics are unrecognized:", ", ".join(unknown))
            confirm = input("Do you still want to include them as-is? [y/N]: ").strip().lower()
            if confirm in ("y", "yes"):
                # include unknown as entered
                validated.extend(unknown)
            else:
                print("Let's try again.")
                continue

        # deduplicate preserving order 
        seen = set()
        final = []
        for topic in validated:
            key = topic.lower()
            if key not in seen:
                seen.add(key)
                final.append(topic)
        if final:
            return final
        print("No valid topics parsed; please try again.")

def prompt_for_num_qas() -> int:
    while True:
        user_input = input("Enter number of Q&A pairs per topic (default 2): ").strip()
        if not user_input:
            return 2
        try:
            n = int(user_input)
            if n <= 0:
                print("Please enter a positive integer.")
                continue
            return n
        except ValueError:
            print("Could not parse input as integer. Try again.")

# Core Generation & Polishing
def generate_qas_for_topic(topic: str, count: int) -> list[dict]:
    prompt = f"""
              Header schema: question, answer, topic
              Topic: \"{topic}\"
              Generate exactly {count} Japanese Q&A objects. Output only a JSON array of objects.
              """
    response = openai.chat.completions.create(
        model=qa_generator_model,
        messages=[
            {"role": "system", "content": "You are a Japanese Q&A dataset generator."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=400,
    )
    text = response.choices[0].message.content
    try:
        return safe_json_parse(text)
    except Exception:
        print(f"JSON parse failed for topic '{topic}'. Raw response:\n{text}")
        raise

def polish_texts(texts: list[str], batch_size: int = polish_batch_size) -> list[str]:
    polished_results = [None] * len(texts)
    for start_idx in range(0, len(texts), batch_size):
        batch = texts[start_idx:start_idx + batch_size]
        to_request = [t for t in batch if t not in polish_cache]
        if to_request:
            numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(batch))
            prompt = "以下の日本語の文章を、自然で簡潔な文に改善してください。\n" + numbered
            response = openai.chat.completions.create(
                model=text_polisher_model,
                messages=[
                    {"role": "system", "content": "You are a Japanese text polisher. Refine the following Japanese text to be natural, concise, and clear."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800,
            )
            lines = response.choices[0].message.content.strip().splitlines()
            for orig, polished_line in zip(batch, lines):
                polish_cache[orig] = polished_line
        for idx, original in enumerate(batch, start=start_idx):
            polished_results[idx] = polish_cache.get(original, original)
    return polished_results

def run_generation_pipeline(topics: list[str], num_qas: int, output_path: str = "qa_dataset.json"):
    all_records = []
    for topic in tqdm(topics, desc="Generating Q&A data"):
        try:
            qas = generate_qas_for_topic(topic, num_qas)
        except Exception:
            print(f"Skipping topic '{topic}' due to error.")
            continue
        for item in qas:
            item["topic"] = topic
            item["reference_urls"] = TOPIC_WIKI_URLS.get(topic, [])
            all_records.append(item)
        time.sleep(delay_between_requests)

    if not all_records:
        print("No Q&A records generated. Exiting.")
        return

    questions = [r.get("question", "") for r in all_records]
    answers = [r.get("answer", "") for r in all_records]
    polished_questions = polish_texts(questions)
    polished_answers = polish_texts(answers)

    for record, pq, pa in zip(all_records, polished_questions, polished_answers):
        record["question_augmented"] = pq
        record["answer_augmented"] = pa

    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(all_records)} Q&A samples to {output_path}")

    try:
        files.download(output_path)
    except Exception:
        print("Automatic download failed; retrieve the file manually from the runtime.")

if __name__ == "__main__":
    topics_list = prompt_for_topics()
    num_per_topic = prompt_for_num_qas()
    run_generation_pipeline(topics_list, num_per_topic)



# ─── Async, language-agnostic generator (issue #42) ──────────────────────────
import asyncio
try:
    import nest_asyncio as _nest
    _nest.apply()
except ImportError:
    pass

_LANG_CONCURRENCY = 3
_LANG_MAX_RETRIES = 3


def _lang_get_async_client(model: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return openai.AsyncOpenAI(api_key=api_key)


def _lang_build_system(prompt: str, columns: list, language: str, examples: list) -> str:
    col_desc = ", ".join(f'"{c}"' for c in columns)
    system = (
        f"You are a multilingual synthetic dataset generator.\n"
        f"Target language: {language}\n"
        f"Context: {prompt}\n"
        f"Each response must be a JSON object with exactly these keys: {col_desc}.\n"
        f"Write all text values in {language}. Return ONLY the JSON object.\n"
    )
    if examples:
        system += f"\nReference examples:\n{json.dumps(examples[:3], ensure_ascii=False)}\n"
    return system


async def _lang_generate_one(
    client, system: str, columns: list, model: str,
    semaphore: asyncio.Semaphore, index: int,
) -> dict:
    async with semaphore:
        for attempt in range(_LANG_MAX_RETRIES):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"Generate row {index + 1}."},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.85,
                )
                raw = resp.choices[0].message.content.strip()
                row = json.loads(raw)
                return {col: row.get(col, "") for col in columns} | {"status": "succeeded"}
            except json.JSONDecodeError as e:
                if attempt == _LANG_MAX_RETRIES - 1:
                    return {"status": "failed", "error": f"JSON parse error: {e}"}
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == _LANG_MAX_RETRIES - 1:
                    return {"status": "failed", "error": str(e)}
                await asyncio.sleep(2 ** attempt)
    return {"status": "failed", "error": "Max retries exceeded"}


async def _lang_generate_all(
    prompt: str, columns: list, num_rows: int, examples: list, params: dict,
) -> list:
    language = params.get("language", params.get("target_language", "English"))
    model = params.get("model", "gpt-4o-mini")
    concurrency = min(int(params.get("concurrency", _LANG_CONCURRENCY)), 8)
    client = _lang_get_async_client(model)
    semaphore = asyncio.Semaphore(concurrency)
    system = _lang_build_system(prompt, columns, language, examples)
    tasks = [
        _lang_generate_one(client, system, columns, model, semaphore, i)
        for i in range(num_rows)
    ]
    results = []
    for coro in asyncio.as_completed(tasks):
        results.append(await coro)
    return results[:num_rows]


def generate_language_data(
    prompt: str,
    columns: list,
    num_rows: int = 5,
    examples: list = None,
    params: dict = None,
) -> list:
    """
    Generate multilingual synthetic data using GPT-4o-mini (async, concurrent).

    params keys:
        language: target language string, e.g. "Japanese", "Spanish" (default: "English")
        model: OpenAI model name (default: "gpt-4o-mini")
        concurrency: parallel API calls (default: 3, max: 8)
    """
    examples = examples or []
    params = params or {}
    try:
        return asyncio.get_event_loop().run_until_complete(
            _lang_generate_all(prompt, columns, num_rows, examples, params)
        )
    except RuntimeError as e:
        return [{"status": "failed", "error": str(e)}] * num_rows
