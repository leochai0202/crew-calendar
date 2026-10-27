"""Offline safety checks. No real credentials, browsers, mail, or network."""
import contextlib
import importlib.util
import io
import os
import types
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

SPEC = importlib.util.spec_from_file_location("training_login_probe", Path(__file__).with_name("login_probe.py"))
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class PresenceOnly(dict):
    def __getitem__(self, key):
        raise AssertionError("Credential values must not be read by preflight")

    def get(self, *args):
        raise AssertionError("Credential values must not be read by preflight")


class LoginProbeSafetyTests(unittest.TestCase):
    def test_preflight_checks_names_without_reading_values(self):
        env = PresenceOnly({name: None for name in probe.REQUIRED_ENV})
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(probe.os, "environ", env):
                result = probe.preflight(Path(directory))
        self.assertEqual(result["missing_environment_names"], [])
        self.assertEqual(result["status"], "SOURCE_NOT_READY")
        self.assertFalse(result["login_attempted"])

    def test_missing_environment_blocks_import_and_profile_creation(self):
        with patch.object(probe, "preflight", return_value={"status": "ENVIRONMENT_MISSING"}):
            with patch.object(probe.importlib, "import_module") as importer:
                with patch.object(probe.Path, "mkdir") as mkdir:
                    result = probe.run_probe()
        self.assertEqual(result["status"], "ENVIRONMENT_MISSING")
        importer.assert_not_called()
        mkdir.assert_not_called()

    def test_unreviewed_source_is_rejected_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "password_email_auth.py").write_text("raise RuntimeError('DO_NOT_EXECUTE')\n")
            with patch.object(probe.os, "environ", PresenceOnly(dict.fromkeys(probe.REQUIRED_ENV))):
                result = probe.preflight(root)
        self.assertEqual(result["unreviewed_source_files"], ["password_email_auth.py"])
        self.assertEqual(result["status"], "SOURCE_NOT_READY")

    def test_second_iteration_is_stopped_before_another_email_request(self):
        original = Mock()
        wrapper = probe.SingleRequestReader(original)
        requests = 0
        with self.assertRaisesRegex(RuntimeError, "TRAINING_EMAIL_RETRY_DISABLED"):
            # The reviewed production function connects before each request click.
            for _ in range(2):
                wrapper.connect()
                requests += 1
        self.assertEqual(requests, 1)
        original.connect.assert_called_once_with()
        wrapper.wait_for_new_otp(12, not_before="test-boundary")
        original.wait_for_new_otp.assert_called_once_with(12, not_before="test-boundary")
        wrapper.close()
        original.close.assert_called_once_with()

    def test_auth_output_is_discarded(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            with probe.quiet_auth():
                print("SYNTHETIC_PRIVATE_VALUE")
                print("SYNTHETIC_PRIVATE_VALUE", file=probe.sys.stderr)
        self.assertEqual(output.getvalue(), "")

    def test_second_guard_preserves_safe_reason_and_still_raises(self):
        failure = {"concurrency_failure_reason": "CONCURRENCY_API_TIMEOUT",
                   "concurrency_check": "ACTIVE_RUNS_QUEUED"}
        module = types.ModuleType("workflow_guard")
        module.check_activity = Mock(side_effect=RuntimeError("synthetic-private-value"))
        module.safe_failure = Mock(return_value=failure)
        report = {"login_attempted": False, "cp_authenticated": False}
        with patch.dict(probe.sys.modules, {"workflow_guard": module}):
            with self.assertRaisesRegex(RuntimeError, "^CONCURRENCY_CHECK_BLOCKED$"):
                probe.check_before_auth(report)
        self.assertFalse(report["login_attempted"])
        self.assertFalse(report["cp_authenticated"])
        self.assertEqual(report["concurrency_failure_reason"], "CONCURRENCY_API_TIMEOUT")
        self.assertNotIn("synthetic-private-value", str(report))

    def test_second_guard_import_failure_is_distinct(self):
        report = {"login_attempted": False}
        with patch.dict(probe.sys.modules, {"workflow_guard": None}):
            with self.assertRaises(RuntimeError):
                probe.check_before_auth(report)
        self.assertEqual(report["concurrency_failure_reason"], "CONCURRENCY_GUARD_IMPORT_FAILED")
        self.assertFalse(report["login_attempted"])

    def viewer_fixture(self, before, after):
        page = MagicMock()
        page.get_by_role.return_value.count.return_value = 1
        page.locator.return_value.count.return_value = 1
        page.get_by_text.return_value.count.return_value = 1
        frame = Mock()
        frame.evaluate.side_effect = [before, after]
        page.frames = [frame]
        context = Mock()
        context.pages = [page]
        return page, context

    def test_viewer_requires_a_new_loaded_document(self):
        document = {"count": 29, "fingerprint": "synthetic-existing"}
        page, context = self.viewer_fixture(document, document)
        evidence = probe.inspect_course_and_viewer(page, context)
        self.assertFalse(evidence["target_pdf_accessible"])
        self.assertFalse(evidence["pdf_29_pages_confirmed"])

    def test_viewer_confirms_new_document_metadata_without_export(self):
        page, context = self.viewer_fixture(None, {"count": 29, "fingerprint": "synthetic-new"})
        evidence = probe.inspect_course_and_viewer(page, context)
        self.assertTrue(evidence["target_pdf_accessible"])
        self.assertTrue(evidence["pdf_29_pages_confirmed"])
        self.assertNotIn("fingerprint", evidence)
        page.get_by_text.return_value.nth.return_value.click.assert_called_once()

    def test_ambiguous_resource_is_not_opened(self):
        page, context = self.viewer_fixture(None, None)
        page.get_by_text.return_value.count.return_value = 2
        evidence = probe.inspect_course_and_viewer(page, context)
        self.assertEqual(evidence["viewer_check"], "TARGET_LINK_NOT_UNIQUE")
        page.get_by_text.return_value.nth.return_value.click.assert_not_called()

    def test_reviewed_production_function_cannot_request_twice(self):
        # Runs in the staged workflow sources; old local checkouts skip safely.
        source = probe.ROOT / "password_email_auth.py"
        if not source.is_file():
            self.skipTest("Reviewed production sources are absent in this checkout")
        readiness = probe.preflight()
        if readiness["missing_source_files"] or readiness["unreviewed_source_files"]:
            self.skipTest("Production dependency versions require review")
        with patch.object(probe.sys, "path", [str(probe.ROOT), *probe.sys.path]):
            auth = probe.importlib.import_module("password_email_auth")
        page = MagicMock()
        page.url = "https://cas.9cair.com/login"
        request = page.locator.return_value.locator.return_value
        request.is_enabled.return_value = True
        original_reader = Mock()
        wrapper = probe.SingleRequestReader(original_reader)
        observation = auth.AuthObservation(auth.AuthStatus.LOGIN_REQUIRED, auth.AuthSignals())
        with patch.dict(os.environ, dict.fromkeys(probe.REQUIRED_ENV, "synthetic-test-only")):
            with patch.object(auth, "prepare_login_page_for_auth_method", return_value=observation), \
                 patch.object(auth, "_unique_visible", side_effect=lambda locator: locator), \
                 patch.object(auth, "_select_email_verification"), \
                 patch.object(auth, "email_request_accepted", return_value=False), \
                 probe.quiet_auth():
                result = auth.attempt_password_email_login(page, reader_factory=lambda: wrapper)
        self.assertEqual(result.status, auth.AuthStatus.LOGIN_REQUIRED)
        request.click.assert_called_once()
        original_reader.connect.assert_called_once()
        original_reader.close.assert_called_once()
        original_reader.wait_for_new_otp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
