"""Offline tests only; no account/session access."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import live_save


class LiveSaveTests(unittest.TestCase):
    def test_invalid_session_never_selects_an_arbitrary_path(self):
        for value in ('', '../private-delivery', 'A'*32, '123'):
            with patch.dict(os.environ, {'TRAINING_LIVE_SESSION': value}):
                with self.assertRaisesRegex(RuntimeError, 'LIVE_SESSION_INVALID'):
                    live_save.control_directory()

    def test_requires_existing_dedicated_mailbox(self):
        with tempfile.TemporaryDirectory() as root, patch.object(live_save, 'CONTROL_BASE', Path(root)), \
                patch.dict(os.environ, {'TRAINING_LIVE_SESSION': 'a'*32}):
            with self.assertRaisesRegex(RuntimeError, 'LIVE_CONTROL_NOT_PREPARED'):
                live_save.control_directory()
            expected = Path(root)/('live-control-'+'a'*32)
            expected.mkdir()
            self.assertEqual(live_save.control_directory(), expected)

    def test_abort_closes_loop_without_another_login_or_save(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            (directory/'request.json').write_text(json.dumps({'id':1, 'operation':'abort'}))
            page = Mock()
            page.is_closed.return_value = False
            page.frames = []
            context = Mock(pages=[page])
            report = {}
            with patch.dict(os.environ, {'TRAINING_CAPTURE_ALLOWED': '1'}), \
                    patch.object(live_save, 'control_directory', return_value=directory):
                result = live_save.run_live_save(page, context, directory, [], Mock(), report)
            self.assertEqual(result['status'], 'LIVE_SAVE_STOPPED')
            self.assertEqual(json.loads((directory/'response.json').read_text())['status'], 'STOPPED')
            page.goto.assert_not_called()
            page.pdf.assert_not_called()


if __name__ == '__main__':
    unittest.main()
