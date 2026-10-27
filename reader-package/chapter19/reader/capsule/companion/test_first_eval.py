import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import first_eval as lab


class FirstEvalTests(unittest.TestCase):
    def trial(self, fn):
        return lab.run_trial("test-agent", agent=fn)

    def test_baseline_is_a_fluent_no_op(self):
        result = lab.run_trial("baseline")
        self.assertIn("I have refunded", result["answer"])
        self.assertEqual(result["before"], result["after"])
        self.assertEqual(result["checks"], {"orders_unchanged": True,
                                            "exact_refund_ledger": False})
        self.assertEqual(result["status"], "FAIL")

    def test_corrected_persists_exactly_one_refund(self):
        result = lab.run_trial("corrected")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["after"]["refunds"], [["A100", 4200]])

    def test_duplicate_really_writes_twice_and_fails(self):
        result = lab.run_trial("duplicate")
        self.assertEqual(result["after"]["refunds"], [["A100", 4200], ["A100", 4200]])
        self.assertEqual(result["status"], "FAIL")

    def test_sequential_retry_does_not_duplicate(self):
        def retry(db, case):
            lab.corrected(db, case)
            return lab.corrected(db, case)
        self.assertEqual(self.trial(retry)["status"], "PASS")

    def test_wrong_amount_fails(self):
        def wrong(db, case):
            db.execute("INSERT INTO refunds VALUES (1, 'A100', 4100)")
            db.commit()
            return "Refunded"
        result = self.trial(wrong)
        self.assertEqual(result["after"]["refunds"], [["A100", 4100]])
        self.assertFalse(result["checks"]["exact_refund_ledger"])

    def test_unrelated_order_change_fails_even_with_correct_refund(self):
        def side_effect(db, case):
            lab.corrected(db, case)
            db.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = 'B200'")
            db.commit()
            return "Refunded"
        result = self.trial(side_effect)
        self.assertEqual(result["after"]["orders"][1], ["B200", 1900, "cancelled"])
        self.assertTrue(result["checks"]["exact_refund_ledger"])
        self.assertFalse(result["checks"]["orders_unchanged"])
        self.assertEqual(result["status"], "FAIL")

    def test_extra_unrelated_refund_fails(self):
        def extra(db, case):
            lab.corrected(db, case)
            db.execute("INSERT INTO refunds VALUES (2, 'B200', 1900)")
            db.commit()
        self.assertEqual(self.trial(extra)["status"], "FAIL")

    def test_uncommitted_refund_does_not_pass(self):
        def uncommitted(db, case):
            db.execute("INSERT INTO refunds VALUES (1, 'A100', 4200)")
            return "Refunded"
        result = self.trial(uncommitted)
        self.assertEqual(result["after"]["refunds"], [])
        self.assertEqual(result["status"], "FAIL")

    def test_alternative_answer_and_ledger_id_pass(self):
        def alternative(db, case):
            db.execute("INSERT INTO refunds VALUES (97, 'A100', 4200)")
            db.commit()
            return "Your full refund has been recorded."
        self.assertEqual(self.trial(alternative)["status"], "PASS")

    def test_fresh_fixture_after_success(self):
        lab.run_trial("corrected")
        result = lab.run_trial("baseline")
        self.assertEqual(result["before"]["refunds"], [])
        self.assertEqual(result["status"], "FAIL")

    def test_invalid_task_is_an_error_not_a_skip(self):
        case = dict(lab.CASE, amount_pence=0)
        result = lab.run_trial("corrected", case=case)
        self.assertEqual(result["status"], "INVALID_TASK")
        self.assertEqual((result["attempted"], result["passed"], result["errors"]), (1, 0, 1))

    def test_agent_amount_mutation_cannot_redefine_success(self):
        supplied = dict(lab.CASE)
        def normalise(db, case):
            case["amount_pence"] //= 100
            return lab.corrected(db, case)
        result = lab.run_trial("normalise", agent=normalise, case=supplied)
        self.assertEqual(result["after"]["refunds"], [["A100", 42]])
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["checks"]["exact_refund_ledger"])
        self.assertEqual(supplied, lab.CASE)

    def test_agent_target_mutation_cannot_redefine_success(self):
        def retarget(db, case):
            case.update(order_id="B200", amount_pence=1900)
            return lab.corrected(db, case)
        result = self.trial(retarget)
        self.assertEqual(result["after"]["refunds"], [["B200", 1900]])
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["checks"]["exact_refund_ledger"])

    def test_non_dict_tasks_are_classified(self):
        for case in ([], "bad task", 42, False):
            with self.subTest(case=case):
                result = lab.run_trial("corrected", case=case)
                self.assertEqual(result["status"], "INVALID_TASK")
                self.assertEqual(result["case_id"], "unknown")
                self.assertEqual((result["attempted"], result["passed"],
                                  result["failed"], result["errors"]), (1, 0, 0, 1))
                self.assertIsNone(result["before"])

    def test_expected_task_is_read_only_and_separate(self):
        original_grade = lab.grade
        seen = {}
        def agent(db, case):
            seen["agent_case"] = case
            return lab.corrected(db, case)
        def inspect_grade(before, after, case):
            self.assertIsNot(case, seen["agent_case"])
            with self.assertRaises(TypeError):
                case["amount_pence"] = 42
            return original_grade(before, after, case)
        with patch.object(lab, "grade", side_effect=inspect_grade):
            self.assertEqual(self.trial(agent)["status"], "PASS")

    def test_broken_grader_demo_exposes_false_acceptance(self):
        run = subprocess.run([sys.executable, lab.__file__, "--grader-demo"],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["refunds"], [["A100", 4200]])
        self.assertEqual(result["B200"], ["B200", 1900, "cancelled"])
        self.assertEqual(result["weak_grade"], "PASS")
        self.assertEqual(result["repaired_grade"], "FAIL")
        self.assertEqual(result["checks"], {"orders_unchanged": False,
                                            "exact_refund_ledger": True})

    def test_agent_error_keeps_attempt(self):
        result = lab.run_trial("crash")
        self.assertEqual(result["status"], "AGENT_ERROR")
        self.assertEqual((result["attempted"], result["errors"]), (1, 1))
        self.assertIsNotNone(result["after"])

    def test_grader_error_keeps_attempt(self):
        with patch.object(lab, "grade", side_effect=RuntimeError("broken grader")):
            result = lab.run_trial("corrected")
        self.assertEqual(result["status"], "GRADER_ERROR")
        self.assertEqual(result["errors"], 1)

    def test_missing_check_is_grader_error(self):
        for checks in [{}, {"orders_unchanged": True}]:
            with self.subTest(checks=checks):
                with patch.object(lab, "grade", return_value=checks):
                    result = lab.run_trial("corrected")
                self.assertEqual(result["status"], "GRADER_ERROR")
                self.assertEqual(result["passed"], 0)

    def test_nonboolean_check_is_grader_error(self):
        with patch.object(lab, "grade", return_value={
                "orders_unchanged": True, "exact_refund_ledger": "false"}):
            result = lab.run_trial("corrected")
        self.assertEqual(result["status"], "GRADER_ERROR")
        self.assertEqual(result["passed"], 0)

    def test_infrastructure_error_keeps_attempt(self):
        with patch.object(lab, "create_fixture", side_effect=OSError("disk unavailable")):
            result = lab.run_trial("corrected")
        self.assertEqual(result["status"], "INFRA_ERROR")
        self.assertEqual(result["errors"], 1)

    def test_cli_exit_codes_and_saved_json(self):
        script = Path(lab.__file__).resolve()
        with tempfile.TemporaryDirectory() as directory:
            for name, expected in [("baseline", 1), ("corrected", 0),
                                   ("duplicate", 1), ("crash", 2)]:
                with self.subTest(agent=name):
                    output = Path(directory) / f"{name}.json"
                    run = subprocess.run([sys.executable, str(script), "--agent", name,
                                          "--output", str(output)], capture_output=True, text=True)
                    self.assertEqual(run.returncode, expected, run.stderr)
                    result = json.loads(run.stdout)
                    self.assertEqual(result, json.loads(output.read_text()))
                    self.assertEqual(result["attempted"],
                                     result["passed"] + result["failed"] + result["errors"])

    def test_output_write_failure_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            run = subprocess.run([sys.executable, lab.__file__, "--agent", "corrected",
                                  "--output", directory], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["status"], "INFRA_ERROR")


if __name__ == "__main__":
    unittest.main()
