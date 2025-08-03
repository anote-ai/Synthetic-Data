import os
import time
import json
import requests

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
MODEL_VERSION = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"

# Updated base path
BASE_VIDEO_DIR = "sdk/examples/dataset/Video"
BASE_LABEL_DIR = "sdk/examples/dataset/Video/labels"

# Ensure directories exist
os.makedirs(BASE_VIDEO_DIR, exist_ok=True)
os.makedirs(BASE_LABEL_DIR, exist_ok=True)

def generate_video_data(prompt: str, num_rows: int = 1, examples: list = []) -> list:
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
        video_path = os.path.join(BASE_VIDEO_DIR, f"video_{i}.mp4")
        label_path = os.path.join(BASE_LABEL_DIR, f"video_{i}.json")

        video_data = requests.get(video_url)
        with open(video_path, "wb") as f:
            f.write(video_data.content)

        # Save metadata
        with open(label_path, "w") as f:
            json.dump({"prompt": prompt, "video": video_path}, f, indent=2)

        results.append({
            "video_path": video_path,
            "video_url": video_url,
            "prompt": prompt,
            "status": "succeeded"
        })

    return results

