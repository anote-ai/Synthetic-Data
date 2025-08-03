import os
import torch
from faster_whisper import WhisperModel

os.makedirs("dataset/Audio", exist_ok=True)
os.makedirs("dataset/labels", exist_ok=True)

def load_model(model_size="large-v3", device=None):
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    compute_type = "float16" if device == "cuda" else "int8"
    
    return WhisperModel(model_size, device=device, compute_type=compute_type)

def analyze_audio(audio_path):
    print(f"\nAnalyzing: {audio_path}")
    segments, info = model.transcribe(audio_path, beam_size=5)
    segments = list(segments)
    
    results = {
        "transcription": " ".join([seg.text for seg in segments]),
        "segments": [{"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments],
        "language": info.language,
    }

    return results

def generate_audio_data(prompt: str, columns: list, num_rows: int = 1, examples: list = []) -> list:
    results = []

    for i in range(num_rows):
        try:
            example = examples[i % len(examples)] if examples else None
            if not example or "audio_path" not in example:
                raise ValueError("Missing or invalid example with 'audio_path'.")

            src_audio_path = example["audio_path"]
            dst_audio_path = f"dataset/Audio/sample_{i}.wav"
            os.system(f"cp '{src_audio_path}' '{dst_audio_path}'")

            analysis = analyze_audio(dst_audio_path)

            results.append({
                "audio_path": dst_audio_path,
                "prompt": prompt,
                "analysis": analysis,
                "status": "succeeded"
            })

        except Exception as e:
            results.append({
                "status": "failed",
                "error": str(e)
            })

    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run audio analysis on a .wav file.")
    parser.add_argument("audio_path", type=str, help="Path to the .wav file to analyze")
    args = parser.parse_args()

    if not os.path.isfile(args.audio_path):
        raise FileNotFoundError(f"File not found: {args.audio_path}")

    result = analyze_audio(args.audio_path)

    print("\n--- TRANSCRIPTION ---")
    print(result["transcription"])

    print("\n--- SEGMENTS ---")
    for seg in result["segments"]:
        print(f"[{seg['start']}s - {seg['end']}s]: {seg['text']}")

    print("\n--- LANGUAGE DETECTED ---")
    print(result["language"])
