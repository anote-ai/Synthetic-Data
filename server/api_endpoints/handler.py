from flask import jsonify
from database.db import store_generate_request
from generators.text import generate_text_data
from generators.image import generate_image_data
from generators.video import generate_video_data
from generators.audio import generate_audio_data
from generators.agent import generate_agent_data
from generators.PII import generate_pii_data
from validators import GenerateRequest

GENERATOR_MAP = {
    "text": generate_text_data,
    "image": generate_image_data,
    "video": generate_video_data,
    "audio": generate_audio_data,
    "agent": generate_agent_data,
    "pii": generate_pii_data,
}

def GenerateHandler(payload: GenerateRequest, user_email: str):
    try:
        store_generate_request(user_email, payload.task_type, payload.columns, payload.prompt, payload.num_rows)
    except Exception:
        pass  # DB logging failure should not block generation

    generator_fn = GENERATOR_MAP.get(payload.task_type)
    if not generator_fn:
        return jsonify({"error": f"Unsupported task_type: {payload.task_type}"}), 400

    try:
        generated = generator_fn(payload.prompt, payload.columns, payload.num_rows, payload.examples, payload.params)
    except Exception as e:
        return jsonify({"error": f"Generation failed: {str(e)}"}), 500

    return jsonify({"data": generated}), 200