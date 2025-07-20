import os
import time
import json
import requests

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN") or "r8_TmFVTZiq3U6NgMonmd5eza9YYEdX7YC0FZh8i"

# 📥 Prompt list
prompts = [
    "A panda playing with snow in a bamboo forest",
    "A red sports car driving on a mountain road at sunset",
    "A futuristic city with flying cars and neon lights",
    "A lion walking through the savannah during golden hour"
]

# 📁 Save location
os.makedirs("dataset/Video", exist_ok=True)
os.makedirs("dataset/labels", exist_ok=True)

# 🧠 Model version (ZeroScope v2 576x320)
model_version = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"

headers = {
    "Authorization": f"Token {REPLICATE_API_TOKEN}",
    "Content-Type": "application/json",
}

for i, prompt in enumerate(prompts):
    print(f"\n🚀 Generating video for: {prompt}")

    # Step 1: Create prediction
    data = {
        "version": model_version,
        "input": {
            "prompt": prompt,
            "num_frames": 24,
            "fps": 6,
            "width": 576,
            "height": 320
        }
    }

    response = requests.post(
        "https://api.replicate.com/v1/predictions",
        headers=headers,
        data=json.dumps(data)
    )

    if response.status_code != 201:
        print(f"❌ Failed to create prediction: {response.text}")
        continue

    prediction = response.json()
    prediction_id = prediction["id"]
    status = prediction["status"]
    print(f"🔁 Prediction ID: {prediction_id} — status: {status}")

    # Step 2: Poll until complete
    poll_url = prediction["urls"]["get"]

    while status not in ["succeeded", "failed", "canceled"]:
        time.sleep(10)
        poll_response = requests.get(poll_url, headers=headers)
        prediction = poll_response.json()
        status = prediction["status"]
        print(f"⏳ Status: {status}")

    if status != "succeeded":
        print(f"❌ Generation failed for: {prompt}")
        continue

    video_url = prediction["output"]
    video_path = f"dataset/Video/video_{i}.mp4"
    label_path = f"dataset/labels/video_{i}.json"

    # Step 3: Download video
    video_data = requests.get(video_url)
    with open(video_path, "wb") as f:
        f.write(video_data.content)

    # Save metadata
    with open(label_path, "w") as f:
        json.dump({"prompt": prompt, "video": video_path}, f, indent=2)

    print(f"✅ Saved: {video_path} and metadata")
