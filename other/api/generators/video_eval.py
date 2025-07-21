import os
import nltk
nltk.download('punkt')
import json
import pandas as pd
import torch
import numpy as np
import pandas as pd
import cv2
from sklearn.metrics.pairwise import cosine_similarity
from transformers import CLIPProcessor, CLIPModel, BlipProcessor, BlipForConditionalGeneration
from moviepy.editor import VideoFileClip
from rouge_score import rouge_scorer
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from nltk.tokenize import word_tokenize

label_dir = "dataset/labels"
output_csv = "dataset/Video/video_index.csv"

rows = []

for fname in os.listdir(label_dir):
    if not fname.endswith(".json"):
        continue
    fpath = os.path.join(label_dir, fname)
    with open(fpath, "r") as jf:
        data = json.load(jf)
        rows.append({
            "video_id": fname.replace(".json", ""),
            "prompt": data["prompt"],
            "video_path": data["video"]
        })

df = pd.DataFrame(rows)
df.to_csv(output_csv, index=False)
print(f"✅ Saved index to {output_csv}")


device = "cuda" if torch.cuda.is_available() else "cpu"

# Load CLIP
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Load BLIP captioning
blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)

# Load dataset
df = pd.read_csv("dataset/video_index.csv")

# Utility: get frame at fraction of duration
def extract_frame(video_path, t_frac=0.5):
    clip = VideoFileClip(video_path)
    frame = clip.get_frame(clip.duration * t_frac)
    return frame

# Utility: convert frame to torch tensor
def preprocess_image(frame_np):
    frame_bgr = cv2.cvtColor(frame_np, cv2.COLOR_RGB2BGR)
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return frame_rgb

# CLIP score
def get_clip_score(prompt, frame):
    inputs = clip_processor(text=[prompt], images=[frame], return_tensors="pt").to(device)
    outputs = clip_model(**inputs)
    text_emb = outputs.text_embeds
    image_emb = outputs.image_embeds
    score = cosine_similarity(text_emb.cpu().detach(), image_emb.cpu().detach())[0][0]
    return score

# Caption
def generate_caption(frame):
    inputs = blip_processor(images=frame, return_tensors="pt").to(device)
    output = blip_model.generate(**inputs)
    caption = blip_processor.decode(output[0], skip_special_tokens=True)
    return caption

# Caption–prompt BLEU & ROUGE
def compute_text_similarity(prompt, caption):
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    rouge_l = scorer.score(prompt, caption)['rougeL'].fmeasure
    tokens_ref = [word_tokenize(prompt.lower())]
    tokens_hyp = word_tokenize(caption.lower())
    bleu = sentence_bleu(tokens_ref, tokens_hyp, smoothing_function=SmoothingFunction().method1)
    return bleu, rouge_l

# Motion score (L2 diff between start and mid frame)
def compute_motion(video_path):
    try:
        f1 = extract_frame(video_path, 0.1)
        f2 = extract_frame(video_path, 0.5)
        diff = np.linalg.norm(f1.astype(np.float32) - f2.astype(np.float32)) / f1.size
        return round(diff, 3)
    except Exception:
        return None

results = []

for _, row in df.iterrows():
    prompt = row["prompt"]
    video_path = row["video_path"]
    if not os.path.exists(video_path):
        continue

    try:
        frame = extract_frame(video_path, 0.5)
        frame_tensor = preprocess_image(frame)

        # CLIPScore
        clip_score = get_clip_score(prompt, frame_tensor)

        # Caption + BLEU/ROUGE
        caption = generate_caption(frame_tensor)
        bleu, rouge_l = compute_text_similarity(prompt, caption)

        # Motion score
        motion = compute_motion(video_path)

        results.append({
            "video_id": row["video_id"],
            "prompt": prompt,
            "clip_score": round(clip_score, 4),
            "generated_caption": caption,
            "bleu_score": round(bleu, 4),
            "rouge_l": round(rouge_l, 4),
            "motion_score": motion
        })

    except Exception as e:
        print(f"Error with {row['video_id']}: {e}")

# Save
out_df = pd.DataFrame(results)
out_df.to_csv("dataset/eval_generated_no_gt.csv", index=False)
print("✅ Saved results to dataset/eval_generated_no_gt.csv")
