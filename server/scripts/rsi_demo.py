"""
RSI feedback loop demo (issue #92).

Runs Natan's generation -> train -> score -> feedback loop end-to-end using
the real generator (server/generators/text.py) and the real RSI utilities
(server/utils/rsi.py) — no mocked scoring, no fabricated numbers. The only
optional mock is the synthetic *generation* step itself, so this runs even
without an OpenAI key.

Usage (from server/):
    python scripts/rsi_demo.py            # uses OPENAI_API_KEY if set
    python scripts/rsi_demo.py --mock     # fully offline, canned synthetic rows
"""
import argparse
import os
import sys
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TASK_TYPE = "text"
TEXT_COLUMN = "clause"
LABEL_COLUMN = "label"
WEAK_SPOT = "negation sentences in legal domain (e.g. 'shall not', 'may not', 'will not' used to express prohibition)"
TARGET_MODEL = "my-classifier-v3"
BASE_PROMPT = (
    "Generate short legal contract clauses labeled as either 'obligation' or 'prohibition', "
    "for columns 'clause' and 'label'."
)
USER_EMAIL = "demo@anote.ai"
ROWS_PER_ITERATION = 6


def _row(clause, label):
    return {"clause": clause, "label": label, "status": "succeeded"}


# A baseline dataset whose "prohibition" examples are all phrased with explicit
# words (prohibited/forbidden/not permitted) — it has never seen the classic
# "shall not / may not / will not" negation construction.
BASELINE_ROWS = [
    _row("The tenant shall pay rent by the first of each month.", "obligation"),
    _row("The contractor must complete the work within 30 days.", "obligation"),
    _row("The buyer is required to provide a deposit before closing.", "obligation"),
    _row("The employee agrees to maintain confidentiality of trade secrets.", "obligation"),
    _row("The supplier shall deliver goods according to the agreed schedule.", "obligation"),
    _row("The borrower is obligated to repay the loan in full.", "obligation"),
    _row("The landlord must provide 30 days notice before entry.", "obligation"),
    _row("The vendor shall maintain adequate insurance coverage.", "obligation"),
    _row("The tenant is prohibited from subletting the premises.", "prohibition"),
    _row("Employees are forbidden from disclosing client information.", "prohibition"),
    _row("Smoking is not permitted anywhere on the premises.", "prohibition"),
    _row("The contractor is barred from hiring subcontractors without approval.", "prohibition"),
]

# Held-out test set: prohibitions phrased with negation ("shall not"/"may not"/
# "will not") — exactly the weak spot the baseline hasn't seen.
TEST_ROWS = [
    _row("The tenant shall not sublet the premises without written consent.", "prohibition"),
    _row("The employee may not disclose confidential information to third parties.", "prohibition"),
    _row("The contractor shall not assign this agreement without prior approval.", "prohibition"),
    _row("The buyer shall not withhold payment pending inspection results.", "prohibition"),
    _row("The supplier will not ship goods after the contract expiration date.", "prohibition"),
    _row("The tenant shall pay a security deposit prior to move-in.", "obligation"),
    _row("The contractor must obtain a permit before starting construction.", "obligation"),
    _row("The employee is required to complete annual compliance training.", "obligation"),
    _row("The landlord shall return the deposit within 14 days of termination.", "obligation"),
    _row("The borrower agrees to provide monthly financial statements.", "obligation"),
]

# Canned rows for --mock (or no OPENAI_API_KEY): "generic" stays in the same
# prohibited/forbidden phrasing as the baseline (doesn't address the weak
# spot); "hard-case" targets the negation construction directly.
MOCK_ROWS = {
    "generic": [
        _row("The distributor is prohibited from selling to competitors.", "prohibition"),
        _row("The manager is forbidden from approving her own expenses.", "prohibition"),
        _row("Parking is not permitted in the loading zone.", "prohibition"),
        _row("The licensee shall pay royalties on a quarterly basis.", "obligation"),
        _row("The seller must disclose known defects prior to sale.", "obligation"),
        _row("The trustee is required to file annual reports.", "obligation"),
    ],
    "hard-case": [
        _row("The licensee shall not sublicense the software to any third party.", "prohibition"),
        _row("The employee may not compete with the company for one year after termination.", "prohibition"),
        _row("The tenant will not alter the structure without landlord approval.", "prohibition"),
        _row("The distributor shall not represent competing brands during the term.", "prohibition"),
        _row("The contractor may not delegate performance without written consent.", "prohibition"),
        _row("The buyer will not resell the goods below the listed price.", "prohibition"),
    ],
}


def generate_batch(template: dict, num_rows: int, mock: bool):
    prompt = template["prompt_template"].format(base_prompt=BASE_PROMPT, weak_spot=WEAK_SPOT)
    if mock:
        rows = MOCK_ROWS[template["label"]][:num_rows]
        return rows, prompt
    from generators.text import generate_text_data
    rows = generate_text_data(prompt, [TEXT_COLUMN, LABEL_COLUMN], num_rows, examples=[])
    return rows, prompt


