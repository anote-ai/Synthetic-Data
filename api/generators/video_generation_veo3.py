import os
import json
import time
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

# 🔑 Authenticate with service account
creds = service_account.Credentials.from_service_account_file(
    "key.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
authed_session = AuthorizedSession(creds)

# 📍 Vertex AI config
PROJECT_ID = "infra-chimera-466009-p0"
LOCATION = "us-central1"
MODEL_ID = "veo-3.0-generate-preview"
ENDPOINT = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/{MODEL_ID}:predict"

# 🎥 Prompts to generate
prompts = [
    "A panda playing with snow in a bamboo forest",
    "A red sports car driving on a mountain road at sunset",
    "A futuristic city with flying cars and neon lights",
    "A lion walking through the savannah during golden hour"
]

# 📁 Output directories
os.makedirs("dataset/Video", exist_ok=True)
os.makedirs("dataset/labels", exist_ok=True)

# 🔁 Loop through prompts
for i, prompt in enumerate(prompts):
    print(f"\n🚀 Generating video for prompt {i+1}/{len(prompts)}: {prompt}")

    # Build request payload
    payload = {
        "instances": [
            {
                "prompt": prompt,
                "aspect_ratio": "16:9",
                "duration": "8s",
                "output_video_quality": "PREMIUM",
                "output_audio": "ENABLED"
            }
        ]
    }

    # 🔁 Send request
    response = authed_session.post(ENDPOINT, json=payload)
    if response.status_code != 200:
        print(f"❌ Failed for prompt '{prompt}': {response.text}")
        continue

    # Get polling operation URL
    result = response.json()
    operation_url = result["predictions"][0]["operation"]
    print(f"🔁 Polling: {operation_url}")

    # Poll until video is ready
    while True:
        operation_response = authed_session.get(operation_url).json()
        if operation_response.get("done"):
            break
        time.sleep(10)

    try:
        video_uri = operation_response["response"]["generatedVideos"][0]["video"]["uri"]
        print(f"✅ Video ready: {video_uri}")

        # Download video
        video_path = f"dataset/Video/video_{i}.mp4"
        label_path = f"dataset/labels/video_{i}.json"

        video_data = requests.get(video_uri)
        with open(video_path, "wb") as f:
            f.write(video_data.content)

        # Save label JSON
        with open(label_path, "w") as f:
            json.dump({"prompt": prompt, "video": video_path}, f, indent=2)

        print(f"🎬 Saved: {video_path} + label")

    except Exception as e:
        print(f"❌ Error extracting video: {str(e)}")
