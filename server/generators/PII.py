import sys
import subprocess
import importlib.util
import os
import json
import random
import string
import re
import asyncio

# Ensure dependencies
REQUIRED = ["faker", "openai", "tqdm", "nest_asyncio"]
for pkg in REQUIRED:
    if importlib.util.find_spec(pkg) is None:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg])

from faker import Faker
from tqdm.auto import tqdm
import nest_asyncio; nest_asyncio.apply()
from openai import AsyncOpenAI


WORD_MIN, WORD_MAX = 40, 120
MODEL = "gpt-4o-mini"
TEMP = 0.9
CONCURRENCY = 5  
DRY_RUN = False

def ask_int(prompt_text, default):
    while True:
        resp = input(f"{prompt_text} [{default}]: ").strip()
        if resp == "":
            return default
        if resp.isdigit() and int(resp) > 0:
            return int(resp)
        print("Please enter a positive integer.")

def ask_float(prompt_text, default):
    while True:
        resp = input(f"{prompt_text} [{default}]: ").strip()
        if resp == "":
            return default
        try:
            v = float(resp)
            if 0.0 <= v <= 1.0:
                return v
        except:
            pass
        print("Please enter a number between 0.0 and 1.0.")

def ask_yesno(prompt_text, default=True):
    default_str = "Y/n" if default else "y/N"
    while True:
        resp = input(f"{prompt_text} ({default_str}): ").strip().lower()
        if resp == "":
            return default
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("Please answer yes or no.")

def load_api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()
    fallback_path = os.path.expanduser("~/.openai_key")
    if os.path.isfile(fallback_path):
        try:
            with open(fallback_path, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return k
        except Exception:
            pass
    return None

OPENAI_KEY = load_api_key()
if not OPENAI_KEY:
    print("No Key")
    DRY_RUN = True
else:
    os.environ.setdefault("OPENAI_API_KEY", OPENAI_KEY)

client = AsyncOpenAI() if not DRY_RUN else None

# PII and prompt setup
fake = Faker("en_US")

def luhn_complete(prefix=4, length=16):
    num = [int(x) for x in str(prefix)]
    while len(num) < length - 1:
        num.append(random.randint(0, 9))
    s = sum(d if i % 2 else (d * 2 - 9 if d * 2 > 9 else d * 2)
            for i, d in enumerate(reversed(num)))
    num.append((10 - s % 10) % 10)
    return "".join(map(str, num))

rand_dl = lambda: f"{fake.state_abbr()} {fake.bothify('?########')}"
rand_pas = lambda: fake.random_number(9, fix_len=True)
rand_pl = lambda: f"{''.join(random.choices(string.ascii_uppercase, k=3))}-{random.randint(1000,9999)}"
rand_mrn = lambda: "MR" + fake.bothify("#" * 5)
rand_emp = lambda: "E" + fake.bothify("#" * 5)
rand_bio = lambda: "BD" + fake.bothify("#" * 5)
rand_vin = lambda: ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ0123456789', k=17))

FIELD = {
    "NAME": fake.name,
    "ADDRESS": lambda: fake.address().replace("\n", ", "),
    "PHONE": fake.phone_number,
    "BIRTH": lambda: fake.date_of_birth(minimum_age=18, maximum_age=90).strftime("%Y-%m-%d"),
    "DL": rand_dl,
    "PASSPORT": rand_pas,
    "SSN": fake.ssn,
    "CREDIT": luhn_complete,
    "MRN": rand_mrn,
    "PLATE": rand_pl,
    "IP": fake.ipv4_public,
    "EMP": rand_emp,
    "VIN": rand_vin,
    "BIO": rand_bio,
}

SYSTEM = (
    "You write short casual text ABOUT the person. The text needs to be reasonable and understandable to real people, and never in first-person. "
    "Use the full name exactly as given (no I / my / me). "
    "End with a period or exclamation mark."
)

USER_TEMPLATES = [
    """Write an informal paragraph of {minw}-{maxw} words using all of the following facts.
Do not list them directly—blend them naturally into the writing. Finish with proper punctuation.""",
    """Write a casual character sketch in {minw}-{maxw} words.
Include all the values below exactly as written, embedded smoothly in full sentences.""",
    """Write a short, natural-sounding story or moment (between {minw}-{maxw} words) that includes every detail listed below.
Avoid using a list, and make sure all the facts are clearly present in the text.""",
    """Compose a professional background summary of {minw}-{maxw} words.
Ensure that each of the following values is mentioned verbatim and presented as a polished, coherent paragraph.""",
    """Write a concise formal profile (between {minw}-{maxw} words) that incorporates all of the following details.
Avoid listing—integrate each fact into natural, professional sentences.""",
    """Generate a third-person summary suitable for an internal report or personnel file.
Use {minw}-{maxw} words and include each fact below exactly as provided, without using a bulleted list.""",
    """Create a brief narrative overview of {minw}-{maxw} words suitable for a government or institutional document.
All values below must appear as written, woven into a professional and neutral tone."""
]

TONE_HINTS = [
    "Make it sound like gossip overheard at a cafe.",
    "Pretend a coworker is describing them.",
    "Make it feel like a neighbor sharing a story.",
    "Give it the tone of a casual anecdote at a party.",
    "Imagine a friend describing them after a trip.",
    "Write in the style of a biographical note for a personnel file.",
    "Present the facts as part of a formal character reference.",
    "Write a third-person summary for an official document.",
    "Frame it as a descriptive paragraph in a background check report.",
    "Present the individual in a professional tone as if for an HR profile.",
    "Write it like a brief overview in a government or legal file.",
    "Describe the person for inclusion in a corporate personnel directory.",
    "Frame the text as if summarizing details for a formal application.",
    "Write a short profile as it might appear in a confidential case report.",
    "Describe the person as if in an identity verification summary."
]

def shuffle_seed_table(seed: dict) -> str:
    items = list(seed.items())
    random.shuffle(items)
    return "\n".join(f"- {key}: {value}" for key, value in items)

def make_messages(seed: dict, extra_prompt: str = ""):
    seed_table = shuffle_seed_table(seed)
    user_template = random.choice(USER_TEMPLATES)
    tone_hint = random.choice(TONE_HINTS)
    user_message = user_template.format(minw=WORD_MIN, maxw=WORD_MAX)
    if extra_prompt:
        user_message = f"{extra_prompt}\n\n{user_message}"
    user_message = user_message + "\n" + tone_hint + "\n\n" + seed_table
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_message}
    ]

