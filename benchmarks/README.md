# Training utility benchmark

This benchmark answers a narrow question: does synthetic training data improve
performance on a held-out set of real examples?

Prepare two JSONL files with the same `text` and `label` fields, then run:

```bash
python benchmarks/text_classification.py \
  --real private/real-support-tickets.jsonl \
  --synthetic outputs/synthetic-support-tickets.jsonl \
  --output benchmark-report.json
```

The report compares real-only, synthetic-only, and combined training conditions
using the same held-out real test set. Commit the report only when its source
data can be shared; customer or sensitive datasets should remain private.

This baseline is deliberately simple and reproducible. A production evaluation
should additionally use the intended downstream model, multiple seeds, per-label
metrics, confidence intervals, and manual error review.
