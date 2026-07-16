"""
RSI feedback loop (issue #92): scores synthetic data batches by their measured
"lift" on a lightweight probe model, and learns which generator prompt
templates produce genuinely useful data.

Persistence follows the file-first, DB-optional-mirror pattern already used
by utils/versioning.py and utils/jobs.py — everything works with no MySQL
configured; the DB mirror is best-effort.
"""
import json
import logging
import os
import random
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs"))
_BATCHES_DIR = _OUTPUT_DIR / "rsi_batches"
_TEMPLATES_DIR = _OUTPUT_DIR / "rsi_templates"

MIN_USES_BEFORE_EXCLUSION = 3


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _batches_dir() -> Path:
    _BATCHES_DIR.mkdir(parents=True, exist_ok=True)
    return _BATCHES_DIR


def _templates_dir(task_type: str) -> Path:
    d = _TEMPLATES_DIR / task_type
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Probe model (lightweight: TF-IDF + logistic regression) ──────────────────

def train_probe(rows: list, text_column: str, label_column: str):
    """Fit a TF-IDF + LogisticRegression probe on rows. Returns (vectorizer, model)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    texts = [str(r[text_column]) for r in rows]
    labels = [r[label_column] for r in rows]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    X = vectorizer.fit_transform(texts)
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X, labels)
    return vectorizer, model


def evaluate_probe(vectorizer, model, rows: list, text_column: str, label_column: str) -> float:
    """Return macro-F1 of the probe on rows."""
    from sklearn.metrics import f1_score

    texts = [str(r[text_column]) for r in rows]
    y_true = [r[label_column] for r in rows]
    y_pred = model.predict(vectorizer.transform(texts))
    return f1_score(y_true, y_pred, average="macro", zero_division=0)


def compute_lift(
    baseline_rows: list,
    synthetic_rows: list,
    test_rows: list,
    text_column: str,
    label_column: str,
) -> dict:
    """
    Train the probe on baseline_rows alone, then on baseline_rows + synthetic_rows,
    and compare macro-F1 on test_rows. Never raises — returns {"status": "error", ...}
    on failure.
    """
    def _labeled(rows):
        return [
            r for r in rows
            if r.get("status", "succeeded") == "succeeded"
            and r.get(text_column)
            and r.get(label_column) not in (None, "")
        ]

    try:
        baseline_ok = _labeled(baseline_rows)
        synthetic_ok = _labeled(synthetic_rows)
        test_ok = _labeled(test_rows)

        if len(baseline_ok) < 2 or len(test_ok) < 2:
            return {"status": "error", "error": "baseline_data and test_data each need at least 2 labeled rows"}
        if len({r[label_column] for r in baseline_ok}) < 2:
            return {"status": "error", "error": "baseline_data must contain at least 2 distinct labels"}
        if not synthetic_ok:
            return {"status": "error", "error": "synthetic batch had no successfully labeled rows to score"}

        vec_base, clf_base = train_probe(baseline_ok, text_column, label_column)
        baseline_score = evaluate_probe(vec_base, clf_base, test_ok, text_column, label_column)

        vec_new, clf_new = train_probe(baseline_ok + synthetic_ok, text_column, label_column)
        new_score = evaluate_probe(vec_new, clf_new, test_ok, text_column, label_column)

        lift_score = round(new_score - baseline_score, 4)
        return {
            "status": "flagged" if lift_score < 0 else "scored",
            "baseline_score": round(baseline_score, 4),
            "new_score": round(new_score, 4),
            "lift_score": lift_score,
        }
    except Exception as e:
        logger.warning("compute_lift failed: %s", e)
        return {"status": "error", "error": str(e)}


# ── Batch persistence ──────────────────────────────────────────────────────

def save_batch(
    user_email: str,
    task_type: str,
    template_id: Optional[str],
    weak_spot: Optional[str],
    target_model: Optional[str],
    iteration: Optional[int],
    prompt: str,
    row_count: int,
    lift_result: dict,
) -> str:
    """Persist an RSI batch record and return its batch_id (uuid4)."""
    batch_id = str(uuid.uuid4())
    record = {
        "batch_id": batch_id,
        "user_email": user_email,
        "task_type": task_type,
        "template_id": template_id,
        "weak_spot": weak_spot,
        "target_model": target_model,
        "iteration": iteration,
        "prompt": prompt,
        "row_count": row_count,
        "baseline_score": lift_result.get("baseline_score"),
        "new_score": lift_result.get("new_score"),
        "lift_score": lift_result.get("lift_score"),
        "status": lift_result.get("status", "unscored"),
        "error": lift_result.get("error"),
        "created_at": _now(),
    }
    try:
        path = _batches_dir() / f"{batch_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("Could not persist RSI batch %s: %s", batch_id, e)

    try:
        from database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO rsi_batches
                   (batch_id, user_email, task_type, template_id, weak_spot, target_model,
                    iteration, prompt, row_count, baseline_score, new_score, lift_score, status, error)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    batch_id, user_email, task_type, template_id, weak_spot, target_model,
                    iteration, prompt, row_count, record["baseline_score"], record["new_score"],
                    record["lift_score"], record["status"], record["error"],
                ),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass  # DB optional — file store is the fallback

    return batch_id


def get_batch(batch_id: str) -> Optional[dict]:
    """Return the full batch record, or None if not found."""
    try:
        path = _batches_dir() / f"{batch_id}.json"
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        logger.warning("Could not read RSI batch file %s: %s", batch_id, e)

    try:
        from database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM rsi_batches WHERE batch_id = %s", (batch_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row
    except Exception:
        pass

    return None


def list_batches(task_type: Optional[str] = None, limit: int = 50) -> list:
    """Return recent RSI batch records, newest first, optionally filtered by task_type."""
    batches = []
    try:
        files = sorted(_batches_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            try:
                record = json.loads(f.read_text())
                if task_type is None or record.get("task_type") == task_type:
                    batches.append(record)
                    if len(batches) >= limit:
                        break
            except Exception:
                continue
    except Exception as e:
        logger.warning("Could not list RSI batches: %s", e)
    return batches


# ── Template library ─────────────────────────────────────────────────────────

_DEFAULT_TEMPLATES = [
    {
        "label": "generic",
        "prompt_template": (
            "{base_prompt}\n"
            "Focus on generating diverse, realistic examples related to: {weak_spot}."
        ),
    },
    {
        "label": "hard-case",
        "prompt_template": (
            "{base_prompt}\n"
            "Generate especially hard, edge-case examples for: {weak_spot}. "
            "Include subtle variations, exceptions, and tricky phrasing that a naive model would misclassify."
        ),
    },
]


def _template_path(task_type: str, template_id: str) -> Path:
    return _templates_dir(task_type) / f"{template_id}.json"


def _write_template(t: dict) -> None:
    try:
        _template_path(t["task_type"], t["template_id"]).write_text(
            json.dumps(t, ensure_ascii=False, indent=2)
        )
    except Exception as e:
        logger.warning("Could not persist RSI template %s: %s", t.get("template_id"), e)

    try:
        from database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO rsi_templates (template_id, task_type, label, prompt_template, use_count, avg_lift)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE use_count = VALUES(use_count), avg_lift = VALUES(avg_lift)""",
                (t["template_id"], t["task_type"], t["label"], t["prompt_template"], t["use_count"], t["avg_lift"]),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass


