from flask import jsonify
from database.db import store_generate_request, store_generated_data
from generators.text import generate_text_data
# from generators.image import generate_image_data
# from generators.video import generate_video_data
# from generators.agent import generate_agent_data
# from generators.audio import generate_audio_data

def GenerateHandler(request, user_email):
    data = request.json
    task_type = data.get("task_type")
    prompt = data.get("prompt")
    num_rows = data.get("num_rows", 10)
    columns = data.get("columns", [])
    examples = data.get("examples", [])

    # Store the request and get the request ID
    request_id = store_generate_request(task_type, columns, prompt, num_rows, user_email)

    if task_type == "text":
        generated = generate_text_data(prompt, num_rows, columns)

    # elif task_type == "image":
    #     generated = generate_image_data(prompt, columns, num_rows, examples)

    # elif task_type == "video":
    #     generated = generate_video_data(prompt, columns, num_rows, examples)
        
    # elif task_type == "agent":
    #     generated = generate_agent_data(prompt, columns, num_rows, examples)
        
    # elif task_type == "audio":
    #     generated = generate_audio_data(prompt, columns, num_rows, examples)
        
    else:
        raise ValueError(f"Unsupported task_type: {task_type}")

    # Store the generated data in the database
    if request_id and generated:
        store_generated_data(request_id, generated)

    return jsonify({
        "data": generated,
        "request_id": request_id
    })