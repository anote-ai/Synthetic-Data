"""
Export utilities for converting generated data to various formats.
Supports CSV, JSONL (OpenAI fine-tuning compatible), Parquet, and JSON.
"""
import csv
import json
import io
from typing import List
from flask import Response, jsonify


def to_csv(data: List[dict]) -> str:
    """Convert list of dicts to CSV string."""
    if not data:
        return ""
    fieldnames = list(data[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


def to_jsonl(data: List[dict]) -> str:
    """Convert list of dicts to JSONL string (one JSON object per line)."""
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in data) + "\n"


def to_parquet_bytes(data: List[dict]) -> bytes:
    """Convert list of dicts to Parquet bytes."""
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise RuntimeError("pandas and pyarrow required for Parquet export. Run: pip install pandas pyarrow")
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def make_export_response(data: List[dict], fmt: str, filename: str = "synthetic_data") -> Response:
    """
    Build a Flask Response for file download.

    Args:
        data: List of row dicts
        fmt: "csv" | "jsonl" | "parquet" | "json"
        filename: Base filename (without extension)

    Returns:
        Flask Response with appropriate Content-Type and Content-Disposition
    """
    fmt = fmt.lower().strip()

    if fmt == "csv":
        content = to_csv(data)
        return Response(
            content,
            mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    elif fmt == "jsonl":
        content = to_jsonl(data)
        return Response(
            content,
            mimetype="application/jsonl",
            headers={"Content-Disposition": f'attachment; filename="{filename}.jsonl"'},
        )
    elif fmt == "parquet":
        content = to_parquet_bytes(data)
        return Response(
            content,
            mimetype="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}.parquet"'},
        )
    elif fmt == "json":
        return Response(
            json.dumps({"data": data}, indent=2, ensure_ascii=False),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
    else:
        raise ValueError(f"Unsupported format '{fmt}'. Must be: csv, jsonl, parquet, json")
