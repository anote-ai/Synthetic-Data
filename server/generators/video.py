"""
Video synthetic data generator — async Replicate polling + GPT-4o Vision frame annotations.
No interactive OpenCV UI; all labeling is headless.
"""
import asyncio
import base64
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import httpx

try:
    import nest_asyncio as _nest
    _nest.apply()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_MODEL_VERSION = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"
_REPLICATE_BASE = "https://api.replicate.com/v1"
_POLL_BACKOFF = [5, 10, 20, 40, 60]  # seconds between polls

_OUTPUT_DIR = Path(os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs")) / "video"


def _output_dir() -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _OUTPUT_DIR


# ── Replicate async client ────────────────────────────────────────────────────

async def _submit_prediction(client: httpx.AsyncClient, token: str, prompt: str, params: dict) -> str:
    fps = int(params.get("fps", 6))
    width, height = _parse_resolution(params.get("resolution", "576x320"))
    payload = {
        "version": _MODEL_VERSION,
        "input": {
            "prompt": prompt,
            "num_frames": int(params.get("num_frames", fps * int(params.get("duration", 4)))),
            "fps": fps,
            "width": width,
            "height": height,
        },
    }
    resp = await client.post(
        f"{_REPLICATE_BASE}/predictions",
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["urls"]["get"]


async def _poll_prediction(client: httpx.AsyncClient, token: str, poll_url: str) -> str:
    """Poll until succeeded/failed; return video URL on success."""
    headers = {"Authorization": f"Token {token}"}
    for wait in _POLL_BACKOFF + [60] * 20:  # up to ~30 minutes
        await asyncio.sleep(wait)
        resp = await client.get(poll_url, headers=headers, timeout=30)
        resp.raise_for_status()
        prediction = resp.json()
        status = prediction.get("status")
        if status == "succeeded":
            return prediction["output"]
        if status in ("failed", "canceled"):
            raise RuntimeError(f"Replicate prediction {status}: {prediction.get('error', 'unknown')}")
    raise TimeoutError("Video generation timed out")


# ── Frame extraction & GPT-4o Vision annotation ──────────────────────────────

def _extract_keyframes(video_path: str, num_keyframes: int = 5) -> list[str]:
    """Return list of base64-encoded JPEG keyframes, or empty list if cv2 unavailable."""
    try:
        import cv2  # optional dependency
    except ImportError:
        logger.warning("cv2 not available — skipping keyframe extraction")
        return []
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    indices = [int(total * i / num_keyframes) for i in range(num_keyframes)]
    frames_b64 = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        _, buf = cv2.imencode(".jpg", frame)
        frames_b64.append(base64.b64encode(buf).decode())
    cap.release()
    return frames_b64


async def _annotate_frames(frames_b64: list[str], prompt: str) -> list[dict]:
    """Call GPT-4o Vision to describe each keyframe."""
    import openai
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    client = openai.AsyncOpenAI(api_key=api_key)
    annotations = []
    for i, b64 in enumerate(frames_b64):
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"This is keyframe {i} from a synthetic video generated with prompt: '{prompt}'. "
                                    "Describe the scene in 1-2 sentences."
                                ),
                            },
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ],
                    }
                ],
                max_tokens=150,
            )
            description = resp.choices[0].message.content.strip()
        except Exception as e:
            description = f"annotation failed: {e}"
        annotations.append({"frame_index": i, "description": description})
    return annotations


# ── Per-row generation ────────────────────────────────────────────────────────

async def _generate_one(
    client: httpx.AsyncClient,
    token: str,
    prompt: str,
    index: int,
    params: dict,
) -> dict:
    try:
        poll_url = await _submit_prediction(client, token, prompt, params)
        video_url = await _poll_prediction(client, token, poll_url)

        # Download video
        out_path = _output_dir() / f"video_{index}.mp4"
        video_bytes = (await client.get(video_url, timeout=120)).content
        out_path.write_bytes(video_bytes)

        result: dict = {
            "video_path": str(out_path),
            "video_url": video_url,
            "fps": int(params.get("fps", 6)),
            "resolution": params.get("resolution", "576x320"),
            "duration_seconds": float(params.get("duration", 4)),
            "frame_annotations": [],
            "status": "succeeded",
        }

        if params.get("annotate_frames", False):
            num_kf = int(params.get("num_keyframes", 5))
            frames = _extract_keyframes(str(out_path), num_kf)
            if frames:
                result["frame_annotations"] = await _annotate_frames(frames, prompt)

        return result
    except Exception as e:
        logger.error("Video generation row %d failed: %s", index, e)
        return {"status": "failed", "error": str(e)}


async def _generate_all(prompt: str, num_rows: int, params: dict) -> list:
    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        return [{"status": "failed", "error": "REPLICATE_API_TOKEN not set"}] * num_rows

    async with httpx.AsyncClient() as client:
        tasks = [_generate_one(client, token, prompt, i, params) for i in range(num_rows)]
        return await asyncio.gather(*tasks)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_video_data(
    prompt: str,
    columns: list,
    num_rows: int = 1,
    examples: list = None,
    params: dict = None,
) -> list:
    """
    Generate synthetic video data using the Replicate API (async, non-blocking poll).

    params keys:
        fps: frames per second (default 6)
        resolution: e.g. "576x320" or "1280x720" (default "576x320")
        duration: video length in seconds (default 4)
        annotate_frames: bool — run GPT-4o Vision on keyframes (default False)
        num_keyframes: how many frames to annotate (default 5)
    """
    params = params or {}
    try:
        return asyncio.get_event_loop().run_until_complete(_generate_all(prompt, num_rows, params))
    except RuntimeError as e:
        return [{"status": "failed", "error": str(e)}] * num_rows


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_resolution(res: str) -> tuple[int, int]:
    try:
        w, h = res.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 576, 320
