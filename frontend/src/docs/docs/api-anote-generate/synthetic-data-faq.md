# Does synthetic data work well enough to train on?

Short answer: synthetic data can be strong enough for training and augmentation when the task is well-scoped, the schema is explicit, and the generated rows are evaluated against real held-out examples. It should not be treated as a free replacement for real labels without measurement.

## When synthetic data is a good fit

Synthetic data is usually most useful for:

- Classification tasks with clear labels, such as support ticket intent or product review sentiment.
- Structured extraction tasks, such as NER, PII redaction, and contract clause extraction.
- Edge-case coverage where real examples are rare, sensitive, or expensive to label.
- Test fixtures for data pipelines, annotation tools, and model evaluation harnesses.

It is a weaker fit when the task requires fresh real-world facts, hidden business context, or legally/medically authoritative answers.

## Evidence from published work

Research does not say that synthetic data is magic. It does show that high-quality generated data can improve models in specific settings:

- [Self-Instruct](https://arxiv.org/abs/2212.10560) generated instruction, input, and output examples, filtered low-quality rows, and used them for instruction tuning. The paper reports large improvements over the base GPT-3 model on instruction-following evaluations.
- [TinyStories](https://arxiv.org/abs/2305.07759) used GPT-generated stories to train and evaluate very small language models, showing that carefully constrained synthetic text can teach targeted language behavior.
- [Textbooks Are All You Need](https://arxiv.org/abs/2306.11644) trained phi-1 with a mix of high-quality web data and synthetically generated textbook-style data, demonstrating strong code benchmark results at small model scale.

The common pattern is quality control: narrow task definition, explicit format, filtering, and evaluation. Anote should follow the same pattern for production synthetic datasets.

## How to evaluate an Anote synthetic dataset

Use a direct comparison before trusting generated data for training:

| Condition | Training data | What it tells you |
| --- | --- | --- |
| Real baseline | Real labeled examples only | How strong the current data is |
| Synthetic only | Synthetic examples generated from task instructions and a few seeds | Whether generated rows carry enough signal |
| Augmented | Real examples plus synthetic examples | Whether synthetic data improves coverage |

Evaluate all three on the same held-out real test set. Track accuracy, F1, per-label recall, and failure examples. For extraction tasks, inspect entity-level precision and recall, not just row-level accuracy.

## Quality checklist

Before using generated rows in training:

- Confirm every row matches the requested schema.
- Check class balance and label distribution.
- Remove duplicates and near-duplicates.
- Review a sample of rows manually.
- Evaluate on held-out real data.
- Keep the prompt, examples, model, and generation parameters with the dataset for reproducibility.

## Honest answer for buyers

If someone asks, "Will a model trained on synthetic data perform as well as one trained on real labeled data?", the best answer is:

> It depends on the task. For classification, extraction, redaction, and edge-case augmentation, synthetic data can be highly effective when measured against real held-out data. For factual or domain-authoritative tasks, synthetic data should augment human-reviewed data rather than replace it.

Anote's job is to make that evaluation easier by generating structured data, preserving generation metadata, surfacing quality metrics, and supporting export into downstream training workflows.
