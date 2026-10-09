"""Producer F1 regression: byte completeness is not durability acknowledgement.
Derived from the preserved independent completion replace-then-raise observation.
All checks remain active under python -O; no live provider calls.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import integration as i
from demo import envelope
from native import SQLiteExecutor, snapshot


class CompletionExportPolicy(unittest.TestCase):
    def test_published_marker_explicit_export_stopped_admission(self):
        for provider in ('responses', 'messages'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                session = i.Session(root/'capture', provider, SQLiteExecutor(root/'db'))
                session.turn(lambda _: envelope(provider))
                session.turn(lambda _: envelope(provider, True))
                real = os.replace
                def replace(src, dst):
                    real(src, dst)
                    if Path(dst).name == 'complete.json':
                        raise OSError('published marker; durability acknowledgement failed')
                with patch.object(i.storage.os, 'replace', side_effect=replace):
                    with self.assertRaisesRegex(OSError, 'acknowledgement failed'):
                        session.finish()
                self.assertTrue(session.stopped)
                self.assertTrue(session.budget.blocked)
                self.assertFalse((root/'out').exists())
                saved = {p.name: p.read_bytes() for p in (root/'capture').iterdir()}
                self.assertFalse(i.read(root/'capture'/'complete.json')['accounting']['blocked'])
                callbacks = []
                with self.assertRaisesRegex(ValueError, 'session_stopped'):
                    session.turn(lambda request: callbacks.append(request))
                with self.assertRaises(ValueError):
                    session.finish()
                self.assertEqual(callbacks, [])
                self.assertEqual(session.executor.calls, 2)
                self.assertEqual(snapshot(session.executor.path)['refunds'], [['A100', 4200]])
                self.assertEqual(i.export(root/'capture', root/'out'), 6)
                self.assertEqual(i.replay(root/'out')['entries'], 6)
                self.assertEqual(saved, {p.name:p.read_bytes() for p in (root/'capture').iterdir()})
                self.assertTrue(session.stopped)
                self.assertTrue(session.budget.blocked)
                print('BYTE_COMPLETE_EXPLICIT_EXPORT', provider,
                      'entries=6 callbacks_after_stop=0 executor_calls=2 live_blocked=true saved_blocked=false', flush=True)

    def test_unpublished_marker_is_not_exportable(self):
        for provider in ('responses', 'messages'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                session = i.Session(root/'capture', provider, SQLiteExecutor(root/'db'))
                session.turn(lambda _: envelope(provider))
                session.turn(lambda _: envelope(provider, True))
                real = os.replace
                def replace(src, dst):
                    if Path(dst).name == 'complete.json':
                        raise OSError('before publication')
                    return real(src, dst)
                with patch.object(i.storage.os, 'replace', side_effect=replace):
                    with self.assertRaises(OSError):
                        session.finish()
                self.assertTrue(session.stopped)
                self.assertTrue(session.budget.blocked)
                with self.assertRaises((ValueError, OSError)):
                    i.export(root/'capture', root/'out')
                self.assertFalse((root/'out').exists())
                print('UNPUBLISHED_MARKER_EXPORT_REFUSED', provider, flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
