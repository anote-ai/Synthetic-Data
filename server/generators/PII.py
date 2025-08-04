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

# Global config
WORD_MIN, WORD_MAX = 40, 120
MODEL = "gpt-4o-mini"
TEMP = 0.9
CONCURRENCY = 5
DRY_RUN = False

# Load API key
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
    print("No API Key found. DRY_RUN enabled.")
    DRY_RUN = True
else:
    os.environ.setdefault("OPENAI_API_KEY", OPENAI_KEY)

client = AsyncOpenAI() if not DRY_RUN else None
fake = Faker("en_US")

# Random PII generators
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
    "Use the full name exactly as given (no I / my / me). End with a period or exclamation mark."
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
]

TONE_HINTS = [
    "Make it sound like gossip overheard at a cafe.",
    "Pretend a coworker is describing them.",
    "Write in the style of a biographical note for a personnel file.",
    "Write a third-person summary for an official document.",
    "Frame the text as if summarizing details for a formal application.",
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
    user_message += "\n" + tone_hint + "\n\n" + seed_table
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_message}
    ]

# Async generation
async def generate_single_example():
    selected_fields = random.sample(list(FIELD), k=random.randint(4, 6))
    seed_values = {field: str(FIELD[field]()) for field in selected_fields}

    if DRY_RUN:
        text = " ".join(f"{k} is {v}" for k, v in seed_values.items())
        if not text.endswith((".", "!")):
            text += "."
        entities = [
            [text.find(v), text.find(v) + len(v), k]
            for k, v in seed_values.items() if v in text
        ]
        return {"text": text, "entities": entities, "seed": seed_values}

    messages = make_messages(seed_values)
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=TEMP,
            top_p=0.95,
            max_tokens=200
        )
        generated_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"API call failed: {e}")
        generated_text = " ".join(f"{k} is {v}" for k, v in seed_values.items())

    entities = [
        [generated_text.find(v), generated_text.find(v) + len(v), k]
        for k, v in seed_values.items() if v in generated_text
    ]
    return {"text": generated_text, "entities": entities, "seed": seed_values}

# Generate full dataset
async def generate_PII_data(prompt, columns, num_rows, examples):
    semaphore = asyncio.Semaphore(CONCURRENCY)
    async def worker():
        async with semaphore:
            return await generate_single_example()
    tasks = [worker() for _ in range(num_rows)]
    return [await t for t in tqdm(asyncio.as_completed(tasks), total=num_rows, desc="Generating")]

# Sync wrapper for Flask
def generate_PII_data_sync(prompt, columns, num_rows, examples):
    return asyncio.run(generate_PII_data(prompt, columns, num_rows, examples))

# Optional CLI
if __name__ == "__main__":
    print("PII Generator CLI (interactive)")
    try:
        num = int(input("How many examples? [100]: ") or 100)
    except:
        num = 100
    output = asyncio.run(generate_PII_data("", [], num, []))
    with open("synthetic_example.jsonl", "w", encoding="utf-8") as f:
        for ex in output:
            f.write(json.dumps(ex) + "\n")
    print(f"Saved {num} examples to synthetic_example.jsonl")
