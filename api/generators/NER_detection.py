import os
import sys
import re
import json
import random
import string
import asyncio
import subprocess
import inspect
from pathlib import Path
from typing import List, Dict, Any
from faker import Faker
from tqdm.auto import tqdm
import pandas as pd
import nest_asyncio
from sklearn.metrics import precision_score, recall_score, f1_score
from openai import AsyncOpenAI
import spacy
from spacy.util import load_config
from spacy.tokens import DocBin
from spacy.training.example import Example
import itertools
import random


# API
os.environ["OPENAI_API_KEY"] = "API KEY Here"
client = AsyncOpenAI()

# CONFIG
fake = Faker("en_US")

# PII generators
def luhn_complete(prefix=4, length=16):

    num = [int(x) for x in str(prefix)]

    while len(num) < length-1:
      num.append(random.randint(0,9))

    s = sum(d if i%2 else (d*2-9 if d*2>9 else d*2) for i,d in enumerate(reversed(num)))

    num.append((10-s%10)%10);

    return "".join(map(str,num))

# PII fields generators
rand_license  = lambda: f"{fake.state_abbr()} {fake.bothify('?########')}"
rand_passport = lambda: fake.random_number(9, fix_len=True)
rand_plate  = lambda: f"{''.join(random.choices(string.ascii_uppercase,k=3))}-{random.randint(1000,9999)}"
rand_medicalrecord = lambda: "MR"+fake.bothify("#"*5)
rand_employment = lambda: "E"+fake.bothify("#"*5)
rand_biometric = lambda: "BD"+fake.bothify("#"*5)
rand_vin = lambda: ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ0123456789',k=17))

# PII fields
FIELD = {
    "NAME": fake.name,
    "ADDRESS": lambda: fake.address().replace("\n", ", "),
    "PHONE": fake.phone_number,
    "BIRTHDATE": lambda: fake.date_of_birth(minimum_age=1, maximum_age=90).strftime("%Y-%m-%d"),
    "EMAIL": fake.email,
    "SSN": fake.ssn,
    "PASSPORT": rand_passport,
    "LICENSE": rand_license,
    "CREDITCARD": luhn_complete,
    "MEDICALRECORD": rand_medicalrecord,
    "BIOMETRIC": rand_biometric,
    "PLATE": rand_plate,
    "VIN": rand_vin,
    "IP": fake.ipv4_public,
    "EMPLOYMENT": rand_employment,
    "EDUCATION": lambda: fake.bothify("STU#####"),
}


# Constants
WORD_MIN, WORD_MAX = 40, 120

SYSTEM = (
    "You write short casual text ABOUT the person. The text needs to be reasonable and understandable to real people, and never in first-person. "
    "Use the full name exactly as given (no I / my / me). "
    "End with a period or exclamation mark."
  
)

# Multiple user prompt styles
USER_TEMPLATES = [
    # Informal styles
    """Write an informal paragraph of {minw}-{maxw} words using all of the following facts. 
Do not list them directly—blend them naturally into the writing. Finish with proper punctuation.""",

    """Write a casual character sketch in {minw}-{maxw} words. 
Include all the values below exactly as written, embedded smoothly in full sentences.""",

    """Write a short, natural-sounding story or moment (between {minw}-{maxw} words) that includes every detail listed below. 
Avoid using a list, and make sure all the facts are clearly present in the text.""",

    # Formal styles
    """Compose a professional background summary of {minw}-{maxw} words. 
Ensure that each of the following values is mentioned verbatim and presented in a polished, coherent paragraph.""",

    """Write a concise formal profile (between {minw}-{maxw} words) that incorporates all of the following details. 
Avoid listing—integrate each fact into natural, professional sentences.""",

    """Generate a third-person summary suitable for an internal report or personnel file. 
Use {minw}-{maxw} words and include each fact below exactly as provided, without using a bulleted list.""",

    """Create a brief narrative overview of {minw}-{maxw} words suitable for a government or institutional document. 
All values below must appear as written, woven into a professional and neutral tone."""
]


#  tone or perspective variation
TONE_HINTS = [
    "Make it sound like gossip overheard at a cafe.",
    "Pretend a coworker is describing them.",
    "Make it feel like a neighbor sharing a story.",
    "Give it the tone of a casual anecdote at a party.",
    "Imagine a friend describing them after a trip."
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

def prompt(seed: dict):

    seed_table = shuffle_seed_table(seed)
    user_template = random.choice(USER_TEMPLATES)
    tone_hint = random.choice(TONE_HINTS)

    user_message = user_template.format(minw=WORD_MIN, maxw=WORD_MAX) + "\n" + tone_hint + "\n\n" + seed_table

    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_message}
    ]


# GPT model
MODEL = "gpt-4o-mini"
TEMP = 0.9

# Generate a single synthetic PII text
async def generate_single_example():
    # Randomly choose 4 to 6 PII types
    selected_fields = random.sample(list(FIELD.keys()), k=random.randint(4, 6))

    # Generate values
    seed_values = {}
    for field in selected_fields:
        generator = FIELD[field]
        value = generator() if callable(generator) else generator
        seed_values[field] = value

    # Format the prompt
    messages = prompt(seed_values)

    # Call the OpenAI
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMP,
        top_p=0.95,
        max_tokens=200
    )

    # Extract the generated text
    generated_text = response.choices[0].message.content.strip()

    # Find entity in the generated text
    entities = []
    for label, value in seed_values.items():
        match = re.search(re.escape(str(value)), generated_text)
        if match:
            start = match.start()
            end = match.end()
            entities.append([start, end, label])

    return {
        "text": generated_text,
        "entities": entities
    }


