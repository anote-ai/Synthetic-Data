from flask import jsonify
from database.db import store_generate_request
from generators.text import generate_text_data  # similar import for other modalities
from generators.image import generate_image_data  # similar import for other modalities
from generators.video import generate_video_data  # similar import for other modalities

def GenerateHandler(request, user_email):
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

    return jsonify({"data": generated})