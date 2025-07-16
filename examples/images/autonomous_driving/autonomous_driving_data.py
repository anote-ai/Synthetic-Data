import torch
from diffusers import StableDiffusionPipeline
from ultralytics import YOLO

import os
import json
import random
import gc
from PIL import Image
from diffusers import StableDiffusionPipeline
from ultralytics import YOLO

ROAD_CLASSES = ["Car", "Truck", "Person", "Deer", "Rabbit", "Duck"]
ROAD_OUTPUT_DIR = "synthetic_road_scenarios"
os.makedirs(f"{ROAD_OUTPUT_DIR}/images", exist_ok=True)
os.makedirs(f"{ROAD_OUTPUT_DIR}/annotations", exist_ok=True)

pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5").to("cpu")
yolo_model = YOLO("yolov8n.pt")  # or yolov8s.pt, yolov8m.pt, yolov8x.pt depending on size
#will be able to use yolov11 once it is trained, for now, must be yollov8

#need to define detect yolo bounding boxes first
def detect_bbox_yolo(image_path, target_class):
    results = yolo_model(image_path)  # Run YOLO on the image
    detections = results[0].boxes
    bboxes = []

    for box in detections:
        cls_id = int(box.cls[0].item())
        class_name = yolo_model.names[cls_id]
        if class_name.lower() == target_class.lower():
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bbox = [x1, y1, x2 - x1, y2 - y1]  # [x, y, width, height]
            bboxes.append(bbox)

    return bboxes


def generate_road_prompt(cls):
    conditions = [
        "sunny morning", "foggy afternoon", "nighttime with headlights",
        "rainy road", "snow-covered road", "clear highway"
    ]
    traffic = [
        "light traffic", "heavy traffic", "empty road"
    ]
    actions = {
        "Car": ["a car driving towards the camera", "a car passing by"],
        "Truck": ["a large truck approaching", "a delivery truck on the side"],
        "Person": ["a person crossing the road", "a group walking on crosswalk"],
        "Deer": ["a deer crossing in front"], "Rabbit": ["a rabbit near the roadside"],
        "Duck": ["a duck waddling across the road"]
    }
    return f"realistic photo of a road during {random.choice(conditions)}, {random.choice(traffic)}, {random.choice(actions[cls])}"

road_annotations = []
for i in range(10): #reduced to generate quickly, can change to increase the number of images and bounding boxes outputted 
    cls = random.choice(ROAD_CLASSES)
    prompt = generate_road_prompt(cls)
    image = pipe(prompt, num_inference_steps=15).images[0]
    img_path = f"{ROAD_OUTPUT_DIR}/images/{cls}_{i}.jpg"
    image.save(img_path)
    print(f"Saved image successfuly to location: {img_path}")

    bboxes = detect_bbox_yolo(img_path, cls)  # using same YOLO detection
    for bbox in bboxes:
        road_annotations.append({
            "image": os.path.basename(img_path),
            "bbox": bbox,
            "class": cls,
            "class_id": ROAD_CLASSES.index(cls),
            "image_id": i
        })

    if i % 100 == 0:  # memory management
        gc.collect()

with open(f"{ROAD_OUTPUT_DIR}/annotations.json", "w") as f:
    json.dump(road_annotations, f, indent=2)


