# Synthetic Road Scene Dataset Generator

## Overview

This project generates a synthetic dataset of annotated road scene images using:
- **Stable Diffusion v1.5** (`runwayml/stable-diffusion-v1-5`) for image generation.
- **YOLOv8** (`yolov8n.pt`) for object detection and bounding box annotation.

The goal is to simulate varied real-world traffic conditions for training or benchmarking object detection models.

## Object Classes

- Car
- Truck
- Person
- Deer
- Rabbit
- Duck

## Pipeline Steps

1. Randomly select a class.
2. Generate a detailed natural language prompt with road, weather, and traffic conditions.
3. Generate an image using Stable Diffusion.
4. Save the image to `synthetic_road_scenarios/images/`.
5. Use YOLOv8 to detect objects and extract bounding boxes for the target class.
6. Save annotations in `synthetic_road_scenarios/annotations.json`.

## Example Annotation Format

```json
{
  "image": "Car_2.jpg",
  "bbox": [x, y, width, height],
  "class": "Car",
  "class_id": 0,
  "image_id": 2
}
