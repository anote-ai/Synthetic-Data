import os
import json
import time
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Setup
load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

os.makedirs("dataset/Video", exist_ok=True)
os.makedirs("dataset/labels", exist_ok=True)

# List of prompts for training data
prompts = [
    "A panda playing with snow in a bamboo forest",
    "A red sports car driving on a mountain road at sunset",
    "A futuristic city with flying cars and neon lights",
    "A lion walking through the savannah during golden hour"
]

# Loop through prompts to generate video training pairs
for i, prompt in enumerate(prompts):
    print(f"🚀 Generating video for: {prompt}")
    operation = client.models.generate_videos(
        model="veo-2.0-generate-001",
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            person_generation="dont_allow",
            number_of_videos=1,
            duration_seconds=5,
            enhance_prompt=True
        ),
    )

    # Poll
    while True:
        op_status = client.operations.get(operation)
        if op_status.done:
            break
        time.sleep(15)

    if op_status.error:
        print(f"⚠️ Failed: {op_status.error['message']}")
        continue

    # Save video and label
    for idx, video_obj in enumerate(op_status.response.generated_videos):
        video_url = video_obj.video.uri
        video_path = f"dataset/Video/video_{i}_{idx}.mp4"
        label_path = f"dataset/Video/labels/video_{i}_{idx}.json"

        response = requests.get(video_url)
        with open(video_path, "wb") as f:
            f.write(response.content)

        with open(label_path, "w") as f:
            json.dump({"prompt": prompt, "video": video_path}, f, indent=2)

        print(f"✅ Saved: {video_path} with label")
