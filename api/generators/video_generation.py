import requests
import json
import time
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

API_KEY = os.getenv("MODELSLAB_API_KEY")
if not API_KEY:
    raise ValueError("API key not found. Set MODELSLAB_API_KEY in your .env file")

API_URL = "https://modelslab.com/api/v6/video/text2video"

def generate_video(prompt: str, **kwargs):
    payload = {
        "key": API_KEY,
        "model_id": "cogvideox",
        "prompt": prompt,
        "negative_prompt": kwargs.get("negative_prompt", ""),
        "height": kwargs.get("height", 512),
        "width": kwargs.get("width", 512),
        "num_frames": kwargs.get("num_frames", 24),
        "num_inference_steps": kwargs.get("num_inference_steps", 20),
        "guidance_scale": kwargs.get("guidance_scale", 7),
        "output_type": kwargs.get("output_type", "mp4"),
        "instant_response": False
    }
    resp = requests.post(API_URL, json=payload)
    resp.raise_for_status()
    return resp.json()

def poll_and_download(track_id: str):
    status_url = f"{API_URL}/{track_id}"
    while True:
        time.sleep(5)
        resp = requests.get(status_url)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        print(f"[{track_id}] status: {status}")
        if status == "succeeded":
            return data["output_url"]
        elif status == "failed":
            raise RuntimeError(f"Video generation failed: {data.get('error')}")

def main():
    prompt = input("Enter video prompt: ")
    print("Submitting request...")
    job = generate_video(prompt, height=512, width=512, num_frames=16)
    track_id = job.get("track_id")
    if not track_id:
        print("Response:", job)
        return

    print(f"Track ID: {track_id}, polling for results...")
    video_url = poll_and_download(track_id)
    print("Generated video URL:", video_url)

    # Download the video
    video_data = requests.get(video_url).content
    out_path = "generated_video.mp4"
    with open(out_path, "wb") as f:
        f.write(video_data)
    print(f"Saved video to {out_path}")

    # Save metadata
    meta = {
        "prompt": prompt,
        "video_url": video_url,
        "track_id": track_id
    }
    with open("video_output.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Saved metadata to video_output.json")

if __name__ == "__main__":
    main()
