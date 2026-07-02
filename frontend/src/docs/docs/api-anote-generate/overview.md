
# Overview

The `anote-generate` SDK enables developers to programmatically generate high-quality synthetic datasets across supported task types: text, image, video, audio, agent, pii, language, tabular, and code. This package is designed to work seamlessly with the Anote Synthetic Data API and offers a Pythonic interface for generating datasets that can be used for training, testing, and evaluation of AI models.

## Key Features

- Unified API for multimodal synthetic data generation.
- Supports few-shot examples to guide generation.
- `generate()` returns generated rows as structured data; use `to_file()` to save rows locally.
- Compatible with Anote’s human-in-the-loop workflows.
- Built for supported text, image, video, audio, agent, pii, language, tabular, and code generation workflows.
