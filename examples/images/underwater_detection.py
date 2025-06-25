import os
import random
import cv2
import json
from PIL import Image
import numpy as np
from diffusers import StableDiffusionPipeline #using stable diffusion pipeline
from torchvision.ops import box_convert

#root directory to dataset
CLASSES = ["Fish", "Jellyfish", "Penguin", "Puffin", "Shark", "Starfish", "Stingray", "Turtle", "Shrimp"]
OUTPUT_DIR = "synthetic_undersea_data_example" 

# generate subfolders for outputs and annotations
os.makedirs(f"{OUTPUT_DIR}/images", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/annotations", exist_ok=True)

# loading from Stable Diffusion v1.5 model from HuggingFace **
pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5").to("cpu")


def generate_image_with_prompt(class_name, idx):
    prompt = f"underwater photo of a {class_name}, clear visibility, blue ocean background, some noise"
    image = pipe(prompt, num_inference_steps=30).images[0]
    image_path = f"{OUTPUT_DIR}/images/{class_name}_{idx}.jpg"
    image.save(image_path)
    return image_path, image

def generate_random_bbox(img_width, img_height):
    w, h = random.randint(80, 150), random.randint(80, 150)
    x1, y1 = random.randint(0, img_width - w), random.randint(0, img_height - h)
    x2, y2 = x1 + w, y1 + h
    return [x1, y1, x2, y2]

def create_annotation(image_path, class_name, bbox, image_id):
    annotation = {
        "image": os.path.basename(image_path),
        "bbox": bbox,  # [x_min, y_min, x_max, y_max]
        "class": class_name,
        "class_id": CLASSES.index(class_name),
        "image_id": image_id
    }
    return annotation

annotations = []
for i in range(100):  # Generate 100 synthetic images
    cls = random.choice(CLASSES)
    img_path, img = generate_image_with_prompt(cls, i)
    bbox = generate_random_bbox(img.width, img.height)
    ann = create_annotation(img_path, cls, bbox, i)
    annotations.append(ann)

with open(f"{OUTPUT_DIR}/annotations/annotations.json", "w") as f:
    json.dump(annotations, f, indent=2)
