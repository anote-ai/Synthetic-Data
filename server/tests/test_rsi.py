"""Tests for the RSI feedback loop (issue #92): probe/lift scoring, template
library, batch persistence, and the /public/generate + /public/rsi/* routes."""
import json
import os
import sys
import uuid
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REPLICATE_API_TOKEN", "test-token")
os.environ.setdefault("SYNTHETIC_OUTPUT_DIR", "/tmp/synthetic-test-output")

POSITIVE_VOCAB = ["amazing", "wonderful", "excellent", "great"]
NEGATIVE_VOCAB = ["terrible", "bad", "awful", "poor"]


def _row(words, label):
    return {"text": " ".join(words), "label": label, "status": "succeeded"}


BASELINE_ROWS = [
    _row(["amazing", "wonderful", "product"], "positive"),
    _row(["excellent", "great", "quality"], "positive"),
    _row(["wonderful", "fast", "shipping"], "positive"),
    _row(["great", "amazing", "service"], "positive"),
    _row(["excellent", "wonderful", "experience"], "positive"),
    _row(["amazing", "great", "value"], "positive"),
    _row(["terrible", "bad", "quality"], "negative"),
    _row(["awful", "poor", "service"], "negative"),
    _row(["bad", "terrible", "product"], "negative"),
    _row(["poor", "awful", "experience"], "negative"),
    _row(["terrible", "poor", "value"], "negative"),
    _row(["bad", "awful", "shipping"], "negative"),
]

TEST_ROWS = [
    _row(["amazing", "excellent", "product"], "positive"),
    _row(["wonderful", "great", "service"], "positive"),
    _row(["excellent", "amazing", "value"], "positive"),
    _row(["terrible", "awful", "product"], "negative"),
    _row(["bad", "poor", "service"], "negative"),
    _row(["terrible", "bad", "value"], "negative"),
]

HELPFUL_SYNTHETIC_ROWS = [
    _row(["bad", "disappointing", "purchase"], "negative"),
    _row(["terrible", "awful", "experience"], "negative"),
    _row(["poor", "quality", "bad"], "negative"),
    _row(["awful", "terrible", "delivery"], "negative"),
    _row(["disappointing", "poor", "service"], "negative"),
]

MISLABELED_SYNTHETIC_ROWS = [
    _row(["terrible", "awful", "shipping"], "positive"),
    _row(["bad", "poor", "quality"], "positive"),
    _row(["poor", "terrible", "value"], "positive"),
    _row(["awful", "bad", "service"], "positive"),
    _row(["terrible", "poor", "product"], "positive"),
    _row(["bad", "awful", "experience"], "positive"),
]


class TestProbe:
    def test_train_and_evaluate_probe_on_separable_data(self):
        from utils.rsi import train_probe, evaluate_probe
        vec, clf = train_probe(BASELINE_ROWS, "text", "label")
        score = evaluate_probe(vec, clf, TEST_ROWS, "text", "label")
        assert score > 0.8


class TestComputeLift:
    def test_helpful_synthetic_batch_yields_positive_lift(self):
        from utils.rsi import compute_lift
        # Weaken the baseline so there's room for the synthetic batch to help.
        weak_baseline = BASELINE_ROWS[:7]  # only 1 negative example
        result = compute_lift(weak_baseline, HELPFUL_SYNTHETIC_ROWS, TEST_ROWS, "text", "label")
        assert result["status"] == "scored"
        assert result["lift_score"] > 0

    def test_mislabeled_synthetic_batch_yields_negative_lift(self):
        from utils.rsi import compute_lift
        result = compute_lift(BASELINE_ROWS, MISLABELED_SYNTHETIC_ROWS, TEST_ROWS, "text", "label")
        assert result["status"] == "flagged"
        assert result["lift_score"] < 0

    def test_too_few_baseline_rows_returns_error(self):
        from utils.rsi import compute_lift
        result = compute_lift([BASELINE_ROWS[0]], HELPFUL_SYNTHETIC_ROWS, TEST_ROWS, "text", "label")
        assert result["status"] == "error"

    def test_single_label_baseline_returns_error(self):
        from utils.rsi import compute_lift
        single_label = [r for r in BASELINE_ROWS if r["label"] == "positive"]
        result = compute_lift(single_label, HELPFUL_SYNTHETIC_ROWS, TEST_ROWS, "text", "label")
        assert result["status"] == "error"

    def test_no_successful_synthetic_rows_returns_error(self):
        from utils.rsi import compute_lift
        failed = [{"status": "failed", "error": "boom"}]
        result = compute_lift(BASELINE_ROWS, failed, TEST_ROWS, "text", "label")
        assert result["status"] == "error"


