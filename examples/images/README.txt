readme = f"""
# Synthetic Undersea Object Detection Dataset

This dataset contains 100 synthetically generated underwater images with bounding box annotations for 7 marine classes:
Fish, Jellyfish, Penguin, Puffin, Shark, Starfish, and Stingray.

## Contents
- /images: 100 high-quality images generated using Stable Diffusion
- /annotations: COCO-style JSON file with bounding boxes and class labels

## How It Was Generated
Images were generated using Stable Diffusion with class-specific prompts.
Bounding boxes were randomly sampled and associated with the correct class.

## Classes
{', '.join(CLASSES)}

## Format
Each annotation contains:
- image: filename
- bbox: [x_min, y_min, x_max, y_max]
- class: class name
- class_id: integer label
- image_id: unique image identifier

## License
MIT License
"""

with open(f"{OUTPUT_DIR}/README.md", "w") as f:
    f.write(readme)
