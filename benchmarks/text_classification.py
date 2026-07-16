"""Reproducible real-vs-synthetic text classification benchmark.

Input files are JSONL records with configurable text and label fields. The real
file is deterministically split into train/test; the held-out test set is never
used for training. A standard-library multinomial Naive Bayes model keeps the
benchmark easy to run in CI and on customer data without uploading it.
"""
import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path, text_field="text", label_field="label"):
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            rows.append((str(record[text_field]), str(record[label_field])))
    return rows


def split_real(rows, test_fraction=0.2, seed=42):
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    test_size = max(1, round(len(shuffled) * test_fraction))
    return shuffled[test_size:], shuffled[:test_size]


def tokens(text):
    return re.findall(r"[\w']+", text.lower())


def train(rows):
    label_counts = Counter(label for _, label in rows)
    word_counts = defaultdict(Counter)
    totals = Counter()
    vocabulary = set()
    for text, label in rows:
        words = tokens(text)
        word_counts[label].update(words)
        totals[label] += len(words)
        vocabulary.update(words)
    return label_counts, word_counts, totals, vocabulary


def predict(model, text):
    label_counts, word_counts, totals, vocabulary = model
    total_rows = sum(label_counts.values())
    scores = {}
    for label, count in label_counts.items():
        score = math.log(count / total_rows)
        denominator = totals[label] + len(vocabulary)
        for word in tokens(text):
            score += math.log((word_counts[label][word] + 1) / denominator)
        scores[label] = score
    return max(scores, key=scores.get)


def evaluate(training_rows, test_rows):
    model = train(training_rows)
    pairs = [(label, predict(model, text)) for text, label in test_rows]
    labels = sorted({label for label, _ in pairs} | {pred for _, pred in pairs})
    accuracy = sum(actual == pred for actual, pred in pairs) / len(pairs)
    f1_scores = []
    for label in labels:
        tp = sum(actual == label and pred == label for actual, pred in pairs)
        fp = sum(actual != label and pred == label for actual, pred in pairs)
        fn = sum(actual == label and pred != label for actual, pred in pairs)
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        f1_scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return {"accuracy": round(accuracy, 4), "macro_f1": round(sum(f1_scores) / len(f1_scores), 4)}


def run(real_rows, synthetic_rows, seed=42, test_fraction=0.2):
    real_train, real_test = split_real(real_rows, test_fraction, seed)
    conditions = {
        "real_only": real_train,
        "synthetic_only": synthetic_rows,
        "real_plus_synthetic": real_train + synthetic_rows,
    }
    return {
        "seed": seed,
        "held_out_real_rows": len(real_test),
        "training_rows": {name: len(rows) for name, rows in conditions.items()},
        "results": {name: evaluate(rows, real_test) for name, rows in conditions.items()},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", required=True)
    parser.add_argument("--synthetic", required=True)
    parser.add_argument("--text-field", default="text")
    parser.add_argument("--label-field", default="label")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run(
        load_jsonl(args.real, args.text_field, args.label_field),
        load_jsonl(args.synthetic, args.text_field, args.label_field),
        args.seed,
    )
    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
