import cv2
import json
import os

# Configurable paths
VIDEO_PATH = "sdk/examples/dataset/Video/video_0.mp4"
LABEL_PATH = "sdk/examples/dataset/Video/labels/video_0.json"
PROMPT = "a cat riding a skateboard"

# Global vars
annotations = []
current_frame_idx = 0
frame_annotations = []
drawing = False
bbox_start = (0, 0)
current_frame = None

def mouse_callback(event, x, y, flags, param):
    global drawing, bbox_start, frame_annotations, current_frame

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        bbox_start = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        bbox_end = (x, y)
        x1, y1 = bbox_start
        x2, y2 = bbox_end
        label = input(f"Enter label for object at {x1, y1, x2, y2}: ")
        frame_annotations.append({
            "label": label,
            "bbox": [min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)],
            "confidence": 1.0
        })
        cv2.rectangle(current_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

def label_video(video_path):
    global current_frame_idx, frame_annotations, current_frame

    cap = cv2.VideoCapture(video_path)
    cv2.namedWindow("Labeler")
    cv2.setMouseCallback("Labeler", mouse_callback)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_frame = frame.copy()
        frame_annotations = []

        while True:
            cv2.imshow("Labeler", current_frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("n"):  # Next frame
                if frame_annotations:
                    annotations.append({
                        "frame": current_frame_idx,
                        "objects": frame_annotations.copy()
                    })
                current_frame_idx += 1
                break
            elif key == ord("q"):  # Quit
                cap.release()
                cv2.destroyAllWindows()
                return

    cap.release()
    cv2.destroyAllWindows()

def save_annotations(prompt, video_path, label_path):
    label_data = {
        "prompt": prompt,
        "video_path": video_path,
        "annotations": annotations,
        "summary_labels": list({obj["label"] for frame in annotations for obj in frame["objects"]})
    }
    with open(label_path, "w") as f:
        json.dump(label_data, f, indent=2)
    print(f"✅ Labels saved to {label_path}")

if __name__ == "__main__":
    label_video(VIDEO_PATH)
    save_annotations(PROMPT, VIDEO_PATH, LABEL_PATH)