# Core generation logic reused
async def generate_single_example():
    selected_fields = random.sample(list(FIELD), k=random.randint(4, 6))
    seed_values = {field: FIELD[field]() for field in selected_fields}

    if DRY_RUN:
        parts = [f"{label} is {value}" for label, value in seed_values.items()]
        generated_text = " ".join(parts)[:WORD_MAX * 5].strip()
        if not generated_text.endswith((".", "!")):
            generated_text += "."
        entities = []
        for label, value in seed_values.items():
            match = re.search(re.escape(str(value)), generated_text)
            if match:
                entities.append([match.start(), match.end(), label])
        return {"text": generated_text, "entities": entities, "seed": seed_values}

    messages = make_messages(seed_values)
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=TEMP,
            top_p=0.95,
            max_tokens=200
        )
    except Exception as e:
        print(f"API call failed for one example: {e}")
        parts = [f"{label} is {value}" for label, value in seed_values.items()]
        generated_text = " ".join(parts)[:WORD_MAX * 5].strip()
        if not generated_text.endswith((".", "!")):
            generated_text += "."
        entities = []
        for label, value in seed_values.items():
            match = re.search(re.escape(str(value)), generated_text)
            if match:
                entities.append([match.start(), match.end(), label])
        return {"text": generated_text, "entities": entities, "seed": seed_values}

    generated_text = response.choices[0].message.content.strip()
    entities = []
    for label, value in seed_values.items():
        match = re.search(re.escape(str(value)), generated_text)
        if match:
            entities.append([match.start(), match.end(), label])
    return {"text": generated_text, "entities": entities, "seed": seed_values}

async def generate_dataset(num_examples=500, max_concurrent_requests=10):
    semaphore = asyncio.Semaphore(max_concurrent_requests)
    async def worker():
        async with semaphore:
            return await generate_single_example()
    tasks = [worker() for _ in range(num_examples)]
    results = []
    for coro in tqdm(asyncio.as_completed(tasks), total=num_examples, desc="Generating"):
        result = await coro
        results.append(result)
    return results

async def generate_dataset_stream(num_examples=500, max_concurrent_requests=10, output_path="synthetic_example.jsonl", on_new_example=None):
    """
    Incrementally generates examples, writing each to disk as soon as it's done.
    """
    semaphore = asyncio.Semaphore(max_concurrent_requests)
    async def worker():
        async with semaphore:
            return await generate_single_example()

    tasks = [worker() for _ in range(num_examples)]
    with open(output_path, "w", encoding="utf-8") as f:
        for coro in tqdm(asyncio.as_completed(tasks), total=num_examples, desc="Generating (stream)"):
            result = await coro
            json_line = json.dumps(result, ensure_ascii=False)
            f.write(json_line + "\n")
            f.flush()
            if on_new_example:
                try:
                    on_new_example(result)
                except Exception:
                    pass
            print(json_line)
    return None

async def maybe_preview():
    print("\n--- Previewing one example ---")
    try:
        example = await generate_single_example()
    except Exception as e:
        print(f"Preview failed: {e}")
        print("Please check API access or configuration.")
        sys.exit(1)
    print("\nGenerated Text:\n", example["text"])
    print("\nSeed values:", example["seed"])
    print("\nEntities:", example["entities"])
    proceed = ask_yesno("Proceed with full generation?", True)
    if not proceed:
        print("Aborted by user.")
        sys.exit(0)

async def generate_PII_data(prompt, columns, num_rows, examples):

    dataset = await generate_dataset(num_examples=num_rows, max_concurrent_requests=CONCURRENCY)
    return dataset

def generate_PII_data_sync(prompt, columns, num_rows, examples):

    return asyncio.run(generate_text_data(prompt, columns, num_rows, examples))

def generate_pii_data(prompt, columns, num_rows, examples, params=None):
    return generate_PII_data_sync(prompt, columns, num_rows, examples)

# Main entry (interactive)
if __name__ == "__main__":
    print("Synthetic PII Text Generator Interactive")
    N_ROWS = ask_int("How many synthetic PII examples to generate?", 100)
    CONCURRENCY = ask_int("Maximum concurrent requests?", 10)
    WORD_MIN, WORD_MAX = 40, 120
    MODEL = "gpt-4o-mini"
    TEMP = ask_float("Temperature (0.0–1.0)?", 0.9)
    PREVIEW = ask_yesno("Would you like to preview one example before full generation?", True)

    async def main():
        if PREVIEW:
            await maybe_preview()

        print(f"\nStarting generation of {N_ROWS} examples with concurrency={CONCURRENCY} using model={MODEL} temperature={TEMP}")
        await generate_dataset_stream(num_examples=N_ROWS, max_concurrent_requests=CONCURRENCY)
        print(f"\nSaved {N_ROWS} synthetic records to synthetic_example.jsonl")

    asyncio.run(main())
