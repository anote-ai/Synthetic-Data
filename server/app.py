import logging
import os
import time
import uuid

from flask import Flask, request, jsonify, g, Response, stream_with_context
from flask_cors import CORS
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(
    app,
    origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

VALID_TASK_TYPES = {"text", "image", "video", "audio", "agent", "pii", "language", "tabular", "code"}
MAX_ROWS = int(os.getenv("MAX_ROWS_PER_REQUEST", "100"))


class _BodyRequest:
    """Minimal request-like wrapper so GenerateHandler can be called with a modified body."""

    def __init__(self, body):
        self.json = body
        self.is_json = True
        self.headers = request.headers


@app.before_request
def attach_request_id():
    g.request_id = str(uuid.uuid4())
    g.start_time = time.time()


@app.after_request
def log_request(response):
    duration_ms = int((time.time() - getattr(g, "start_time", time.time())) * 1000)
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")
    logger.info(
        "Request completed",
        extra={
            "request_id": getattr(g, "request_id", ""),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/public/generate/task-types", methods=["GET"])
def list_task_types():
    """Return generation task types supported by the public API."""
    return jsonify({
        "task_types": sorted(VALID_TASK_TYPES),
        "max_rows_per_request": MAX_ROWS,
    })


@app.route("/public/generate", methods=["POST"])
def generate():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}

    # Inline validation — keeps 422 responses consistent
    errors = {}
    task_type = body.get("task_type")
    if not task_type:
        errors["task_type"] = "field required"
    elif task_type not in VALID_TASK_TYPES:
        errors["task_type"] = f"must be one of {sorted(VALID_TASK_TYPES)}"

    if not body.get("prompt", "").strip():
        errors["prompt"] = "field required"

    columns = body.get("columns", [])
    if not columns:
        errors["columns"] = "must be a non-empty list"

    num_rows = body.get("num_rows", 5)
    if not isinstance(num_rows, int) or num_rows < 1 or num_rows > MAX_ROWS:
        errors["num_rows"] = f"must be an integer between 1 and {MAX_ROWS}"

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    rsi_context = body.get("rsi_context")
    effective_prompt = body.get("prompt", "")
    rsi_template = None

    if rsi_context:
        from utils.rsi import select_template
        rsi_template = select_template(
            task_type,
            weak_spot=rsi_context.get("weak_spot"),
            template_id=rsi_context.get("template_id"),
        )
        effective_prompt = rsi_template["prompt_template"].format(
            base_prompt=body.get("prompt", ""),
            weak_spot=rsi_context.get("weak_spot") or "",
        )
        result = GenerateHandler(_BodyRequest({**body, "prompt": effective_prompt}), user_email)
    else:
        result = GenerateHandler(request, user_email)

    if isinstance(result, tuple):
        return result  # GenerateHandler returned an error response (e.g. unsupported task_type)

    generated_data = result.get_json().get("data", [])
    payload = dict(result.get_json())

    # Save version snapshot (non-fatal if it fails)
    try:
        from utils.versioning import save_version
        version_id = save_version(
            user_email=user_email,
            task_type=body.get("task_type"),
            prompt=effective_prompt,
            columns=body.get("columns", []),
            params=body.get("params", {}),
            result_data=generated_data,
            num_rows=body.get("num_rows", 5),
            name=body.get("dataset_name"),
            parent_version_id=body.get("parent_version_id"),
            examples=body.get("examples", []),
        )
        payload["version_id"] = version_id
    except Exception as e:
        logger.warning("Versioning failed (non-fatal): %s", e)

    if rsi_context:
        try:
            from utils.rsi import compute_lift, save_batch, record_template_result

            baseline_data = rsi_context.get("baseline_data")
            test_data = rsi_context.get("test_data")
            text_column = rsi_context.get("text_column")
            label_column = rsi_context.get("label_column")
            if baseline_data and test_data and text_column and label_column:
                lift_result = compute_lift(baseline_data, generated_data, test_data, text_column, label_column)
            else:
                lift_result = {"status": "unscored"}

            batch_id = save_batch(
                user_email=user_email,
                task_type=task_type,
                template_id=rsi_template["template_id"],
                weak_spot=rsi_context.get("weak_spot"),
                target_model=rsi_context.get("target_model"),
                iteration=rsi_context.get("iteration"),
                prompt=effective_prompt,
                row_count=len(generated_data),
                lift_result=lift_result,
            )
            if lift_result.get("lift_score") is not None:
                record_template_result(task_type, rsi_template["template_id"], batch_id, lift_result["lift_score"])

            rsi_block = {
                "batch_id": batch_id,
                "template_id": rsi_template["template_id"],
                "status": lift_result.get("status", "unscored"),
                "baseline_score": lift_result.get("baseline_score"),
                "new_score": lift_result.get("new_score"),
                "lift_score": lift_result.get("lift_score"),
            }
            if lift_result.get("status") == "flagged":
                rsi_block["warning"] = (
                    f"Synthetic batch reduced macro-F1 by {abs(lift_result['lift_score'])} vs baseline "
                    "— review before adding it to the training set."
                )
            elif lift_result.get("status") == "error":
                rsi_block["error"] = lift_result.get("error")
            payload["rsi"] = rsi_block
        except Exception as e:
            logger.warning("RSI scoring failed (non-fatal): %s", e)

    return jsonify(payload)


@app.route("/public/generate/versions", methods=["GET"])
def list_versions():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    limit = min(int(request.args.get("limit", 20)), 100)
    from utils.versioning import list_versions as _list
    return jsonify({"versions": _list(user_email, limit)})


@app.route("/public/generate/versions/<version_id>", methods=["GET"])
def get_version(version_id):
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.versioning import get_version as _get
    record = _get(version_id)
    if record is None or record.get("user_email") != user_email:
        return jsonify({"error": f"Version '{version_id}' not found"}), 404
    return jsonify(record)


@app.route("/public/generate/versions/<version_id>", methods=["PATCH"])
def rename_version(version_id):
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}
    patch = {k: v for k, v in body.items() if k in ("name", "quality_score")}
    if not patch:
        return jsonify({"error": "Nothing to update — provide 'name' and/or 'quality_score'"}), 422

    from utils.versioning import get_version as _get, update_version as _update
    record = _get(version_id)
    if record is None or record.get("user_email") != user_email:
        return jsonify({"error": f"Version '{version_id}' not found"}), 404

    record = _update(version_id, **patch)
    return jsonify(record)


@app.route("/public/generate/versions/<version_id>/diff", methods=["GET"])
def diff_version(version_id):
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    against = request.args.get("against")
    if not against:
        return jsonify({"error": "Query param 'against' (a version_id) is required"}), 422

    from utils.versioning import diff_versions as _diff, get_version as _get
    records = (_get(version_id), _get(against))
    if any(record is None or record.get("user_email") != user_email for record in records):
        return jsonify({"error": "One or both versions not found"}), 404
    result = _diff(version_id, against)
    if result is None:
        return jsonify({"error": "One or both versions not found"}), 404
    return jsonify(result)


@app.route("/public/generate/versions/<version_id>/restore", methods=["POST"])
def restore_version(version_id):
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.versioning import get_version as _get, save_version as _save
    source = _get(version_id)
    if source is None or source.get("user_email") != user_email:
        return jsonify({"error": f"Version '{version_id}' not found"}), 404

    new_version_id = _save(
        user_email=user_email,
        task_type=source["task_type"],
        prompt=source["prompt"],
        columns=source["columns"],
        params=source.get("params", {}),
        result_data=source.get("result_data", []),
        num_rows=source["num_rows"],
        name=source.get("name"),
        parent_version_id=version_id,
        examples=source.get("examples", []),
    )
    return jsonify(_get(new_version_id))


@app.route("/public/rsi/batches/<batch_id>", methods=["GET"])
def get_rsi_batch(batch_id):
    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.rsi import get_batch
    batch = get_batch(batch_id)
    if batch is None:
        return jsonify({"error": f"Batch '{batch_id}' not found"}), 404
    return jsonify(batch)


@app.route("/public/rsi/batches", methods=["GET"])
def list_rsi_batches():
    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.rsi import list_batches
    task_type = request.args.get("task_type")
    limit = min(int(request.args.get("limit", 50)), 200)
    return jsonify({"batches": list_batches(task_type=task_type, limit=limit)})


@app.route("/public/rsi/templates", methods=["GET"])
def get_rsi_templates():
    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.rsi import list_templates
    task_type = request.args.get("task_type")
    return jsonify({"templates": list_templates(task_type=task_type)})


@app.route("/public/generate/export", methods=["POST"])
def generate_export():
    from utils.export import make_export_response

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json() or {}
    fmt = body.pop("format", "json")
    filename = body.pop("filename", "synthetic_data")

    VALID_FORMATS = {"csv", "jsonl", "parquet", "json"}
    if fmt not in VALID_FORMATS:
        return jsonify({"error": f"Invalid format. Must be one of: {VALID_FORMATS}"}), 422

    result = GenerateHandler(_BodyRequest(body), user_email)
    data = result.get_json().get("data", [])

    try:
        return make_export_response(data, fmt, filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/public/generate/huggingface", methods=["POST"])
def export_to_huggingface():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}
    required = [field for field in ("token", "repo_id", "rows") if not body.get(field)]
    if required:
        return jsonify({"error": f"Missing required fields: {', '.join(required)}"}), 422
    if "/" not in body["repo_id"]:
        return jsonify({"error": "Dataset name must use username/name format"}), 422

    try:
        from utils.huggingface_export import push_dataset
        url = push_dataset(
            token=body["token"],
            repo_id=body["repo_id"],
            private=bool(body.get("private", False)),
            rows=body["rows"],
            prompt=body.get("prompt", ""),
            task_category=body.get("task_category", "text-classification"),
            language=body.get("language", "en"),
        )
        return jsonify({"dataset_url": url}), 201
    except Exception as e:
        logger.warning("Hugging Face export failed: %s", type(e).__name__)
        return jsonify({"error": "Hugging Face export failed. Check the token and dataset name."}), 502


@app.route("/public/generate/quality", methods=["POST"])
def generate_quality():
    from utils.quality import score_dataset

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json() or {}
    data = body.get("data", [])
    prompt = body.get("prompt", "")
    run_llm_review = body.get("run_llm_review", False)
    deduplicate = body.get("deduplicate", False)

    if not isinstance(data, list) or not data:
        return jsonify({"error": "data must be a non-empty list"}), 422

    try:
        report = score_dataset(data, prompt=prompt, run_llm_review=run_llm_review)
    except Exception as e:
        logger.error("Quality scoring failed: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

    response = {"quality": report}
    if deduplicate:
        from utils.quality import deduplicate as dedup_fn
        response["data"] = dedup_fn(data)
    return jsonify(response)


@app.route("/public/generate/stream", methods=["POST"])
def generate_stream():
    """SSE endpoint — same request body as /public/generate, streams rows as they complete."""
    import json as _json
    import queue as _queue
    import threading
    import inspect
    from api_endpoints.handler import _resolve_generator

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}
    task_type = body.get("task_type")
    prompt = body.get("prompt", "")
    num_rows = body.get("num_rows", 5)
    columns = body.get("columns", [])
    examples = body.get("examples", [])
    params = body.get("params", {})
    dataset_name = body.get("dataset_name")
    parent_version_id = body.get("parent_version_id")

    def event_stream():
        generator_fn = _resolve_generator(task_type)
        if generator_fn is None:
            yield f'data: {_json.dumps({"type": "error", "message": f"Unsupported task_type: {task_type}"})}\n\n'
            return

        try:
            sig = inspect.signature(generator_fn)
            supports_on_row = "on_row" in sig.parameters
        except (ValueError, TypeError):
            supports_on_row = False

        row_queue = _queue.Queue()
        rows_via_callback = []

        def on_row(row):
            rows_via_callback.append(row)
            row_queue.put(row)

        def run_generator():
            try:
                if supports_on_row:
                    result = generator_fn(prompt, columns, num_rows, examples, params, on_row=on_row)
                    # Fallback: if generator returned a list without calling on_row (e.g. in tests)
                    if not rows_via_callback and result:
                        for row in result:
                            row_queue.put(row)
                else:
                    for row in (generator_fn(prompt, columns, num_rows, examples, params) or []):
                        row_queue.put(row)
            except Exception as e:
                row_queue.put({"__stream_error__": str(e)})
            finally:
                row_queue.put(None)  # sentinel

        threading.Thread(target=run_generator, daemon=True).start()

        row_index = 0
        all_rows = []
        while True:
            item = row_queue.get()
            if item is None:
                version_id = None
                try:
                    from utils.versioning import save_version
                    version_id = save_version(
                        user_email=user_email,
                        task_type=task_type,
                        prompt=prompt,
                        columns=columns,
                        params=params,
                        result_data=all_rows,
                        num_rows=num_rows,
                        name=dataset_name,
                        parent_version_id=parent_version_id,
                        examples=examples,
                    )
                except Exception as e:
                    logger.warning("Versioning failed (non-fatal): %s", e)
                yield f'data: {_json.dumps({"type": "done", "total_rows": len(all_rows), "data": all_rows, "version_id": version_id})}\n\n'
                break
            if isinstance(item, dict) and "__stream_error__" in item:
                yield f'data: {_json.dumps({"type": "error", "message": item["__stream_error__"]})}\n\n'
                break
            all_rows.append(item)
            yield f'data: {_json.dumps({"type": "progress", "row": row_index, "total": num_rows, "data": item})}\n\n'
            row_index += 1

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/public/generate/async", methods=["POST"])
def generate_async():
    """Submit a generation job and return immediately with a job_id."""
    from utils.jobs import JobLimitExceeded, submit_job

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    body = request.get_json(silent=True) or {}

    errors = {}
    task_type = body.get("task_type")
    if not task_type:
        errors["task_type"] = "field required"
    elif task_type not in VALID_TASK_TYPES:
        errors["task_type"] = f"must be one of {sorted(VALID_TASK_TYPES)}"
    if not body.get("prompt", "").strip():
        errors["prompt"] = "field required"
    if not body.get("columns", []):
        errors["columns"] = "must be a non-empty list"
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    try:
        job = submit_job(body, user_email)
    except JobLimitExceeded as e:
        return jsonify({"error": str(e)}), 429
    return jsonify({"job_id": job["job_id"], "status": job["status"]}), 202


@app.route("/public/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    """Return job status and result (once complete)."""
    from utils.jobs import get_job as _get

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    job = _get(job_id)
    if job is None or job.get("user_email") != user_email:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    return jsonify(job)


@app.route("/public/jobs/<job_id>", methods=["DELETE"])
def cancel_job(job_id):
    """Cancel a queued or running job."""
    from utils.jobs import cancel_job as _cancel

    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.jobs import get_job as _get
    existing = _get(job_id)
    if existing is None or existing.get("user_email") != user_email:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    job = _cancel(job_id)
    return jsonify(job)


@app.route("/public/jobs/<job_id>/retry", methods=["POST"])
def retry_job(job_id):
    """Create a new attempt for an authenticated user's failed/canceled job."""
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError as e:
        return jsonify({"error": "Invalid JWT token", "detail": str(e)}), 401

    from utils.jobs import retry_job as _retry
    try:
        job = _retry(job_id, user_email)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    if job is None:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    return jsonify({"job_id": job["job_id"], "status": job["status"], "parent_job_id": job_id}), 202


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
