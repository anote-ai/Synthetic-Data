import json
import time
from flask import jsonify
from database.db import store_generate_request
from generators.text import generate_text_data  # similar import for other modalities
from generators.image import generate_image_data  # similar import for other modalities
from generators.video import generate_video_data  # similar import for other modalities
from generators.Language import generate_language_data

GENERATOR_MAP = {
    "text": generate_text_data,
    "image": generate_image_data,
    "video": generate_video_data,
    "language": generate_language_data,
}


def GenerateHandler(request, user_email):
    data = request.json
    task_type = data.get("task_type")
    prompt = data.get("prompt")
    num_rows = data.get("num_rows", 10)
    columns = data.get("columns", [])
    examples = data.get("examples", [])
    params = data.get("params", {})

    store_generate_request(user_email, task_type, columns, prompt, num_rows)

    generator = GENERATOR_MAP.get(task_type)
    if generator is None:
        raise ValueError(f"Unsupported task_type: {task_type}")

    generated = generator(prompt, columns, num_rows, examples, params)

    return jsonify({"data": generated})


def generate_streaming(request, user_email):
    try:
        data = request.json
        task_type = data.get("task_type")
        prompt = data.get("prompt")
        num_rows = data.get("num_rows", 10)
        columns = data.get("columns", [])
        examples = data.get("examples", [])
        params = data.get("params", {})

        store_generate_request(user_email, task_type, columns, prompt, num_rows)

        generator = GENERATOR_MAP.get(task_type)
        if generator is None:
            raise ValueError(f"Unsupported task_type: {task_type}")

        generated = generator(prompt, columns, num_rows, examples, params)

        for index, row in enumerate(generated):
            event = json.dumps({"type": "progress", "row": index, "total": num_rows, "data": row})
            yield f"data: {event}\n\n"
            time.sleep(0.05)

        done_event = json.dumps({"type": "done", "total_rows": num_rows})
        yield f"data: {done_event}\n\n"

    except Exception as e:
        error_event = json.dumps({"type": "error", "message": str(e)})
        yield f"data: {error_event}\n\n"
