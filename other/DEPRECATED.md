# DEPRECATED

This directory contains an early FastAPI prototype of the Synthetic Data API.

**It is no longer maintained and should not be used in production.**

## Canonical Implementation

The production API is the Flask app in [`server/`](../server/). See the main [README.md](../README.md) for setup instructions.

## What's here

- `other/api/` — FastAPI rewrite prototype (not wired to deployed system)
- `other/images/` — Example synthetic image outputs

## Why it's kept

Kept for historical reference. The FastAPI version explored Pydantic-based request validation and a cleaner router structure, some of which informed the Flask implementation.
