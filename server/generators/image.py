import openai
import json
import requests
import os
from ultralytics import YOLO

openai.api_key = os.getenv("OPENAI_API_KEY") or "INSERT_YOUR_OPENAI_KEY"
YOLO_MODEL_PATH = "yolo11n.pt"

def generate_image_data(prompt: str, columns: list, num_rows: int = 1, examples: list = []) -> list:
    results = []
    prompt_full = f"High-quality illustration of a synthetic data task: {prompt}, use theme colors: #111827, #DEFE47, #28B2FB, white"

    for i in range(num_rows):
        try:
            response = openai.images.generate(
                model="dall-e-3",
                prompt=prompt_full,
                n=1,
                size="1024x1024"
            )
            image_url = response.data[0].url
            img_path = f"generated_image_{i}.png"
            img_data = requests.get(image_url).content
            with open(img_path, "wb") as f:
                f.write(img_data)

            model = YOLO(YOLO_MODEL_PATH)
            results_yolo = model(img_path)
            results_yolo[0].save(filename=f"detected_image_{i}.png")

            results.append({
                "image_path": img_path,
                "image_url": image_url,
                "detections": results_yolo[0].boxes.cls.tolist(),
                "status": "succeeded"
            })
        except Exception as e:
            results.append({"status": "failed", "error": str(e)})

    return results
