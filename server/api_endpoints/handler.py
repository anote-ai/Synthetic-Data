from flask import jsonify
try:
	from database.db import store_generate_request
except Exception:
	store_generate_request = None

import math
import asyncio
import os


def _generate_language_data(prompt: str, columns: list, num_rows: int, examples: list) -> list:
	# Lazy import to avoid requiring OPENAI_API_KEY unless needed
	from generators.Language import DEFAULT_TOPICS, generate_qas_for_topic, polish_texts, TOPIC_WIKI_URLS

	# Derive topics: if prompt provided, split by comma; else default
	topics = []
	if prompt:
		cand = [t.strip() for t in prompt.split(",") if t.strip()]
		topics = cand if cand else []
	if not topics:
		topics = DEFAULT_TOPICS[:3]

	per_topic = max(1, math.ceil(num_rows / max(1, len(topics))))
	records = []
	for topic in topics:
		qas = generate_qas_for_topic(topic, per_topic)
		for item in qas:
			item["topic"] = topic
			item["reference_urls"] = TOPIC_WIKI_URLS.get(topic, [])
			records.append(item)

	# Polish questions and answers if present
	questions = [r.get("question", "") for r in records]
	answers = [r.get("answer", "") for r in records]
	polished_q = polish_texts(questions)
	polished_a = polish_texts(answers)
	for rec, pq, pa in zip(records, polished_q, polished_a):
		rec["question_augmented"] = pq
		rec["answer_augmented"] = pa

	# Project to requested columns if provided
	if columns:
		projected = []
		for rec in records[:num_rows]:
			projected.append({col: rec.get(col) for col in columns})
		return projected
	return records[:num_rows]


def _generate_pii_data(prompt: str, columns: list, num_rows: int, examples: list) -> list:
	from generators.PII import generate_PII_data
	results = asyncio.run(generate_PII_data(prompt, columns, num_rows, examples))
	if columns:
		projected = []
		for rec in results:
			projected.append({col: rec.get(col) for col in columns})
		return projected
	return results


def _maybe_set_openai_key_from_header(request):
	auth_header = request.headers.get("Authorization") or ""
	if auth_header.lower().startswith("bearer "):
		api_key = auth_header.split(" ", 1)[1].strip()
		if api_key:
			os.environ["OPENAI_API_KEY"] = api_key


def GenerateHandler(request, user_email):
	data = request.json
	task_type = data.get("task_type")
	prompt = data.get("prompt")
	num_rows = data.get("num_rows", 10)
	columns = data.get("columns", [])
	examples = data.get("examples", [])

	# best-effort store; ignore failures in local/dev
	if store_generate_request:
		try:
			store_generate_request(user_email, task_type, columns, prompt, num_rows)
		except Exception:
			pass

	# Set OPENAI_API_KEY from Authorization header if provided
	_maybe_set_openai_key_from_header(request)

	if task_type in ("language", "text"):
		generated = _generate_language_data(prompt, columns, num_rows, examples)
	elif task_type == "pii":
		generated = _generate_pii_data(prompt, columns, num_rows, examples)
	else:
		raise ValueError(f"Unsupported task_type: {task_type}")

	return jsonify({"data": generated})
