"""
Image synthetic data generator.
Uses DALL-E 3 for generation and optionally YOLO for object detection.
"""
import os
import base64
import requests
from typing import List, Optional

import openai

VALID_SIZES = {"1024x1024", "1792x1024", "1024x1792"}
VALID_STYLES = {"vivid", "natural"}
OUTPUT_DIR = os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs/images/")

_yolo_model = None


def _get_yolo():
    """Lazy-load YOLO singleton — not available in all environments."""
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO(os.getenv("YOLO_MODEL_PATH", "yolo11n.pt"))
    return _yolo_model


def generate_image_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 1,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    params = params or {}
    image_size = params.get("image_size", "1024x1024")
    style = params.get("style", "vivid")
    run_detection = params.get("run_detection", True)
    confidence = params.get("detection_confidence", 0.25)

    if image_size not in VALID_SIZES:
        return [{"status": "failed", "error": f"invalid image_size '{image_size}'. Must be one of {VALID_SIZES}"}] * num_rows
    if style not in VALID_STYLES:
        return [{"status": "failed", "error": f"invalid style '{style}'. Must be one of {VALID_STYLES}"}] * num_rows

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [{"status": "failed", "error": "OPENAI_API_KEY not set"}] * num_rows

    client = openai.OpenAI(api_key=api_key)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = []
    for i in range(num_rows):
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size=image_size,
                style=style,
            )
            image_url = response.data[0].url
            revised_prompt = getattr(response.data[0], "revised_prompt", prompt)

            img_bytes = requests.get(image_url, timeout=30).content
            img_path = os.path.join(OUTPUT_DIR, f"image_{i}.png")
            with open(img_path, "wb") as f:
                f.write(img_bytes)
            image_base64 = base64.b64encode(img_bytes).decode()

            row = {
                "image_path": img_path,
                "image_url": image_url,
                "image_base64": image_base64,
                "revised_prompt": revised_prompt,
                "size": image_size,
                "style": style,
                "status": "succeeded",
            }

            if run_detection:
                try:
                    model = _get_yolo()
                    det_results = model(img_path, conf=confidence)
                    boxes = det_results[0].boxes
                    names = det_results[0].names
                    detections = [
                        {
                            "label": names[int(cls)],
                            "confidence": round(float(conf_val), 4),
                            "bbox": [round(float(x), 2) for x in box],
                        }
                        for cls, conf_val, box in zip(
                            boxes.cls.tolist(),
                            boxes.conf.tolist(),
                            boxes.xyxy.tolist(),
                        )
                    ]
                    det_path = os.path.join(OUTPUT_DIR, f"detected_image_{i}.png")
                    det_results[0].save(filename=det_path)
                    row["detections"] = detections
                    row["detected_image_path"] = det_path
                except Exception as det_err:
                    row["detections"] = []
                    row["detection_error"] = str(det_err)

            results.append(row)
        except Exception as e:
            results.append({"status": "failed", "error": str(e)})

    return results
