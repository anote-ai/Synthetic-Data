# 🚗 Synthetic Autonomous Driving Dataset Generator

This project generates a large-scale, diverse synthetic image dataset for autonomous driving using [Stable Diffusion v1.5](https://huggingface.co/runwayml/stable-diffusion-v1-5) and object detection via YOLOv11. Each image contains a realistic road scene with annotated objects such as vehicles, pedestrians, and animals under varied weather, lighting, and traffic conditions.

---

features 
- **Image Generation:** Uses Stable Diffusion to generate realistic driving scenes
- **Annotation:** Uses YOLOv11 to automatically generate bounding boxes
- **Classes Supported:** Car, Truck, Person, Deer, Rabbit, Duck
- **Scene Variations:** Includes different lighting, weather, and traffic conditions
- **Scalable:** Generates up to 10,000 labeled images

## 🛠️ Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/synthetic-driving-gen.git
   cd synthetic-driving-gen

2. install dependencies 
   ```bash  
   pip install -r requirements.txt

3. Download YOLOv11 weights
   ```bash  
   yolo task=detect mode=train model=yolov11.pt
   #if using ultralytics yolo

4. run 
   ```bash  
   python autonomous_driving_data.py






