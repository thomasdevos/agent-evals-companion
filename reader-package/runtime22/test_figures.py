import re
import unittest
from pathlib import Path
import figures

ROOT = Path(__file__).resolve().parent


class FigureTests(unittest.TestCase):
    def test_negative_z_clamped(self):
        self.assertIsNone(figures.clamped_z(None))
        self.assertEqual(figures.clamped_z(-1.2), 0.0)
        self.assertEqual(figures.clamped_z(2.5), 2.5)
        raw = [row['z'] for row in figures.series(False) if row['z'] is not None]
        self.assertTrue(any(value < 0 for value in raw))
        self.assertTrue(all(figures.clamped_z(value) >= 0 for value in raw))

    def test_figure_22_1_axis_and_points(self):
        figures.main()
        text = (ROOT / 'assets' / 'figure-22-1-z.svg').read_text()
        self.assertIn('Figure 22.1', text)
        self.assertIn('z score (negative values clamped to 0)', text)
        pairs = re.findall(
            r'data-series="[^"]+" data-day="\d+" data-raw="([^"]+)" data-z="([^"]+)"', text)
        self.assertTrue(pairs)
        self.assertTrue(any(float(raw) < 0 and float(plotted) == 0 for raw, plotted in pairs))
        self.assertTrue(all(float(plotted) >= 0 for _, plotted in pairs))
        cusum = (ROOT / 'assets' / 'cusum.svg').read_text()
        self.assertIn('Missing days hold the CUSUM state', cusum)
        self.assertIn('threshold 5', cusum)


if __name__ == '__main__':
    unittest.main()
