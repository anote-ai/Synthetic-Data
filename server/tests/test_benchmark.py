import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from benchmarks.text_classification import run


def test_benchmark_reports_all_three_conditions_deterministically():
    real = [
        ("refund my invoice", "billing"), ("charged twice", "billing"),
        ("invoice is incorrect", "billing"), ("payment failed", "billing"),
        ("app crashes", "technical"), ("cannot sign in", "technical"),
        ("page is broken", "technical"), ("server error", "technical"),
        ("reset my password", "account"), ("unlock my account", "account"),
        ("change my email", "account"), ("account is locked", "account"),
    ]
    synthetic = [
        ("billing refund requested", "billing"),
        ("technical server crash", "technical"),
        ("account password reset", "account"),
    ]
    first = run(real, synthetic, seed=7, test_fraction=0.25)
    second = run(real, synthetic, seed=7, test_fraction=0.25)
    assert first == second
    assert set(first["results"]) == {"real_only", "synthetic_only", "real_plus_synthetic"}
    assert first["held_out_real_rows"] == 3
