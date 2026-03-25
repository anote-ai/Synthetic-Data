import os
import time
import json
import requests
import cv2

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_API_TOKEN:
    raise RuntimeError("REPLICATE_API_TOKEN environment variable is not set")

MODEL_VERSION = "8ba52bde11300615f65e9591d7afc58816def12c93c870fa583ff67ae17afdda"

BASE_VIDEO_DIR = os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs") + "/video"
BASE_LABEL_DIR = BASE_VIDEO_DIR + "/labels"
os.makedirs(BASE_VIDEO_DIR, exist_ok=True)
os.makedirs(BASE_LABEL_DIR, exist_ok=True)

def generate_video_data(prompt: str, columns: list, num_rows: int = 1, examples: list = []) -> list:
    results = []

    for i in range(num_rows):
        try:
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
                raise Exception(f"Failed to initiate generation: {response.text}")

            prediction = response.json()
            poll_url = prediction["urls"]["get"]
            status = prediction["status"]

            print(f"⏳ [{i+1}/{num_rows}] Generating video...")

            while status not in ["succeeded", "failed", "canceled"]:
                time.sleep(10)
                prediction = requests.get(poll_url, headers=headers).json()
                status = prediction["status"]

            if status != "succeeded":
                raise Exception("Video generation failed")

            video_url = prediction["output"]
            video_path = os.path.join(BASE_VIDEO_DIR, f"video_{i}.mp4")
            label_path = os.path.join(BASE_LABEL_DIR, f"video_{i}.json")

            video_data = requests.get(video_url)
            with open(video_path, "wb") as f:
                f.write(video_data.content)

            # Save initial label JSON
            with open(label_path, "w") as f:
                json.dump({
                    "prompt": prompt,
                    "video_path": video_path,
                    "annotations": [],
                    "summary_labels": []
                }, f, indent=2)

            results.append({
                "video_path": video_path,
                "video_url": video_url,
                "label_path": label_path,
                "prompt": prompt,
                "columns": columns,
                "status": "succeeded"
            })

        except Exception as e:
            results.append({
                "status": "failed",
                "error": str(e),
                "prompt": prompt
            })

    return results

# --- Labeling UI ---
def annotate_video(video_path, label_path):
    annotations = []
    frame_index = 0

    def click_event(event, x, y, flags, param):
        nonlocal frame_index
        if event == cv2.EVENT_LBUTTONDOWN:
            label = input(f"Label for object at (x={x}, y={y}) on frame {frame_index}: ")
            annotations.append({
                "frame": frame_index,
                "x": x,
                "y": y,
                "label": label
            })
            print(f"✅ Saved annotation at frame {frame_index}: ({x}, {y}) -> {label}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("❌ Failed to open video.")
        return

    cv2.namedWindow("Video Labeler")
    cv2.setMouseCallback("Video Labeler", click_event)

    print("ℹ️ Press 'q' to quit. Left-click to label.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("✅ End of video.")
            break

        cv2.imshow("Video Labeler", frame)
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            print("👋 Exiting video labeler.")
            break

        frame_index += 1

    cap.release()
    cv2.destroyAllWindows()

    with open(label_path, "r") as f:
        data = json.load(f)
    data["annotations"] = annotations

    with open(label_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Saved {len(annotations)} annotations to {label_path}")

# --- Run Everything ---
if __name__ == "__main__":
    prompt = "a cat riding a skateboard"
    columns = ["video_path", "prompt", "annotations"]

    results = generate_video_data(prompt=prompt, columns=columns, num_rows=1)

    for result in results:
        if result["status"] == "succeeded":
            video_path = result["video_path"]
            label_path = result["label_path"]
            annotate_video(video_path, label_path)
        else:
            print(f"⚠️ Skipping video due to failure: {result.get('error')}")

