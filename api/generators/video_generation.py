import os
import time
import json
import requests

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN") or "r8_TmFVTZiq3U6NgMonmd5eza9YYEdX7YC0FZh8i"
MODEL_VERSION = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"

# Ensure output directories exist
os.makedirs("dataset/Video", exist_ok=True)
os.makedirs("dataset/labels", exist_ok=True)

def video_generator(prompt: str, index: int = 0) -> dict:
    """
    Generate a video using the given prompt with Replicate's API.
    
    Args:
        prompt (str): The input prompt describing the video scene.
        index (int): Optional index used for file naming.
        
    Returns:
        dict: {
            'status': 'succeeded' | 'failed',
            'prompt': str,
            'video_path': str (if succeeded),
            'video_url': str (if succeeded),
            'error': str (if failed)
        }
    """

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

    print(f"\n🚀 Generating video for: {prompt}")
    response = requests.post("https://api.replicate.com/v1/predictions", headers=headers, data=json.dumps(data))

    if response.status_code != 201:
        error_msg = f"Failed to create prediction: {response.text}"
        print(f"❌ {error_msg}")
        return {"status": "failed", "prompt": prompt, "error": error_msg}

    prediction = response.json()
    prediction_id = prediction["id"]
    poll_url = prediction["urls"]["get"]
    status = prediction["status"]

    print(f"🔁 Prediction ID: {prediction_id}")

    while status not in ["succeeded", "failed", "canceled"]:
        time.sleep(10)
        poll_response = requests.get(poll_url, headers=headers)
        prediction = poll_response.json()
        status = prediction["status"]
        print(f"⏳ Status: {status}")

    if status != "succeeded":
        error_msg = f"Generation failed for: {prompt}"
        print(f"❌ {error_msg}")
        return {"status": "failed", "prompt": prompt, "error": error_msg}

    video_url = prediction["output"]
    video_path = f"dataset/Video/video_{index}.mp4"
    label_path = f"dataset/labels/video_{index}.json"

    video_data = requests.get(video_url)
    with open(video_path, "wb") as f:
        f.write(video_data.content)

    with open(label_path, "w") as f:
        json.dump({"prompt": prompt, "video": video_path}, f, indent=2)

    print(f"✅ Saved: {video_path}")
    return {
        "status": "succeeded",
        "prompt": prompt,
        "video_url": video_url,
        "video_path": video_path
    }

