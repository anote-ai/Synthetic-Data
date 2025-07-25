import openai
import json
import requests
import os
from ultralytics import YOLO

# configure openai
openai.api_key = "INSERT_YOUR_OPENAI_KEY"
print("Using API key:", openai.api_key[:10])
YOLO_MODEL_PATH = "yolo11n.pt"  # Or replace with your model path

# user prompt
user_prompt = input("Enter your synthetic dataset prompt: ")
labeled_path = input("Optional: Enter path to labeled data file (or press Enter to skip): ")

# load user labeled data 
if labeled_path.strip():
    if os.path.exists(labeled_path):
        with open(labeled_path, "r", encoding="utf-8") as f:
            labeled_data = f.read()
        print("Loaded labeled data sample:\n", labeled_data[:500])
    else:
        print(f"File '{labeled_path}' not found. Continuing without it.")

# generate image using OPENAI --> can be swapped out
try:
    prompt = f"High-quality illustration of a synthetic data task: {user_prompt}, use theme colors: #111827, #DEFE47, #28B2FB, white"
    response = openai.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )

    image_url = response.data[0].url
    print(f"Generated image URL: {image_url}")

    # Download the image
    img_data = requests.get(image_url).content
    img_path = "generated_image.png"
    with open(img_path, "wb") as f:
        f.write(img_data)
    print(f"Image saved to {img_path}")

    # Save metadata
    with open("image_output.json", "w", encoding="utf-8") as f:
        json.dump({"prompt": user_prompt, "image": image_url}, f, indent=2)

    # run yolov11 on object that is downloaded 
    print("Running YOLOv11 model for object detection...")
    model = YOLO(YOLO_MODEL_PATH)
    results = model(img_path)

    # Display results
    results[0].show()  # Opens window or saves image with annotations depending on env
    results[0].save(filename="detected_image.png")  # Save output image
    print("Detection results saved as detected_image.png")

    # Optional: print bounding box info
    print("Detected objects:", results[0].boxes.cls.tolist())

except Exception as e:
    print("Error:", str(e))
