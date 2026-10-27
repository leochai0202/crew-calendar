"""Offline guard and workflow contract checks; no API or browser calls."""
import importlib.util
from pathlib import Path
import re
import io
import contextlib
import json
import ssl
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SPEC = importlib.util.spec_from_file_location("training_guard", Path(__file__).with_name("workflow_guard.py"))
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class WorkflowGuardTests(unittest.TestCase):
    def setUp(self):
        self.env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1",
                    "GITHUB_REPOSITORY": "leochai0202/crew-calendar",
                    "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "123"}

    def get(self, path):
        if path.startswith("/contents/"):
            name = path.split("/")[-1].split("?")[0]
            return {"sha": guard.EXPECTED_WORKFLOWS[name]}
        return {"total_count": 1, "workflow_runs": [{"id": 123}]}

    def test_only_current_run_is_allowed(self):
        self.assertEqual(guard.check_activity(self.get, self.env), "NO_OTHER_ACTIVE_WORKFLOWS")

    def test_active_and_queued_other_runs_block(self):
        for state in guard.ACTIVE_STATES:
            with self.subTest(state=state):
                def get(path):
                    if f"status={state}&" in path:
                        return {"total_count": 1, "workflow_runs": [{"id": 456}]}
                    return self.get(path)
                with self.assertRaisesRegex(guard.GuardError, "OTHER_WORKFLOW_ACTIVE"):
                    guard.check_activity(get, self.env)

    def test_incomplete_api_response_blocks(self):
        def get(path):
            return self.get(path) if path.startswith("/contents/") else {"total_count": 101, "workflow_runs": []}
        with self.assertRaisesRegex(guard.GuardError, "CONCURRENCY_RESULT_INCOMPLETE"):
            guard.check_activity(get, self.env)

    def test_api_failure_blocks(self):
        def unavailable(path):
            raise guard.GuardError("CONCURRENCY_CHECK_UNAVAILABLE")
        with self.assertRaises(guard.GuardError):
            guard.check_activity(unavailable, self.env)

    def test_transport_causes_have_fixed_codes(self):
        cases = [(TimeoutError("private"), "CONCURRENCY_API_TIMEOUT"),
                 (URLError(TimeoutError("private")), "CONCURRENCY_API_TIMEOUT"),
                 (ssl.SSLError("private"), "CONCURRENCY_API_TLS_ERROR"),
                 (URLError("private"), "CONCURRENCY_API_NETWORK_ERROR"),
                 (json.JSONDecodeError("private", "private", 0), "CONCURRENCY_API_INVALID_JSON"),
                 (RuntimeError("private"), "CONCURRENCY_UNEXPECTED_ERROR")]
        for status, expected in ((401, "401"), (403, "403"), (429, "429"), (503, "5XX"), (302, "OTHER")):
            cases.append((HTTPError("https://private.invalid/?token=private", status, "private", {}, None),
                          "CONCURRENCY_API_HTTP_" + expected))
        for exc, code in cases:
            with self.subTest(code=code):
                self.assertEqual(guard.transport_failure(exc), code)

    def test_failure_keeps_check_stage_but_no_exception_details(self):
        def get(path):
            if "status=queued&" in path:
                raise URLError(TimeoutError("synthetic-secret"))
            return self.get(path)
        with self.assertRaises(guard.GuardError) as captured:
            guard.check_activity(get, self.env)
        self.assertEqual(guard.safe_failure(captured.exception), {
            "concurrency_failure_reason": "CONCURRENCY_API_TIMEOUT",
            "concurrency_check": "ACTIVE_RUNS_QUEUED"})
        self.assertNotIn("synthetic-secret", str(captured.exception))

    def test_main_does_not_log_arbitrary_exception_text(self):
        output = io.StringIO()
        with patch.object(guard, "check_activity", side_effect=RuntimeError("synthetic-secret")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(guard.main(), 2)
        self.assertIn("CONCURRENCY_UNEXPECTED_ERROR", output.getvalue())
        self.assertNotIn("synthetic-secret", output.getvalue())

    def test_unknown_reason_and_stage_are_replaced(self):
        report = guard.safe_failure(guard.GuardError("synthetic-secret", "private-url"))
        self.assertEqual(report, {"concurrency_failure_reason": "CONCURRENCY_UNEXPECTED_ERROR",
                                  "concurrency_check": "UNKNOWN"})

    def test_malformed_runs_are_unverifiable(self):
        for runs in ([None], [{"id": "123"}]):
            with self.subTest(runs=runs):
                def get(path):
                    return self.get(path) if path.startswith("/contents/") else {"total_count": 1, "workflow_runs": runs}
                with self.assertRaisesRegex(guard.GuardError, "CONCURRENCY_RESULT_INCOMPLETE"):
                    guard.check_activity(get, self.env)

    def test_changed_production_mutex_requires_review(self):
        with self.assertRaisesRegex(guard.GuardError, "PRODUCTION_WORKFLOW_CHANGED_REVIEW_REQUIRED"):
            guard.check_activity(lambda path: {"sha": "changed"}, self.env)

    def test_reruns_nonmanual_and_other_refs_block(self):
        for field, value in (("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_EVENT_NAME", "push"),
                             ("GITHUB_REF", "refs/heads/test")):
            with self.subTest(field=field):
                with self.assertRaisesRegex(guard.GuardError, "MANUAL_FIRST_ATTEMPT_REQUIRED"):
                    guard.check_activity(self.get, {**self.env, field: value})

    def test_workflow_is_manual_readonly_and_isolated(self):
        text = (Path(__file__).resolve().parent.parent / ".github/workflows/training-login-check.yml").read_text(encoding="utf-8")
        triggers = text.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertEqual(re.findall(r"^  (\w+):", triggers, re.M), ["workflow_dispatch"])
        self.assertIn("  group: crew-calendar\n  cancel-in-progress: false\n  queue: max", text)
        self.assertIn("  contents: read\n  actions: read", text)
        self.assertNotIn("uses:", text)  # No checkout/cache/upload or third-party actions.
        self.assertNotIn("contents: write", text)
        self.assertNotIn("actions: write", text)
        self.assertNotIn("CREW_STORAGE_STATE_B64", text)
        self.assertNotIn("CREW_PERSISTENT_PROFILE_DIR", text)
        self.assertNotIn("CREW_AUTH_BACKUP_PATH", text)
        self.assertNotIn("python crew_calendar", text)
        secrets = re.findall(r"secrets\.([A-Z_]+)", text)
        self.assertCountEqual(secrets, ["CREW_USERNAME", "CREW_PASSWORD", "IMAP_EMAIL", "IMAP_AUTH_CODE"])
        self.assertEqual(text.count("login_probe.py --run"), 1)
        self.assertIn("TRAINING_REQUIRE_GUARD: '1'", text)
        self.assertIn("CLEANUP_PATH_INVALID", text)
        cleanup = Path(__file__).with_name("cleanup_training.ps1").read_text(encoding="utf-8")
        self.assertIn("CLEANUP_REPARSE_POINT_REFUSED", cleanup)
        self.assertIn("CLEANUP_OWNER_INVALID", cleanup)
        self.assertIn("Get-TrainingCleanupPlan -Root $Root -TempBase $TempBase -Id $Id", cleanup)
        self.assertIn("test_cleanup_training.ps1", text)


if __name__ == "__main__":
    unittest.main()
