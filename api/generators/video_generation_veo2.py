import os
import time
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("Missing GOOGLE_API_KEY environment variable.")

# Initialize Gemini client
client = genai.Client(api_key=api_key)

# Start the video generation operation
operation = client.models.generate_videos(
    model="veo-2.0-generate-001",
    prompt="Cinematic aerial shot of a red sailboat on a turquoise ocean, golden sunset, gentle waves",
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        person_generation="dont_allow",
        number_of_videos=1,
        duration_seconds=5,
        enhance_prompt=True
    ),
)

# Poll the operation until it completes
print("⏳ Waiting for video generation to complete...")
while True:
    op_status = client.operations.get(operation)
    if op_status.done:
        break
    time.sleep(15)

# Check for errors
if op_status.error:
    raise RuntimeError(f"Video generation failed: {op_status.error['message']}")

# Download the video using requests
for idx, video_obj in enumerate(op_status.response.generated_videos):
    video_url = video_obj.video.uri  # The video URI is a public URL
    print(f"🎬 Downloading video from: {video_url}")
    response = requests.get(video_url)
    output_path = f"video_{idx}.mp4"
    with open(output_path, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved: {output_path}")
