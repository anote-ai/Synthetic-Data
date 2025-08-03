import cv2
import json
import os

video_path = "server/sdk/examples/dataset/Video/video_0.mp4"
output_json = "server/sdk/examples/dataset/Video/labels/video_0.json"

annotations = []
frame_index = 0
clicked_points = []

# --- Mouse Callback Function ---
def click_event(event, x, y, flags, param):
    global frame_index
    if event == cv2.EVENT_LBUTTONDOWN:
        label = input(f"Label for object at (x={x}, y={y}) on frame {frame_index}: ")
        annotations.append({
            "frame": frame_index,
            "x": x,
            "y": y,
            "label": label
        })
        print(f"✅ Saved annotation at frame {frame_index}: ({x}, {y}) -> {label}")

# --- Load Video ---
cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print("❌ Failed to open video.")
    exit(1)

cv2.namedWindow("Video Labeler")
cv2.setMouseCallback("Video Labeler", click_event)

print("ℹ️ Press 'q' to quit. Left-click on the video to label objects.")

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

# --- Save JSON ---
os.makedirs(os.path.dirname(output_json), exist_ok=True)
with open(output_json, "w") as f:
    json.dump({
        "video_path": video_path,
        "annotations": annotations
    }, f, indent=2)

print(f"✅ Saved {len(annotations)} annotations to {output_json}")