def run_iteration(iteration: int, mock: bool, template_id: str = None):
    from utils.rsi import select_template, compute_lift, save_batch, record_template_result

    template = select_template(TASK_TYPE, weak_spot=WEAK_SPOT, template_id=template_id)
    rows, prompt = generate_batch(template, ROWS_PER_ITERATION, mock)
    lift_result = compute_lift(BASELINE_ROWS, rows, TEST_ROWS, TEXT_COLUMN, LABEL_COLUMN)

    batch_id = save_batch(
        user_email=USER_EMAIL,
        task_type=TASK_TYPE,
        template_id=template["template_id"],
        weak_spot=WEAK_SPOT,
        target_model=TARGET_MODEL,
        iteration=iteration,
        prompt=prompt,
        row_count=len(rows),
        lift_result=lift_result,
    )
    if lift_result.get("lift_score") is not None:
        record_template_result(TASK_TYPE, template["template_id"], batch_id, lift_result["lift_score"])

    return template, lift_result, batch_id


def print_iteration(n: int, template: dict, lift_result: dict, batch_id: str):
    print(f"\n--- Iteration {n} " + "-" * 50)
    print(f"  template selected : {template['template_id']}  (label: {template['label']})")
    status = lift_result.get("status")
    if status == "error":
        print(f"  status            : error - {lift_result.get('error')}")
        return
    print(f"  baseline F1       : {lift_result['baseline_score']}")
    print(f"  new F1            : {lift_result['new_score']}")
    sign = "+" if lift_result["lift_score"] >= 0 else ""
    print(f"  lift_score        : {sign}{lift_result['lift_score']}")
    print(f"  status            : {status.upper()}"
          + ("  [WARNING] synthetic batch HURT performance" if status == "flagged" else ""))
    print(f"  batch_id          : {batch_id}")


def print_leaderboard():
    from utils.rsi import list_templates
    print("\n" + "=" * 64)
    print("TEMPLATE LEADERBOARD (server/utils/rsi.py: list_templates)")
    print("=" * 64)
    for t in list_templates(task_type=TASK_TYPE):
        flag = " (excluded - consistently low lift)" if t["excluded"] else ""
        print(f"  {t['template_id']:<24} avg_lift={t['avg_lift']}"
              f"  use_count={t['use_count']}{flag}")


def print_curl_examples():
    print("\n" + "=" * 64)
    print("Reproduce the same story against the live Flask API:")
    print("=" * 64)
    print("""
  # 1. start the API (from server/):
  python app.py

  # 2. generate a batch tagged with rsi_context (targets the weak spot above):
  curl -s -X POST http://localhost:5000/public/generate \\
    -H "Content-Type: application/json" \\
    -d '{
      "task_type": "text",
      "prompt": "Generate short legal contract clauses labeled obligation or prohibition",
      "num_rows": 6,
      "columns": ["clause", "label"],
      "rsi_context": {
        "weak_spot": "negation sentences in legal domain",
        "target_model": "my-classifier-v3",
        "iteration": 1,
        "baseline_data": <BASELINE_ROWS>,
        "test_data": <TEST_ROWS>,
        "text_column": "clause",
        "label_column": "label"
      }
    }' | python -m json.tool

  # 3. fetch the lift score later via the returned batch_id:
  curl -s http://localhost:5000/public/rsi/batches/<batch_id> | python -m json.tool

  # 4. see the template leaderboard:
  curl -s http://localhost:5000/public/rsi/templates?task_type=text | python -m json.tool
""")


def main():
    parser = argparse.ArgumentParser(description="RSI feedback loop demo (issue #92)")
    parser.add_argument("--mock", action="store_true", help="skip OpenAI calls, use canned synthetic rows")
    parser.add_argument("--auto-iterations", type=int, default=5,
                         help="number of additional auto-selected iterations after the forced ones (default: 5)")
    args = parser.parse_args()

    mock = args.mock or not os.getenv("OPENAI_API_KEY")
    if mock and not args.mock:
        print("(no OPENAI_API_KEY set - falling back to --mock canned rows)")

    print("=" * 64)
    print("RSI FEEDBACK LOOP DEMO - issue #92")
    print(f"  weak_spot    : {WEAK_SPOT}")
    print(f"  target_model : {TARGET_MODEL}")
    print(f"  mode         : {'mock (offline)' if mock else 'live OpenAI calls'}")
    print("=" * 64)

    print("\nStep 1-2 (forced): try each seeded template once so both have a measured lift.")
    template, lift_result, batch_id = run_iteration(1, mock, template_id="text-generic")
    print_iteration(1, template, lift_result, batch_id)

    template, lift_result, batch_id = run_iteration(2, mock, template_id="text-hard-case")
    print_iteration(2, template, lift_result, batch_id)

    print(f"\nStep 3 ({args.auto_iterations} iterations): let the system auto-select the template "
          "using the lift history above.")
    picks = Counter()
    for i in range(args.auto_iterations):
        template, lift_result, batch_id = run_iteration(3 + i, mock)
        picks[template["template_id"]] += 1
        print_iteration(3 + i, template, lift_result, batch_id)

    print(f"\nAuto-selected template counts over {args.auto_iterations} iterations: {dict(picks)}")
    print_leaderboard()
    print_curl_examples()


if __name__ == "__main__":
    main()