class TestBatchPersistence:
    def test_save_and_get_batch_roundtrip(self, tmp_path):
        with patch("utils.rsi._BATCHES_DIR", tmp_path):
            from utils.rsi import save_batch, get_batch
            batch_id = save_batch(
                user_email="u@t.com", task_type="text", template_id="text-generic",
                weak_spot="negation", target_model="clf-v1", iteration=1,
                prompt="prompt text", row_count=5,
                lift_result={"status": "scored", "baseline_score": 0.5, "new_score": 0.6, "lift_score": 0.1},
            )
            record = get_batch(batch_id)
        assert uuid.UUID(batch_id)
        assert record["lift_score"] == 0.1
        assert record["status"] == "scored"

    def test_get_batch_not_found_returns_none(self, tmp_path):
        with patch("utils.rsi._BATCHES_DIR", tmp_path):
            from utils.rsi import get_batch
            assert get_batch("nonexistent") is None

    def test_list_batches_filters_by_task_type(self, tmp_path):
        with patch("utils.rsi._BATCHES_DIR", tmp_path):
            from utils.rsi import save_batch, list_batches
            save_batch("u@t.com", "text", "text-generic", "ws", "m", 1, "p", 3, {"status": "unscored"})
            save_batch("u@t.com", "image", "image-generic", "ws", "m", 1, "p", 3, {"status": "unscored"})
            batches = list_batches(task_type="text")
        assert len(batches) == 1
        assert batches[0]["task_type"] == "text"


class TestTemplateLibrary:
    def test_cold_start_seeds_two_default_templates(self, tmp_path):
        with patch("utils.rsi._TEMPLATES_DIR", tmp_path):
            from utils.rsi import select_template, list_templates
            select_template("text")  # first call seeds the default templates
            templates = list_templates(task_type="text")
        assert len(templates) == 2
        assert {t["label"] for t in templates} == {"generic", "hard-case"}

    def test_select_template_respects_explicit_template_id(self, tmp_path):
        with patch("utils.rsi._TEMPLATES_DIR", tmp_path):
            from utils.rsi import select_template
            t = select_template("text", template_id="text-hard-case")
        assert t["template_id"] == "text-hard-case"

    def test_low_lift_template_gets_excluded_after_min_uses(self, tmp_path):
        with patch("utils.rsi._TEMPLATES_DIR", tmp_path):
            from utils.rsi import select_template, record_template_result, list_templates, MIN_USES_BEFORE_EXCLUSION

            # Force-select the generic template each time and record consistently negative lift.
            for _ in range(MIN_USES_BEFORE_EXCLUSION):
                t = select_template("text", template_id="text-generic")
                record_template_result("text", t["template_id"], str(uuid.uuid4()), -0.2)

            templates = {t["template_id"]: t for t in list_templates(task_type="text")}
            assert templates["text-generic"]["excluded"] is True

            # Selection must now never return the excluded template.
            for _ in range(20):
                picked = select_template("text")
                assert picked["template_id"] != "text-generic"

    def test_record_template_result_updates_avg_lift(self, tmp_path):
        with patch("utils.rsi._TEMPLATES_DIR", tmp_path):
            from utils.rsi import select_template, record_template_result, list_templates
            t = select_template("text", template_id="text-generic")
            record_template_result("text", t["template_id"], "b1", 0.2)
            record_template_result("text", t["template_id"], "b2", 0.4)
            templates = {t["template_id"]: t for t in list_templates(task_type="text")}
        assert templates["text-generic"]["avg_lift"] == 0.3
        assert templates["text-generic"]["use_count"] == 2


class TestGenerateEndpointWithRsiContext:
    def test_generate_with_rsi_context_returns_batch(self, client, tmp_path):
        mock_rows = HELPFUL_SYNTHETIC_ROWS
        payload = {
            "task_type": "text",
            "prompt": "Generate product reviews",
            "num_rows": len(mock_rows),
            "columns": ["text", "label"],
            "examples": [],
            "rsi_context": {
                "weak_spot": "negative reviews",
                "target_model": "demo-classifier",
                "iteration": 1,
                "baseline_data": BASELINE_ROWS[:7],
                "test_data": TEST_ROWS,
                "text_column": "text",
                "label_column": "label",
            },
        }
        with patch("utils.rsi._BATCHES_DIR", tmp_path / "batches"), \
             patch("utils.rsi._TEMPLATES_DIR", tmp_path / "templates"), \
             patch("generators.text.generate_text_data", return_value=mock_rows):
            resp = client.post("/public/generate", json=payload)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "rsi" in data
            assert data["rsi"]["status"] in ("scored", "flagged")
            batch_id = data["rsi"]["batch_id"]

            batch_resp = client.get(f"/public/rsi/batches/{batch_id}")
            assert batch_resp.status_code == 200
            assert batch_resp.get_json()["batch_id"] == batch_id

            templates_resp = client.get("/public/rsi/templates?task_type=text")
            assert templates_resp.status_code == 200
            assert len(templates_resp.get_json()["templates"]) == 2

    def test_generate_without_rsi_context_unaffected(self, client, valid_text_payload):
        mock_result = [{"question": "Q1", "answer": "A1", "status": "succeeded"}]
        with patch("generators.text.generate_text_data", return_value=mock_result):
            resp = client.post("/public/generate", json=valid_text_payload)
        assert resp.status_code == 200
        assert "rsi" not in resp.get_json()

    def test_get_rsi_batch_not_found(self, client, tmp_path):
        with patch("utils.rsi._BATCHES_DIR", tmp_path):
            resp = client.get("/public/rsi/batches/nonexistent-id")
        assert resp.status_code == 404
