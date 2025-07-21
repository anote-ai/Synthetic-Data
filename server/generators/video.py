import os
import time
import json
import requests

# TODO: remove hardcoded values
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN") or "r8_TmFVTZiq3U6NgMonmd5eza9YYEdX7YC0FZh8i"
MODEL_VERSION = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"

os.makedirs("dataset/Video", exist_ok=True)
os.makedirs("dataset/labels", exist_ok=True)

def generate_video_data(prompt: str, columns: list, num_rows: int = 1, examples: list = []) -> list:
    results = []
    for i in range(num_rows):
        headers = {
            "Authorization": f"Token {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json",
        }
        data = {
            "version": MODEL_VERSION,
            "input": {
                "prompt": prompt,
                "num_frames": 24,
                "fps": 6,
                "width": 576,
                "height": 320
            }
        }

        response = requests.post("https://api.replicate.com/v1/predictions", headers=headers, data=json.dumps(data))
        if response.status_code != 201:
            results.append({"status": "failed", "error": response.text})
            continue

        prediction = response.json()
        poll_url = prediction["urls"]["get"]
        status = prediction["status"]
        while status not in ["succeeded", "failed", "canceled"]:
            time.sleep(10)
            prediction = requests.get(poll_url, headers=headers).json()
            status = prediction["status"]

        if status != "succeeded":
            results.append({"status": "failed", "error": f"Video generation failed at index {i}"})
            continue

        video_url = prediction["output"]
        video_path = f"dataset/Video/video_{i}.mp4"
        video_data = requests.get(video_url)
        with open(video_path, "wb") as f:
            f.write(video_data.content)

        results.append({
            "video_path": video_path,
            "video_url": video_url,
            "prompt": prompt,
            "status": "succeeded"
        })

    return results
