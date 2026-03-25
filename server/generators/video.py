"""
Video synthetic data generator.
Uses Replicate API for video generation (async polling with exponential backoff)
and GPT-4o Vision for frame annotation.
"""
import os
import json
import time
import base64
import asyncio
import tempfile
from pathlib import Path
from typing import List, Optional

import requests
import httpx
from openai import AsyncOpenAI
from tqdm.auto import tqdm
import nest_asyncio

nest_asyncio.apply()

REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"
MODEL_VERSION = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"
OUTPUT_DIR = Path(os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs")) / "video"

POLL_INTERVALS = [5, 10, 20, 40, 60, 60, 60, 60, 60, 60]  # seconds, capped at 60s
MAX_POLL_ATTEMPTS = 60  # 10 minutes max
CONCURRENCY = 2  # Video gen is expensive


def _get_replicate_token() -> str:
    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN environment variable is not set")
    return token


def _get_openai_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return AsyncOpenAI(api_key=api_key)


async def _poll_replicate(prediction_id: str, headers: dict) -> dict:
    """Poll Replicate prediction with exponential backoff until terminal state."""
    poll_url = f"{REPLICATE_API_URL}/{prediction_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        for i, interval in enumerate(POLL_INTERVALS):
            await asyncio.sleep(interval)
            response = await client.get(poll_url, headers=headers)
            response.raise_for_status()
            prediction = response.json()
            status = prediction.get("status")
            if status in ("succeeded", "failed", "canceled"):
                return prediction
    raise TimeoutError(f"Video generation timed out after {sum(POLL_INTERVALS)}s")


async def _annotate_frames(
    client: AsyncOpenAI,
    video_path: Path,
    num_keyframes: int = 5,
) -> List[dict]:
    """Extract keyframes from video and annotate with GPT-4o Vision."""
    try:
        import cv2
    except ImportError:
        return []

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    frame_indices = [int(i * total_frames / num_keyframes) for i in range(num_keyframes)]

    frame_b64s = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        _, buf = cv2.imencode(".jpg", frame)
        frame_b64s.append({
            "index": idx,
            "timestamp": round(idx / fps, 2),
            "b64": base64.b64encode(buf.tobytes()).decode("utf-8"),
        })
    cap.release()

    annotations = []
    for frame_info in frame_b64s:
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_info['b64']}"}},
                        {"type": "text", "text": "Describe this video frame in detail. Include: main subjects, actions, setting, colors, and any text visible. Be concise (2-3 sentences)."},
                    ],
                }],
                max_tokens=200,
            )
            annotations.append({
                "frame_index": frame_info["index"],
                "timestamp": frame_info["timestamp"],
                "description": response.choices[0].message.content.strip(),
            })
        except Exception as e:
            annotations.append({
                "frame_index": frame_info["index"],
                "timestamp": frame_info["timestamp"],
                "description": f"Annotation failed: {e}",
            })

    return annotations


async def _generate_single_video(
    prompt: str,
    index: int,
    width: int,
    height: int,
    fps: int,
    num_frames: int,
    annotate_frames: bool,
    num_keyframes: int,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        token = _get_replicate_token()
        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }

        try:
            # Submit prediction
            payload = {
                "version": MODEL_VERSION,
                "input": {
                    "prompt": prompt,
                    "num_frames": num_frames,
                    "fps": fps,
                    "width": width,
                    "height": height,
                },
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(REPLICATE_API_URL, headers=headers, json=payload)
                if resp.status_code != 201:
                    raise Exception(f"Failed to start generation: {resp.text}")
                prediction = resp.json()

            prediction_id = prediction["id"]

            # Poll until complete
            prediction = await _poll_replicate(prediction_id, headers)
            if prediction["status"] != "succeeded":
                raise Exception(f"Generation {prediction['status']}: {prediction.get('error', 'unknown error')}")

            video_url = prediction["output"]
            if isinstance(video_url, list):
                video_url = video_url[0]

            # Download video
            video_path = OUTPUT_DIR / f"video_{index}.mp4"
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()
            video_path.write_bytes(video_response.content)
            video_base64 = base64.b64encode(video_response.content).decode("utf-8")

            # Save metadata
            metadata = {
                "prompt": prompt,
                "video_url": video_url,
                "width": width,
                "height": height,
                "fps": fps,
                "num_frames": num_frames,
                "replicate_prediction_id": prediction_id,
            }
            label_path = OUTPUT_DIR / f"video_{index}.json"
            label_path.write_text(json.dumps(metadata, indent=2))

            row = {
                "video_path": str(video_path),
                "video_url": video_url,
                "video_base64": video_base64,
                "duration_seconds": round(num_frames / fps, 2),
                "fps": fps,
                "resolution": f"{width}x{height}",
                "prediction_id": prediction_id,
                "status": "succeeded",
            }

            # Frame annotation via GPT-4o Vision
            if annotate_frames:
                openai_client = _get_openai_client()
                frame_annotations = await _annotate_frames(openai_client, video_path, num_keyframes)
                row["frame_annotations"] = frame_annotations

            return row

        except Exception as e:
            return {"status": "failed", "error": str(e), "index": index}


async def _generate_all_videos(
    prompt: str,
    columns: List[str],
    num_rows: int,
    examples: List[dict],
    params: dict,
) -> List[dict]:
    width = int(params.get("width", 576))
    height = int(params.get("height", 320))
    fps = int(params.get("fps", 6))
    num_frames = int(params.get("num_frames", 24))
    annotate = bool(params.get("annotate_frames", False))
    num_keyframes = int(params.get("num_keyframes", 5))
    concurrency = min(int(params.get("concurrency", CONCURRENCY)), 4)

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        _generate_single_video(prompt, i, width, height, fps, num_frames, annotate, num_keyframes, semaphore)
        for i in range(num_rows)
    ]

    results = []
    with tqdm(total=num_rows, desc="Generating videos") as pbar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            pbar.update(1)

    return results


def generate_video_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 1,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic videos using Replicate API with async polling.

    Args:
        prompt: Video scene description
        columns: Column names for the output
        num_rows: Number of videos to generate
        examples: Optional example rows
        params: Optional dict with keys:
            - width: frame width (default: 576)
            - height: frame height (default: 320)
            - fps: frames per second (default: 6)
            - num_frames: total frames (default: 24)
            - annotate_frames: bool, run GPT-4o Vision (default: False)
            - num_keyframes: frames to annotate (default: 5)
            - concurrency: parallel generations (default: 2, max: 4)

    Returns:
        List of dicts with video_path, video_base64, frame_annotations, status
    """
    examples = examples or []
    params = params or {}
    return asyncio.get_event_loop().run_until_complete(
        _generate_all_videos(prompt, columns, num_rows, examples, params)
    )
