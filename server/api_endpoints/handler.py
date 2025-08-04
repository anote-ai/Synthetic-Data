import os
import json
import uuid
from flask import jsonify
from database.db import store_generate_request
from generators.PII import generate_PII_data_sync
from generators.text import generate_text_data
from generators.image import generate_image_data
from generators.video import generate_video_data

OUTPUT_DIR = "output_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def GenerateHandler(request, user_email):
    try:
        data = request.json
        task_type = data.get("task_type")
        prompt = data.get("prompt", "")
        num_rows = data.get("num_rows", 10)
        columns = data.get("columns", [])
        examples = data.get("examples", [])

        # Log the request in the database
        store_generate_request(user_email, task_type, columns, prompt, num_rows)

        # Route to the correct generator
        if task_type.lower() == "pii":
            generated = generate_PII_data_sync(prompt, columns, num_rows, examples)
        elif task_type == "text":
            generated = generate_text_data(prompt, columns, num_rows, examples)
        elif task_type == "image":
            generated = generate_image_data(prompt, columns, num_rows, examples)
        elif task_type == "video":
            generated = generate_video_data(prompt, columns, num_rows, examples)
        else:
            return jsonify({"error": f"Unsupported task_type: {task_type}"}), 400

        # Save to file
        file_id = str(uuid.uuid4())
        file_path = os.path.join(OUTPUT_DIR, f"{file_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(generated, f, ensure_ascii=False, indent=2)

        # Return JSON response + download URL
        return jsonify({
            "data": generated,
            "download_url": f"/public/download/{file_id}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