# Generate a full dataset
async def generate_dataset(num_examples=300, max_concurrent_requests=10):
    semaphore = asyncio.Semaphore(max_concurrent_requests)
    results = []

    # check the limit of concurrent requests
    async def worker():
        async with semaphore:
            example = await generate_single_example()
            return example

    # Launch all tasks
    tasks = []
    for _ in range(num_examples):
        task = worker()
        tasks.append(task)

    # Wait for all tasks to complete
    for coroutine in tqdm(asyncio.as_completed(tasks), total=num_examples, desc="Generating"):
        result = await coroutine
        results.append(result)

    return results


N_ROWS = 300
CONCURRENCY = 10

# Save the examples
async def main():
    # Generate examples
    synthetic_rows = await generate_dataset(
        num_examples=N_ROWS,
        max_concurrent_requests=CONCURRENCY
    )

    output_path = "synthetic_example.jsonl"

    # Write each example as a JSON
    with open(output_path, "w", encoding="utf-8") as file:
        for row in synthetic_rows:
            json_line = json.dumps(row, ensure_ascii=False)
            file.write(json_line + "\n")

    print("Saved", len(synthetic_rows), "synthetic records to", output_path)

asyncio.run(main())



example_path = "synthetic_example.jsonl"

# Preview
# with open(example_path, "r", encoding="utf-8") as f:
#     first_five = list(itertools.islice(f, 5))

# for i, line in enumerate(first_five, start=1):
#     obj = json.loads(line)
#     print(f"\n--- Sample {i} ---")
#     print("Text:", obj["text"])
#     print("Entities:", obj["entities"])


# Load synthetic JSONL
with open(example_path, "r", encoding="utf-8") as f:
    examples = []
    for line in f:
        example = json.loads(line)
        examples.append(example)

# Shuffle 
random.seed(42)
random.shuffle(examples)

split_idx = int(0.9 * len(examples))
train_data = examples[:split_idx]
dev_data = examples[split_idx:]

# Create output folder
Path("data").mkdir(exist_ok=True)

def convert_to_spacy_format(examples, save_path):
    nlp = spacy.blank("en")
    doc_bin = DocBin(store_user_data=True)
    skipped = 0

    for i, example in enumerate(examples):
        text = example["text"]
        entities = example["entities"]

        doc = nlp.make_doc(text)
        spans = []

        for start, end, label in entities:
            span = doc.char_span(start, end, label=label)
            if span:
                spans.append(span)
            else:
                skipped += 1
                print(f"Skipped invalid span in example {i}: ({start}, {end}, {label})")

        doc.ents = spacy.util.filter_spans(spans)
        doc_bin.add(doc)

    doc_bin.to_disk(save_path)

    print(f"\nSaved {len(examples) - skipped} examples to '{save_path}'")
    if skipped:
        print(f"{skipped} spans were skipped.")

convert_to_spacy_format(train_data, "data/train.spacy")
convert_to_spacy_format(dev_data, "data/dev.spacy")

# Generate config file
subprocess.run([
    "python", "-m", "spacy", "init", "config", "config.cfg",
    "--lang", "en", "--pipeline", "ner", "--force", "--optimize", "accuracy"
])

subprocess.run([
    "python", "-m", "spacy", "download", "en_core_web_trf"
])



# Load config
cfg = load_config("config.cfg")

# Remove init_tok2vec i
if "initialize" in cfg and "init_tok2vec" in cfg["initialize"]:
    del cfg["initialize"]["init_tok2vec"]

# Set  paths for training and dev data
cfg["corpora"] = {
    "train": {
        "@readers": "spacy.Corpus.v1",
        "path": "data/train.spacy"
    },
    "dev": {
        "@readers": "spacy.Corpus.v1",
        "path": "data/dev.spacy"
    }
}

#  remove any 'vectors' keys
def remove_vectors(config_section):

    if isinstance(config_section, dict):
        config_section.pop("vectors", None)

        for value in config_section.values():
            remove_vectors(value)

    elif isinstance(config_section, list):

        for item in config_section:
            remove_vectors(item)

remove_vectors(cfg)

# Savevto cfg
cfg.to_disk("config.cfg")
print("Cleaned and saved config.cfg")

subprocess.run([
    "python", "-m", "spacy", "train", "config.cfg",
    "--output", "training_output",
    "--gpu-id", "0",
    "--verbose"
])


# Load evaluation examples
examples = []

with open("synthetic_example.jsonl", "r", encoding="utf-8") as f:

    for line in f:
        data = json.loads(line.strip())
        text = data["text"]
        entities = data["entities"] 
        labeled_spans = [(text[start:end], label) for start, end, label in entities]
        examples.append((text, labeled_spans))

# # Preview
# for i, (text, entities) in enumerate(examples[:3], start=1):
#     print(f"\n--- Example {i} ---")
#     print("TEXT:", text)
#     print("ENTITIES:", entities)

# Load the model
nlp = spacy.load("training_output/model-best")

# Evaluate the model
results = []
for text, true_ents in examples:
    doc = nlp(text)
    pred_ents = [(ent.text, ent.label_) for ent in doc.ents]

    true_set = set(true_ents)
    pred_set = set(pred_ents)

    tp = len(true_set & pred_set)
    fp = len(pred_set - true_set)
    fn = len(true_set - pred_set)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1_score  = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    iou       = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0

    results.append({
        "Sentence": text,
        "Ground Truth Entities": true_ents,
        "Model Predicted Entities": pred_ents,
        "Precision": round(precision, 2),
        "Recall": round(recall, 2),
        "F1 Score": round(f1_score, 2),
        "IoU": round(iou, 2)
    })

# Convert to DF
df = pd.DataFrame(results)
df.head()