def _load_template(task_type: str, template_id: str) -> Optional[dict]:
    path = _template_path(task_type, template_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _load_templates(task_type: str) -> list:
    templates = []
    for f in _templates_dir(task_type).glob("*.json"):
        try:
            templates.append(json.loads(f.read_text()))
        except Exception:
            continue
    return templates


def _seed_default_templates(task_type: str) -> list:
    templates = []
    for default in _DEFAULT_TEMPLATES:
        t = {
            "template_id": f"{task_type}-{default['label']}",
            "task_type": task_type,
            "label": default["label"],
            "prompt_template": default["prompt_template"],
            "use_count": 0,
            "avg_lift": None,
            "lift_history": [],
            "created_at": _now(),
        }
        _write_template(t)
        templates.append(t)
    return templates


def select_template(task_type: str, weak_spot: Optional[str] = None, template_id: Optional[str] = None) -> dict:
    """
    Pick a generator prompt template for this task_type. Seeds two default
    templates on first use. Weighted-random toward higher avg_lift; templates
    with negative avg_lift are excluded once they've been used enough times
    to trust the signal, unless that would empty the pool.
    """
    templates = _load_templates(task_type)
    if not templates:
        templates = _seed_default_templates(task_type)

    if template_id:
        for t in templates:
            if t["template_id"] == template_id:
                return t
        # Not among the known templates for this task_type — fall through to auto-select.

    eligible = [
        t for t in templates
        if not (t["use_count"] >= MIN_USES_BEFORE_EXCLUSION and (t["avg_lift"] or 0) < 0)
    ]
    if not eligible:
        eligible = templates

    weights = [max(t["avg_lift"] or 0, 0) + 0.1 for t in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]


def record_template_result(task_type: str, template_id: str, batch_id: str, lift_score: Optional[float]) -> None:
    """Append this batch's lift score to the template's history and recompute avg_lift."""
    if lift_score is None:
        return
    t = _load_template(task_type, template_id)
    if t is None:
        return
    t.setdefault("lift_history", []).append({"batch_id": batch_id, "lift_score": lift_score, "created_at": _now()})
    t["use_count"] = len(t["lift_history"])
    scores = [h["lift_score"] for h in t["lift_history"]]
    t["avg_lift"] = round(sum(scores) / len(scores), 4)
    _write_template(t)


def list_templates(task_type: Optional[str] = None) -> list:
    """Return template summaries (no lift_history) sorted by avg_lift desc."""
    task_types = [task_type] if task_type else (
        [d.name for d in _TEMPLATES_DIR.iterdir() if d.is_dir()] if _TEMPLATES_DIR.exists() else []
    )
    result = []
    for tt in task_types:
        for t in _load_templates(tt):
            entry = {k: v for k, v in t.items() if k != "lift_history"}
            entry["excluded"] = t["use_count"] >= MIN_USES_BEFORE_EXCLUSION and (t["avg_lift"] or 0) < 0
            result.append(entry)
    result.sort(key=lambda t: t["avg_lift"] if t["avg_lift"] is not None else -999, reverse=True)
    return result
