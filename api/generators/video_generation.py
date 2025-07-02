import requests
import json
import time
import os
import sys
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
    data = resp.json()

    # Try getting video from future_links immediately
    if "future_links" in data and data["future_links"]:
        data["early_video_url"] = data["future_links"][0]

    return data

def poll_and_download(fetch_url: str, wait_seconds: int = 5, max_tries: int = 60):
    spinner = ['|', '/', '-', '\\']
    print("Waiting for video to be ready...", end="", flush=True)

    for attempt in range(max_tries):
        time.sleep(wait_seconds)
        sys.stdout.write(f"\rWaiting for video to be ready... {spinner[attempt % len(spinner)]}")
        sys.stdout.flush()

        try:
            resp = requests.get(fetch_url)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "succeeded" and data.get("output"):
                print("\n✅ Video is ready!")
                return data["output"][0]
            elif data.get("status") == "failed":
                print("\n❌ Video generation failed.")
                raise RuntimeError(data.get("error"))

        except Exception as e:
            if attempt % 10 == 0:
                print(f"\nError on attempt {attempt + 1}: {e}")

    print("\n⏳ Timed out while waiting for the video.")
    raise TimeoutError("Video not ready after max polling attempts.")

def main():
    prompt = input("Enter video prompt: ")
    print("Submitting request...")
    job = generate_video(prompt, height=512, width=512, num_frames=16)

    # Check for early video link (preferred)
    early_video_url = job.get("early_video_url")
    if early_video_url:
        print("🎉 Early video URL found via future_links:", early_video_url)
        video_url = early_video_url
        fetch_url = job.get("fetch_result", "N/A")
    else:
        fetch_url = job.get("fetch_result")
        if not fetch_url:
            print("No fetch_result found in response. Exiting.")
            print("Full response:", job)
            return

        print(f"Polling for video result from: {fetch_url}")
        try:
            video_url = poll_and_download(fetch_url)
        except TimeoutError as e:
            print("Timed out while waiting for video:", str(e))
            return

    print(f"Generated video URL: {video_url}")

    # Download the video
    try:
        video_data = requests.get(video_url).content
        out_path = "generated_video.mp4"
        with open(out_path, "wb") as f:
            f.write(video_data)
        print(f"✅ Saved video to {out_path}")
    except Exception as e:
        print("❌ Failed to download video:", str(e))
        return

    # Save metadata
    meta = {
        "prompt": prompt,
        "video_url": video_url,
        "fetch_result": fetch_url
    }
    with open("video_output.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("📝 Saved metadata to video_output.json")

if __name__ == "__main__":
    main()
