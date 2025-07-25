import os
import time
import json
import requests
import re

# 🔑 API Token & Model
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN") or "r8_TmFVTZiq3U6NgMonmd5eza9YYEdX7YC0FZh8i"
MODEL_VERSION = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"

# 📁 Ensure output directories exist
os.makedirs("dataset/Video", exist_ok=True)
os.makedirs("dataset/labels", exist_ok=True)

# 🎬 Video Generator Function
def video_generator(prompt: str, index: str = "0") -> dict:
    """
    Generate a video using the given prompt with Replicate's API.
    Saves the video and metadata locally.
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
    poll_url = prediction["urls"]["get"]
    status = prediction["status"]

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
    safe_index = re.sub(r"[^\w\-]", "_", str(index))  # sanitize index for filenames
    video_path = f"dataset/Video/video_{safe_index}.mp4"
    label_path = f"dataset/labels/video_{safe_index}.json"

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

# 📚 Prompt Categories
education_prompts = [
    "A student typing on a laptop",
    "A child using a tablet",
    "A teacher writing on a board",
    "A student wearing VR goggles",
    "A computer screen showing code"
]

ecommerce_prompts = [
    "A woman looking in a mirror",
    "A robot arm picking up a box",
    "A person using a touchscreen",
    "A drone flying above a house",
    "A clothing store mirror display"
]

healthcare_prompts = [
    "A robot arm in a hospital room",
    "A person jogging with a smartwatch",
    "A doctor looking at a monitor",
    "A nurse standing next to a bed",
    "A robot at a reception desk"
]

robotics_prompts = [
    "A robot vacuum on the floor",
    "A robot arm moving parts",
    "A robot dog walking indoors",
    "A robot hand pressing a button",
    "A delivery robot on a sidewalk"
]

# 🧠 Combine all prompts with category-index tags
all_prompts = (
    [(p, f"education_{i}") for i, p in enumerate(education_prompts)] +
    [(p, f"ecommerce_{i}") for i, p in enumerate(ecommerce_prompts)] +
    [(p, f"healthcare_{i}") for i, p in enumerate(healthcare_prompts)] +
    [(p, f"robotics_{i}") for i, p in enumerate(robotics_prompts)]
)

# 🔁 Generate videos for all prompts
if __name__ == "__main__":
    for prompt, tag in all_prompts:
        print(f"\n=== Generating: {tag} ===")
        result = video_generator(prompt, index=tag)
        print(result)



