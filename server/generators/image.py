"""
Image synthetic data generator.
Uses OpenAI DALL-E 3 for image generation and YOLO11 for object detection.
Images are returned as base64 and saved to a configurable output directory.
"""
import os
import json
import base64
import requests
from pathlib import Path
from typing import List, Optional
from openai import OpenAI
from tqdm.auto import tqdm

# Lazy-loaded YOLO model singleton
_yolo_model = None

VALID_SIZES = {"1024x1024", "1792x1024", "1024x1792"}
VALID_STYLES = {"vivid", "natural"}
OUTPUT_DIR = Path(os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs")) / "images"
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolo11n.pt")


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key)


def _get_yolo_model():
    """Lazily load YOLO model once and cache it."""
    global _yolo_model
    if _yolo_model is None:
        try:
            from ultralytics import YOLO
            _yolo_model = YOLO(YOLO_MODEL_PATH)
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLO model from '{YOLO_MODEL_PATH}': {e}")
    return _yolo_model


def _run_detection(img_path: Path, confidence: float = 0.25) -> dict:
    """Run YOLO detection on an image. Returns structured detection results."""
    model = _get_yolo_model()
    results = model(str(img_path), conf=confidence, verbose=False)
    result = results[0]

    detected_path = img_path.parent / f"detected_{img_path.name}"
    result.save(filename=str(detected_path))

    detections = []
    for box, cls, conf in zip(
        result.boxes.xyxy.tolist(),
        result.boxes.cls.tolist(),
        result.boxes.conf.tolist(),
    ):
        detections.append({
            "label": result.names[int(cls)],
            "confidence": round(float(conf), 4),
            "bbox": [round(x, 2) for x in box],
        })

    return {
        "detections": detections,
        "detected_image_path": str(detected_path),
        "detected_image_base64": _encode_image(detected_path),
    }


def _encode_image(path: Path) -> str:
    """Return base64-encoded image string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _generate_single_image(
    client: OpenAI,
    prompt: str,
    index: int,
    size: str,
    style: str,
    run_detection: bool,
    detection_confidence: float,
) -> dict:
    """Generate one image, optionally run detection, return result dict."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for attempt in range(3):
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size=size,
                style=style,
                response_format="url",
            )
            image_url = response.data[0].url
            revised_prompt = response.data[0].revised_prompt

            # Download image
            img_data = requests.get(image_url, timeout=30).content
            img_path = OUTPUT_DIR / f"image_{index}.png"
            img_path.write_bytes(img_data)

            row = {
                "image_path": str(img_path),
                "image_url": image_url,
                "image_base64": _encode_image(img_path),
                "revised_prompt": revised_prompt,
                "size": size,
                "style": style,
                "status": "succeeded",
            }

            if run_detection:
                detection = _run_detection(img_path, detection_confidence)
                row.update(detection)

            return row

        except Exception as e:
            if attempt == 2:
                return {"status": "failed", "error": str(e)}
            import time
            time.sleep(2 ** attempt)

    return {"status": "failed", "error": "Max retries exceeded"}


def generate_image_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 1,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic images using DALL-E 3 with optional YOLO object detection.

    Args:
        prompt: Description of images to generate
        columns: Column names (used to filter which fields to return)
        num_rows: Number of images to generate
        examples: Optional example rows (used to refine the prompt style)
        params: Optional dict with keys:
            - image_size: "1024x1024" | "1792x1024" | "1024x1792" (default: "1024x1024")
            - style: "vivid" | "natural" (default: "vivid")
            - run_detection: bool (default: True)
            - detection_confidence: float 0-1 (default: 0.25)
            - output_dir: override output directory

    Returns:
        List of dicts with image_path, image_base64, detections, status
    """
    params = params or {}
    size = params.get("image_size", "1024x1024")
    style = params.get("style", "vivid")
    run_detection = params.get("run_detection", True)
    confidence = float(params.get("detection_confidence", 0.25))

    if size not in VALID_SIZES:
        return [{"status": "failed", "error": f"Invalid image_size '{size}'. Must be one of: {VALID_SIZES}"}] * num_rows
    if style not in VALID_STYLES:
        return [{"status": "failed", "error": f"Invalid style '{style}'. Must be one of: {VALID_STYLES}"}] * num_rows

    # Override output dir if specified
    global OUTPUT_DIR
    if "output_dir" in params:
        OUTPUT_DIR = Path(params["output_dir"]) / "images"

    client = _get_client()
    full_prompt = f"High-quality, photorealistic synthetic training image: {prompt}. Style: {style}."

    results = []
    for i in tqdm(range(num_rows), desc="Generating images"):
        row = _generate_single_image(client, full_prompt, i, size, style, run_detection, confidence)
        results.append(row)

    return results
