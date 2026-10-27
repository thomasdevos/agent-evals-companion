import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import conversations as c
import make_figures as fig
from chapter02.task_lab import load_card

ROOT = Path(__file__).resolve().parent


def fresh_rows():
    scheduled = [dict(attempt_id=f'{persona}:{candidate}:1', case_id=load_card('clarify')['id'],
                      persona=persona, candidate=candidate)
                 for persona in c.PERSONAS for candidate in ('vague', 'specific')]
    return [c.run(row['persona'], row['candidate'], attempt_id=row['attempt_id']) for row in scheduled]


def signature(row):
    return tuple(row[key] for key in ('persona', 'candidate', 'outcome', 'questions', 'useful', 'unnecessary', 'stop'))


class FigureTests(unittest.TestCase):
    def test_bundled_outcomes_match_runner(self):
        bundled = json.loads((ROOT / 'results.json').read_text())['rows']
        self.assertEqual([signature(row) for row in bundled], [signature(row) for row in fresh_rows()])

    def test_cli_writes_named_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            run = subprocess.run(
                [sys.executable, 'make_figures.py', '--input', 'results.json', '--out', directory],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            text = (Path(directory) / 'persona-agent-outcomes.svg').read_text()
            self.assertIn('data-persona="literal" data-candidate="vague" data-outcome="unknown"', text)
            self.assertIn('data-persona="literal" data-candidate="specific" data-outcome="completed"', text)
            self.assertIn('data-persona="abandon" data-candidate="specific" data-outcome="abandoned"', text)
            bars = (Path(directory) / 'question-use.svg').read_text()
            self.assertIn('Questions and useful replies', bars)
            self.assertIn('<svg', bars)

    def test_missing_input_exits_2(self):
        run = subprocess.run(
            [sys.executable, 'make_figures.py', '--input', 'missing-results.json', '--out', 'unused-assets'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertFalse((ROOT / 'unused-assets').exists())

    def test_writer_rejects_empty_results(self):
        with self.assertRaises(ValueError):
            fig.write_figures({'rows': []}, ROOT / 'unused-empty')


if __name__ == '__main__':
    unittest.main()
