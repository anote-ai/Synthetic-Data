"""
anote-generate — Python SDK for the Anote Synthetic Data API.

Quick start::

    from anote_generate import Anote

    client = Anote(api_key="your-key")
    rows = client.generate(
        task_type="text",
        columns=["question", "answer"],
        prompt="Generate Q&A pairs about Python programming",
        num_rows=10,
    )

See https://docs.anote.ai for full documentation.
"""

from .core import (
    Anote,
    AnoteGenerate,  # backwards-compatible alias
    AnoteAuthError,
    AnoteValidationError,
    AnoteRateLimitError,
    AnoteServerError,
)

__version__ = "1.0.0"
__all__ = [
    "Anote",
    "AnoteGenerate",
    "AnoteAuthError",
    "AnoteValidationError",
    "AnoteRateLimitError",
    "AnoteServerError",
    "__version__",
]
