"""Consumer regressions: resealed malformed metadata must precede every effect."""
import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import cassettes as c
import durable as d
import capture_store as s

class ImportSchemaTests(unittest.TestCase):
    def test_disk_metadata_before_effects(self):
        bads = [('elapsed_local_seconds', x) for x in (-1, True, False, 'invented', None, [], {}, float('inf'), float('-inf'), float('nan'))]
        bads += [('timestamp', x) for x in (None, [], {}, 1, True)]
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for provider in c.ADAPTERS:
                baseline = d.execute(root/provider, d.read(c.ROOT/'vendor/chapter02/cards/full.json'), provider)
                dest = root/(provider+'-export')
                d.export(root/provider, dest)
                manifest = d.read(dest/'manifest.json')
                seal = d.read(dest/'export-complete.json')
                def save(rows):
                    # JSON nonfinite tokens are deliberately exercised at the disk boundary.
                    (dest/'calls.jsonl').write_text(''.join(json.dumps(r, sort_keys=True, separators=(',', ':'))+'\n' for r in rows))
                    try:
                        digest = c.digest(rows)
                    except ValueError:
                        digest = '0'*64
                    manifest['records_sha256'] = digest
                    seal['calls_sha256'] = digest
                    s.atomic_json(dest/'manifest.json', manifest)
                    s.atomic_json(dest/'export-complete.json', seal)
                for field, bad in bads:
                    with self.subTest(provider=provider, field=field, value=repr(bad)):
                        rows = copy.deepcopy(baseline['records'])
                        rows[-1][field] = bad  # corrupt late row, preserve valid first refund
                        save(rows)
                        with self.assertRaises(ValueError):
                            c.load(dest/'calls.jsonl', manifest)
                        with patch.object(d.money, 'execute', wraps=d.money.execute) as execute:
                            with self.assertRaises(ValueError):
                                d.replay(dest)
                            self.assertEqual(execute.call_count, 0)
                for elapsed in (0, 0.0, 0.125, 10):
                    rows = copy.deepcopy(baseline['records'])
                    for row in rows:
                        row['elapsed_local_seconds'] = elapsed
                        row['timestamp'] = ''  # schema is type-only, not a date format
                    save(rows)
                    c.load(dest/'calls.jsonl', manifest)
                    result = d.replay(dest)['result']
                    self.assertEqual(result['status'], 'PASS')
                    self.assertEqual(result['after']['refunds'], [['A100', 4200]])
                unknown = root/(provider+'-unknown')
                d.execute(unknown, d.read(c.ROOT/'vendor/chapter02/cards/full.json'), provider, callback=c.Authored(provider, 'unknown'))
                d.export(unknown, root/(provider+'-unknown-export'))
                result = d.replay(root/(provider+'-unknown-export'))['result']
                self.assertEqual(result['status'], 'AGENT_ERROR')
                self.assertEqual(result['after']['refunds'], [])

if __name__ == '__main__':
    import sys
    print('child optimize:', sys.flags.optimize, flush=True)
    unittest.main(verbosity=2)
