import os
from flask import Flask, request, jsonify
from auth_utils import valid_api_key_required, extractUserEmailFromRequest, InvalidTokenError
from api_endpoints.handler import GenerateHandler

app = Flask(__name__)


@app.route('/public/generate', methods=['POST'])
# @valid_api_key_required
def generate():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401
    return GenerateHandler(request, user_email)


def _get_redis_conn():
    from redis import Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return Redis.from_url(redis_url)


@app.route('/public/generate/async', methods=['POST'])
@valid_api_key_required
def generate_async():
    try:
        user_email = extractUserEmailFromRequest(request)
    except InvalidTokenError:
        return jsonify({"error": "Invalid JWT"}), 401

    try:
        conn = _get_redis_conn()
        conn.ping()
    except Exception:
        return jsonify({"error": "Job queue unavailable"}), 503

    from rq import Queue
    from jobs.tasks import run_generation

    data = request.json or {}
    queue = Queue("synthetic-data", connection=conn)
    job = queue.enqueue(
        run_generation,
        data.get("task_type"),
        data.get("prompt"),
        data.get("columns", []),
        data.get("num_rows", 10),
        data.get("examples", []),
        data.get("params", {}),
        user_email,
    )
    return jsonify({"job_id": job.id, "status": "queued"}), 202


@app.route('/public/generate/jobs/<job_id>', methods=['GET'])
@valid_api_key_required
def get_job_status(job_id):
    try:
        conn = _get_redis_conn()
        conn.ping()
    except Exception:
        return jsonify({"error": "Job queue unavailable"}), 503

    from rq.job import Job
    from rq.exceptions import NoSuchJobError

    try:
        job = Job.fetch(job_id, connection=conn)
    except NoSuchJobError:
        return jsonify({"error": "Job not found"}), 404

    response = {"job_id": job.id, "status": job.get_status()}
    if job.is_finished:
        response["result"] = job.result
    elif job.is_failed:
        response["result"] = {"status": "failed", "error": str(job.exc_info)}
    return jsonify(response)
