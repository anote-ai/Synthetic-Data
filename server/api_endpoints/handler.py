import json
import time
from flask import jsonify
from database.db import store_generate_request
from generators.text import generate_text_data  # similar import for other modalities
from generators.image import generate_image_data  # similar import for other modalities
from generators.video import generate_video_data  # similar import for other modalities
from utils.quality import score_dataset


def GenerateHandler(request, user_email):
    data = request.json
    task_type = data.get("task_type")
    prompt = data.get("prompt")
    num_rows = data.get("num_rows", 10)
    columns = data.get("columns", [])
    examples = data.get("examples", [])
    auto_score = data.get("auto_score", False)

    store_generate_request(user_email, task_type, columns, prompt, num_rows)

    if task_type == "text":
        generated = generate_text_data(prompt, columns, num_rows, examples)

    elif task_type == "image":
        generated = generate_image_data(prompt, columns, num_rows, examples)

    elif task_type == "video":
        generated = generate_video_data(prompt, columns, num_rows, examples)
    else:
        raise ValueError(f"Unsupported task_type: {task_type}")

    response = {"data": generated}

    if auto_score:
        response["quality"] = score_dataset(generated, prompt or "")

    return jsonify(response)


def generate_streaming(request, user_email):
    try:
        data = request.json
        task_type = data.get("task_type")
        prompt = data.get("prompt")
        num_rows = data.get("num_rows", 10)
        columns = data.get("columns", [])
        examples = data.get("examples", [])

        store_generate_request(user_email, task_type, columns, prompt, num_rows)

        if task_type == "text":
            generated = generate_text_data(prompt, columns, num_rows, examples)
        elif task_type == "image":
            generated = generate_image_data(prompt, columns, num_rows, examples)
        elif task_type == "video":
            generated = generate_video_data(prompt, columns, num_rows, examples)
        else:
            raise ValueError(f"Unsupported task_type: {task_type}")

        for index, row in enumerate(generated):
            event = json.dumps({"type": "progress", "row": index, "total": num_rows, "data": row})
            yield f"data: {event}\n\n"
            time.sleep(0.05)

        done_event = json.dumps({"type": "done", "total_rows": num_rows})
        yield f"data: {done_event}\n\n"

    except Exception as e:
        error_event = json.dumps({"type": "error", "message": str(e)})
        yield f"data: {error_event}\n\n"
