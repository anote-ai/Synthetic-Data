# Changelog

All notable changes to `anote-generate` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-04-17

### Added
- `Anote` client class with `generate()`, `to_file()`, `to_dataframe()` methods
- Support for all task types: `text`, `image`, `audio`, `video`, `agent`, `pii`, `tabular`, `code`, `language`
- Typed exception hierarchy: `AnoteAuthError`, `AnoteValidationError`, `AnoteRateLimitError`, `AnoteServerError`
- Automatic retry with exponential backoff on transient errors (3 attempts)
- `AnoteGenerate` as backwards-compatible alias
- Streaming support via `generate_stream()` iterator
- Full `pyproject.toml` packaging (migrated from `setup.py`)
- PyPI publish workflow via GitHub Actions on `v*` tags

## [0.20] - 2025-01-01

### Added
- Initial release with basic `generate()` call
