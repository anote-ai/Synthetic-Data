import logging
import importlib
from flask import jsonify
from database.db import store_generate_request

logger = logging.getLogger(__name__)

_GENERATOR_REGISTRY = {
    "text":     ("generators.text",     "generate_text_data"),
    "image":    ("generators.image",    "generate_image_data"),
    "video":    ("generators.video",    "generate_video_data"),
    "audio":    ("generators.audio",    "generate_audio_data"),
    "agent":    ("generators.agent",    "generate_agent_data"),
    "pii":      ("generators.PII",      "generate_pii_data"),
    "language": ("generators.Language", "generate_language_data"),
    "tabular":  ("generators.tabular",  "generate_tabular_data"),
    "code":     ("generators.code",     "generate_code_data"),
}


def _resolve_generator(task_type):
    """Resolve generator function for task_type. Always reads from the module
    attribute so test patches via unittest.mock.patch take effect."""
    entry = _GENERATOR_REGISTRY.get(task_type)
    if not entry:
        return None
    module_path, fn_name = entry
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, fn_name)
    except Exception as e:
        logger.warning("Could not load generator '%s': %s", task_type, e)
        return None


def GenerateHandler(request, user_email):
    data = request.json
    task_type = data.get("task_type")
    prompt = data.get("prompt", "")
    num_rows = data.get("num_rows", 5)
    columns = data.get("columns", [])
    examples = data.get("examples", [])
    params = data.get("params", {})

    try:
        store_generate_request(user_email, task_type, columns, prompt, num_rows)
    except Exception as e:
        logger.warning("DB logging failed (non-fatal): %s", e)

    generator_fn = _resolve_generator(task_type)

    if generator_fn is None:
        return jsonify({"error": f"Unsupported or unavailable task_type: {task_type}"}), 422

    try:
        generated = generator_fn(prompt, columns, num_rows, examples, params)
    except Exception as e:
        logger.error("Generator %s failed: %s", task_type, e, exc_info=True)
        generated = [{"status": "failed", "error": str(e)}]

    return jsonify({"data": generated})
