"""Chapter 1: a synthetic refund task, scripted agents and a state grader.
Run from this directory: python3 first_eval.py --agent baseline
Only Python's standard library is required. No network or model calls.
"""
import argparse
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from types import MappingProxyType

CASE = {
    "id": "support-refund-001",
    "request": "Please refund order A100 in full.",
    "order_id": "A100",
    "amount_pence": 4200,
    "policy": "A100 is verified eligible. Record one full refund; leave other orders unchanged.",
}
ORDERS = [("A100", 4200, "paid"), ("B200", 1900, "paid")]
EXIT_CODES = {"PASS": 0, "FAIL": 1, "INVALID_TASK": 2,
              "AGENT_ERROR": 2, "GRADER_ERROR": 2, "INFRA_ERROR": 2}


def validate_case(case):
    # Chapter 1 intentionally supports one case, not an unvalidated generic schema.
    if not isinstance(case, dict):
        raise ValueError("Task must be a dictionary")
    if case != CASE:
        raise ValueError("This lab accepts only the published support-refund-001 task")


def create_fixture(path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY, amount_pence INTEGER, status TEXT);
            CREATE TABLE refunds (
                refund_id INTEGER PRIMARY KEY, order_id TEXT, amount_pence INTEGER);
        """)
        db.executemany("INSERT INTO orders VALUES (?, ?, ?)", ORDERS)
        db.commit()


def snapshot(path):
    # A separate, read-only connection sees committed state, not agent assertions.
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        return {
            "orders": [list(row) for row in db.execute(
                "SELECT order_id, amount_pence, status FROM orders ORDER BY order_id")],
            "refunds": [list(row) for row in db.execute(
                "SELECT order_id, amount_pence FROM refunds ORDER BY order_id, amount_pence")],
        }


def baseline(db, case):
    return "I have refunded GBP 42.00 for order A100."


def refund_once(db, case):
    """Idempotent for sequential calls in this single-process teaching fixture."""
    rows = db.execute("SELECT amount_pence FROM refunds WHERE order_id = ?",
                      (case["order_id"],)).fetchall()
    if not rows:
        db.execute("INSERT INTO refunds (order_id, amount_pence) VALUES (?, ?)",
                   (case["order_id"], case["amount_pence"]))
        db.commit()
    elif rows != [(case["amount_pence"],)]:
        raise ValueError("Existing refund conflicts with the requested refund")


def corrected(db, case):
    refund_once(db, case)
    return "I have refunded GBP 42.00 for order A100."


def duplicate(db, case):
    for _ in range(2):
        db.execute("INSERT INTO refunds (order_id, amount_pence) VALUES (?, ?)",
                   (case["order_id"], case["amount_pence"]))
    db.commit()
    return "I have refunded GBP 42.00 for order A100."


def crash(db, case):
    raise RuntimeError("Intentional agent error for the error-path demonstration")


AGENTS = {"baseline": baseline, "corrected": corrected,
          "duplicate": duplicate, "crash": crash}


def grade(before, after, case):
    expected = [[case["order_id"], case["amount_pence"]]]
    return {
        "orders_unchanged": after["orders"] == before["orders"],
        "exact_refund_ledger": after["refunds"] == expected,
    }


def run_trial(agent_name, agent=None, case=None):
    case = dict(CASE) if case is None else case
    result = {"case_id": "unknown", "agent": agent_name,
              "attempted": 1, "status": None, "answer": None,
              "before": None, "after": None, "checks": None, "error": None}
    stage = "INVALID_TASK"
    try:
        if isinstance(case, dict):
            result["case_id"] = case.get("id", "unknown")
        validate_case(case)
        # All published task values are scalars. Own the backing dictionary;
        # never expose it to the agent or retain the caller's mutable object.
        expected_case = MappingProxyType(dict(case))
        agent_case = dict(expected_case)
        stage = "INFRA_ERROR"
        with tempfile.TemporaryDirectory(prefix="agent-evals-") as directory:
            path = Path(directory) / "support.sqlite"
            create_fixture(path)
            result["before"] = snapshot(path)
            with closing(sqlite3.connect(path)) as db:
                stage = "AGENT_ERROR"
                try:
                    result["answer"] = (agent or AGENTS[agent_name])(db, agent_case)
                except Exception as exc:
                    result["status"] = "AGENT_ERROR"
                    result["error"] = f"{type(exc).__name__}: {exc}"
            stage = "INFRA_ERROR"
            result["after"] = snapshot(path)
            if result["status"] is None:
                stage = "GRADER_ERROR"
                result["checks"] = grade(result["before"], result["after"], expected_case)
                checks = result["checks"]
                if (set(checks) != {"orders_unchanged", "exact_refund_ledger"}
                        or any(type(value) is not bool for value in checks.values())):
                    raise ValueError("Grader must return both required boolean checks")
                result["status"] = "PASS" if all(checks.values()) else "FAIL"
            stage = "INFRA_ERROR"
    except Exception as exc:
        result["status"] = stage
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["passed"] = int(result["status"] == "PASS")
    result["failed"] = int(result["status"] == "FAIL")
    result["errors"] = int(result["status"] not in ("PASS", "FAIL"))
    return result


def weak_grade(after, case):
    """Intentionally broken teaching predicate; never used by run_trial."""
    return [case["order_id"], case["amount_pence"]] in after["refunds"]


def grader_demo():
    def side_effect(db, case):
        corrected(db, case)
        db.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = 'B200'")
        db.commit()
        return "Refunded"
    result = run_trial("side-effect", agent=side_effect)
    return {
        "refunds": result["after"]["refunds"],
        "B200": result["after"]["orders"][1],
        "weak_grade": "PASS" if weak_grade(result["after"], CASE) else "FAIL",
        "repaired_grade": result["status"],
        "checks": result["checks"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--agent", choices=AGENTS)
    mode.add_argument("--grader-demo", action="store_true",
                      help="Compare an intentionally weak predicate with the state grader")
    parser.add_argument("--output", type=Path, help="Save the same JSON printed to stdout")
    args = parser.parse_args()
    if args.grader_demo:
        if args.output:
            parser.error("--output is only supported with --agent")
        print(json.dumps(grader_demo(), indent=2))
        return 0
    result = run_trial(args.agent)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            result.update(status="INFRA_ERROR", passed=0, failed=0, errors=1,
                          error=f"Could not save output: {type(exc).__name__}: {exc}")
    print(json.dumps(result, indent=2))
    return EXIT_CODES[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
