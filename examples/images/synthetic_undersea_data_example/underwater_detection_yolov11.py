import os, random, cv2, json, gc
from PIL import Image
from diffusers import StableDiffusionPipeline
from ultralytics import YOLO  # Assuming YOLOv11 behaves like YOLOv8
import torch

CLASSES = ["Fish", "Jellyfish", "Penguin", "Puffin", "Shark", "Starfish", "Stingray", "Turtle", "Shrimp"]
OUTPUT_DIR = "synthetic_undersea_data_example"
os.makedirs(f"{OUTPUT_DIR}/images", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/annotations", exist_ok=True)

pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5").to("cpu")
yolo_model = YOLO("yolov11.pt")  # Replace with correct path or model name

def generate_image_with_prompt(class_name, idx):
    prompt = f"underwater photo of a {class_name}, clear visibility, blue ocean background, some noise"
    image = pipe(prompt, num_inference_steps=15).images[0]
    image_path = f"{OUTPUT_DIR}/images/{class_name}_{idx}.jpg"
    image.save(image_path)
    return image_path

def detect_bbox_yolo(image_path, target_class):
    results = yolo_model(image_path)[0]
    bboxes = []
    for box in results.boxes:
        class_id = int(box.cls)
        if class_id == CLASSES.index(target_class):  # Match generated class
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            bboxes.append([x1, y1, x2, y2])
    return bboxes

def create_annotation(image_path, class_name, bbox, image_id):
    return {
        "image": os.path.basename(image_path),
        "bbox": bbox,
        "class": class_name,
        "class_id": CLASSES.index(class_name),
        "image_id": image_id
    }

annotations = []
for i in range(100):  # Adjust for larger dataset
    cls = random.choice(CLASSES)
    img_path = generate_image_with_prompt(cls, i)
    bboxes = detect_bbox_yolo(img_path, cls)
    for bbox in bboxes:
        ann = create_annotation(img_path, cls, bbox, i)
        annotations.append(ann)
    gc.collect()

with open(f"{OUTPUT_DIR}/annotations/annotations.json", "w") as f:
    json.dump(annotations, f, indent=2)
