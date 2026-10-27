import subprocess
import sys
import unittest
from pathlib import Path
from chapter24 import figures
from chapter24.programme import run

ROOT = Path(__file__).resolve().parents[1]


def prefix_cents(report, label, case_ids):
    by = {row['task_id']: row for row in report['baselines'][label]['cost_rows']}
    return sum(row['request_cents'] + row['labelling_cents'] + row['investigation_cents']
               + row['infrastructure_cents'] for case_id in case_ids for row in (by[case_id],))


class FigureTests(unittest.TestCase):
    def test_frontier_matches_repair_account(self):
        report = run('repair')
        text = figures.frontier_svg(report)
        direct = report['baselines']['direct']['account']['scenario_total_cents']
        retry = report['baselines']['bounded-retry']['account']['scenario_total_cents']
        frequent = report['selected']
        self.assertGreater(direct, retry)
        self.assertIn(f'data-policy="direct" data-suite="full" data-cases="{len(figures.order_of(report))}" data-cents="{direct}"', text)
        self.assertIn(f'data-policy="bounded-retry" data-suite="full" data-cases="{len(figures.order_of(report))}" data-cents="{retry}"', text)
        self.assertIn(f'data-policy="direct" data-suite="frequent" data-cases="{len(frequent)}" data-cents="{prefix_cents(report, "direct", frequent)}"', text)
        self.assertIn('Figure 24.1. Suite cost frontier', text)
        self.assertIn('eligible frequent suite', text)
        destination = ROOT / 'assets' / 'chapter-24' / 'frontier.svg'
        figures.write(report)
        self.assertEqual(destination.read_text(), text)

    def test_module_exits_zero(self):
        run = subprocess.run([sys.executable, '-m', 'chapter24.figures'], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue((ROOT / 'assets' / 'chapter-24' / 'frontier.svg').is_file())


if __name__ == '__main__':
    unittest.main()
