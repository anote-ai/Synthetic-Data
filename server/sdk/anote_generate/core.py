"""
Anote Synthetic Data API client.
"""
from __future__ import annotations

import os
import time
import json
import logging
from typing import List, Optional, Iterator, Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.anote.ai"
DEFAULT_TIMEOUT = 120
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 4, 8]  # seconds


class AnoteAuthError(Exception):
    """Raised on 401 Unauthorized responses."""


class AnoteValidationError(Exception):
    """Raised on 422 Unprocessable Entity responses."""
    def __init__(self, message: str, details: list = None):
        super().__init__(message)
        self.details = details or []


class AnoteRateLimitError(Exception):
    """Raised on 429 Too Many Requests responses."""


class AnoteServerError(Exception):
    """Raised on 5xx server errors."""


class Anote:
    """
    Client for the Anote Synthetic Data API.

    Args:
        api_key: Your Anote API key (Bearer token). If not provided,
                 reads from the ANOTE_API_KEY environment variable.
        base_url: API base URL. Defaults to https://api.anote.ai.
        timeout: Request timeout in seconds (default: 120).

    Example::

        from anote_generate import Anote

        client = Anote(api_key="your-key")
        data = client.generate(
            task_type="text",
            columns=["question", "answer"],
            prompt="Generate Q&A pairs about Python",
            num_rows=10,
        )
        for row in data:
            print(row["question"], "->", row["answer"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("ANOTE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Pass api_key= or set ANOTE_API_KEY environment variable."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"anote-generate/{_get_version()}",
        })

    def generate(
        self,
        task_type: str,
        columns: List[str],
        prompt: str,
        num_rows: int = 5,
        examples: Optional[List[dict]] = None,
        params: Optional[dict] = None,
        export_format: Optional[str] = None,
    ) -> List[dict]:
        """
        Generate synthetic data rows.

        Args:
            task_type: Modality to generate. One of: text, image, audio, video, agent, pii, tabular, code.
            columns: List of column names for the output rows.
            prompt: Natural language description of the data to generate.
            num_rows: Number of rows to generate (default: 5, max: 100).
            examples: Optional list of example rows for few-shot generation.
            params: Optional modality-specific parameters dict.
            export_format: If set, download as file. One of: csv, jsonl, parquet, json.

        Returns:
            List of dicts, each containing the requested columns plus "status".

        Raises:
            AnoteAuthError: Invalid or missing API key.
            AnoteValidationError: Invalid request parameters.
            AnoteRateLimitError: Rate limit exceeded.
            AnoteServerError: Server-side error.

        Example::

            rows = client.generate(
                task_type="text",
                columns=["review", "sentiment", "rating"],
                prompt="Product reviews for a coffee maker",
                num_rows=20,
                examples=[{"review": "Great coffee!", "sentiment": "positive", "rating": "5"}],
            )
        """
        payload = {
            "task_type": task_type,
            "prompt": prompt,
            "num_rows": num_rows,
            "columns": columns,
            "examples": examples or [],
            "params": params or {},
        }

        url = f"{self.base_url}/public/generate"
        response = self._post_with_retry(url, payload)
        data = response.json()
        return data.get("data", data)

    def _post_with_retry(self, url: str, payload: dict) -> requests.Response:
        """POST with exponential backoff retry on 5xx and network errors."""
        last_exc = None
        for attempt, backoff in enumerate(RETRY_BACKOFF + [None]):
            try:
                resp = self._session.post(url, json=payload, timeout=self.timeout)
                self._raise_for_status(resp)
                return resp
            except (AnoteServerError, requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                last_exc = e
                if backoff is None:
                    break
                logger.warning("Request failed (attempt %d/%d): %s. Retrying in %ds...",
                               attempt + 1, MAX_RETRIES, e, backoff)
                time.sleep(backoff)
            except (AnoteAuthError, AnoteValidationError, AnoteRateLimitError):
                raise  # Don't retry client errors
        raise last_exc

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an API request and return the parsed response body."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        resp = self._session.request(method, url, **kwargs)
        self._raise_for_status(resp)

        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def _raise_for_status(self, resp: requests.Response) -> None:
        """Raise typed exceptions based on HTTP status code."""
        if resp.ok:
            return
        try:
            body = resp.json()
        except Exception:
            body = {"error": resp.text}

        if resp.status_code == 401:
            raise AnoteAuthError(body.get("error", "Unauthorized"))
        elif resp.status_code == 422:
            raise AnoteValidationError(
                body.get("error", "Validation failed"),
                details=body.get("details", [])
            )
        elif resp.status_code == 429:
            raise AnoteRateLimitError("Rate limit exceeded. Please slow down requests.")
        elif resp.status_code >= 500:
            raise AnoteServerError(f"Server error {resp.status_code}: {body.get('error', resp.text)}")
        else:
            raise requests.HTTPError(f"HTTP {resp.status_code}: {body}")

    def to_dataframe(self, data: List[dict]):
        """
        Convert generate() output to a pandas DataFrame.

        Args:
            data: List of row dicts from generate()

        Returns:
            pandas.DataFrame

        Example::

            rows = client.generate(task_type="text", columns=["q", "a"], prompt="...", num_rows=10)
            df = client.to_dataframe(rows)
            df.to_csv("output.csv", index=False)
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_dataframe(). Run: pip install pandas")
        return pd.DataFrame(data)

    def to_file(self, data: List[dict], path: str, fmt: Optional[str] = None) -> str:
        """
        Save generate() output to a file.

        Args:
            data: List of row dicts from generate()
            path: Output file path
            fmt: Format override. Auto-detected from file extension if not provided.
                 Supported: csv, jsonl, json, parquet

        Returns:
            Absolute path to saved file

        Example::

            rows = client.generate(task_type="text", columns=["q", "a"], prompt="...", num_rows=10)
            client.to_file(rows, "dataset.csv")
            client.to_file(rows, "dataset.jsonl")
        """
        import pathlib
        p = pathlib.Path(path)
        ext = fmt or p.suffix.lstrip(".")

        if ext == "csv":
            import csv, io
            if not data:
                p.write_text("")
                return str(p.resolve())
            keys = list(data[0].keys())
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)
            p.write_text(out.getvalue())
        elif ext == "jsonl":
            p.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in data) + "\n")
        elif ext == "parquet":
            df = self.to_dataframe(data)
            df.to_parquet(path, index=False)
        else:
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        return str(p.resolve())

    def generate_async(
        self,
        task_type: str,
        columns: List[str],
        prompt: str,
        num_rows: int = 5,
        examples: Optional[List[dict]] = None,
        params: Optional[dict] = None,
        webhook_url: Optional[str] = None,
    ) -> "Job":
        """
        Submit a generation job and return immediately with a Job handle.

        Use job.wait() to poll until completion.

        Example::

            job = client.generate_async(task_type="video", columns=["video_url"], prompt="...", num_rows=3)
            rows = job.wait()
        """
        body = {
            "task_type": task_type,
            "columns": columns,
            "prompt": prompt,
            "num_rows": num_rows,
            "examples": examples or [],
            "params": params or {},
        }
        if webhook_url:
            body["webhook_url"] = webhook_url
        resp = self._request("POST", "/public/generate/async", json=body)
        return Job(resp["job_id"], client=self)

    def _get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/public/jobs/{job_id}")

    def _cancel_job(self, job_id: str) -> dict:
        return self._request("DELETE", f"/public/jobs/{job_id}")


class Job:
    """Handle for an async generation job."""

    def __init__(self, job_id: str, client: "Anote"):
        self.job_id = job_id
        self._client = client
        self._data: Optional[dict] = None

    @property
    def status(self) -> str:
        self._data = self._client._get_job(self.job_id)
        return self._data.get("status", "unknown")

    def wait(self, poll_interval: float = 5.0, timeout: float = 1800.0) -> List[dict]:
        """Poll until job completes. Returns list of result rows."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._data = self._client._get_job(self.job_id)
            s = self._data.get("status")
            if s == "succeeded":
                return self._data.get("result") or []
            if s in ("failed", "canceled"):
                raise RuntimeError(f"Job {self.job_id} {s}: {self._data.get('error')}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {self.job_id} did not complete within {timeout}s")

    def cancel(self) -> dict:
        self._data = self._client._cancel_job(self.job_id)
        return self._data

    def __repr__(self) -> str:
        return f"Job(job_id={self.job_id!r}, status={self._data.get('status', '?') if self._data else '?'})"


def _get_version() -> str:
    try:
        from anote_generate import __version__
        return __version__
    except Exception:
        return "unknown"


# Backwards-compatible alias
AnoteGenerate = Anote
