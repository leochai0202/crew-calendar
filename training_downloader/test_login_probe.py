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


class SsoStateTests(unittest.TestCase):
    def locator(self, count):
        value = MagicMock()
        value.count.return_value = count
        value.nth.return_value.is_visible.return_value = True
        return value

    def page(self, url, texts=(), form=False):
        page = MagicMock()
        page.url = url
        page.is_closed.return_value = False
        page.locator.return_value = self.locator(int(form))
        page.get_by_role.return_value = self.locator(0)
        content = list(texts)
        def lookup(pattern, exact=False):
            matches = [text for text in content if (
                bool(pattern.search(text)) if hasattr(pattern, "search") else
                text == pattern if exact else pattern in text)]
            return self.locator(len(matches))
        page.get_by_text.side_effect = lookup
        page.test_content = content
        return page

    def test_login_callback_path_is_not_a_login_page(self):
        for url in ("https://spring.yidianzhishi.com/api/v1/sso/ch/login/pc?ticket=synthetic-secret",
                    "https://cas.9cair.com/login?service=synthetic-secret",
                    "https://m.yidianzhishi.com/#!/login"):
            with self.subTest(url=url.split('?')[0]):
                state = probe.course_observation(self.page(url))
                self.assertFalse(state["login_required"])
                self.assertFalse(state["course_content_visible"])

    def test_course_url_alone_does_not_prove_access(self):
        state = probe.course_observation(self.page(probe.COURSE))
        self.assertTrue(state["on_target_course"])
        self.assertFalse(state["course_content_visible"])

    def test_content_with_login_in_query_is_still_content(self):
        page = self.page(probe.COURSE + "&return=/login", [probe.TARGET])
        self.assertTrue(probe.course_observation(page)["course_content_visible"])

    def test_visible_credentials_qr_or_prompt_requires_auth(self):
        for form, text in ((True, ""), (False, "扫码登录"), (False, "请先登录")):
            page = self.page("https://cas.9cair.com/login", [text], form)
            state = probe.course_observation(page)
            self.assertTrue(state["login_page_visible"])
            self.assertFalse(state["course_content_visible"])

    def test_content_behind_login_overlay_is_not_success(self):
        state = probe.course_observation(self.page(probe.COURSE, [probe.TARGET, "请先登录"]))
        self.assertFalse(state["course_content_visible"])

    def test_wait_allows_callback_to_finish(self):
        page = self.page("https://spring.yidianzhishi.com/api/v1/sso/ch/login/pc")
        context = Mock(pages=[page])
        def redirect(_):
            page.url = probe.COURSE
            page.test_content.append(probe.TARGET)
        page.wait_for_timeout.side_effect = redirect
        _, state = probe.wait_for_course_state(page, context, [page], probe.SsoDiagnostics(), timeout_ms=1000)
        self.assertTrue(state["course_content_visible"])
        page.goto.assert_not_called()

    def test_wait_does_not_stop_at_transient_login_ui(self):
        page = self.page("https://cas.9cair.com/login", ["扫码登录"])
        def redirect(_):
            page.url = probe.COURSE
            page.test_content[:] = [probe.TARGET]
        page.wait_for_timeout.side_effect = redirect
        _, state = probe.wait_for_course_state(page, Mock(pages=[page]), [page], probe.SsoDiagnostics(), timeout_ms=1000)
        self.assertTrue(state["course_content_visible"])

    def test_pending_callback_stays_unconfirmed(self):
        page = self.page("https://spring.yidianzhishi.com/api/v1/sso/ch/login/pc")
        context = Mock(pages=[page])
        report = {}
        _, state = probe.open_course_through_site(page, context, report)
        self.assertFalse(state["login_required"])
        self.assertFalse(state["course_content_visible"])
        page.goto.assert_called_once_with(probe.COURSE, wait_until="domcontentloaded", timeout=60_000)
        self.assertIn("TRANSITION_TIMEOUT", [event["stage"] for event in report["sso_diagnostics"]])

    def test_existing_cas_login_form_is_not_submitted(self):
        page = self.page("https://cas.9cair.com/login", form=True)
        report = {}
        _, state = probe.open_course_through_site(page, Mock(pages=[page]), report)
        self.assertTrue(state["login_required"])
        page.get_by_role.assert_not_called()
        page.locator.return_value.nth.return_value.fill.assert_not_called()

    def sso_control(self, page, *, role="link", label="企业登录", visible=True,
                    href="https://cas.9cair.com/login?service=site-provided",
                    button_type="button", implicit_submit=False, count=1):
        controls = self.locator(count)
        control = controls.nth.return_value
        control.is_visible.return_value = visible
        control.get_attribute.side_effect = lambda name: href if name == "href" else button_type
        control.evaluate.return_value = implicit_submit
        page.get_by_role.side_effect = lambda requested_role, name: (
            controls if requested_role == role and name.fullmatch(label) else self.locator(0))
        return control

    def test_fifth_run_visible_form_still_uses_unique_safe_sso_entry(self):
        for role in ("link", "button"):
            with self.subTest(role=role):
                page = self.page("https://m.yidianzhishi.com/#!/login", form=True)
                control = self.sso_control(page, role=role)
                def finish(**kwargs):
                    page.url = probe.COURSE
                    page.locator.return_value.count.return_value = 0
                    page.test_content[:] = [probe.TARGET]
                control.click.side_effect = finish
                report = {"cp_authenticated": True, "email_otp_received": True}
                _, state = probe.open_course_through_site(page, Mock(pages=[page]), report)
                self.assertTrue(state["course_content_visible"])
                self.assertTrue(report["sso_handoff_attempted"])
                self.assertEqual(report["sso_entry_source"], "VISIBLE_SITE_LOGIN_ENTRY")
                self.assertNotIn("sso_entry_status", report)
                control.click.assert_called_once_with(timeout=10_000)
                page.locator.return_value.nth.return_value.fill.assert_not_called()
                page.locator.return_value.nth.return_value.press.assert_not_called()
                page.goto.assert_called_once_with(probe.COURSE, wait_until="domcontentloaded", timeout=60_000)

    def test_visible_form_with_no_safe_unique_sso_reports_entry_not_found(self):
        cases = [{"label": "登录"}, {"role": "button", "label": "登录"},
                 {"role": "button", "label": "获取验证码"}, {"visible": False},
                 {"href": "https://unrelated.invalid/sso"},
                 {"href": "https://spring.yidianzhishi.com/logout"},
                 {"count": 2}, {"count": 0},
                 {"role": "button", "button_type": "submit"},
                 {"role": "button", "button_type": None, "implicit_submit": True}]
        for case in cases:
            with self.subTest(case=case):
                page = self.page("https://m.yidianzhishi.com/#!/login", form=True)
                control = self.sso_control(page, **case)
                report = {}
                _, state = probe.open_course_through_site(page, Mock(pages=[page]), report)
                self.assertTrue(state["login_form_visible"])
                self.assertEqual(report["sso_entry_status"], "SSO_ENTRY_NOT_FOUND")
                self.assertFalse(report["sso_handoff_attempted"])
                control.click.assert_not_called()
                page.locator.return_value.nth.return_value.fill.assert_not_called()
                page.locator.return_value.nth.return_value.press.assert_not_called()

    def test_no_entry_final_status_does_not_override_successful_cp_auth(self):
        # Entire probe with synthetic auth/Playwright; no real login or mail IO.
        for has_entry in (False, True):
            with self.subTest(has_entry=has_entry), tempfile.TemporaryDirectory(
                    dir=Path(probe.__file__).resolve().parent, prefix=".sso-offline-") as directory:
                page = self.page("https://m.yidianzhishi.com/#!/login", form=True)
                control = self.sso_control(page, count=int(has_entry))
                context = Mock(pages=[page])
                playwright = MagicMock()
                playwright.chromium.launch_persistent_context.return_value = context
                sync_api = types.ModuleType("playwright.sync_api")
                sync_api.sync_playwright = MagicMock()
                sync_api.sync_playwright.return_value.__enter__.return_value = playwright
                auth, otp = MagicMock(), MagicMock()
                auth.AuthStatus.AUTHENTICATED = "AUTHENTICATED"
                auth.attempt_password_email_login.return_value.status = "AUTHENTICATED"
                modules = {"password_email_auth": auth, "springair_email_otp": otp}
                with patch.object(probe, "preflight", return_value={"status": "READY", "login_attempted": False}), \
                        patch.object(probe, "RUNTIME", Path(directory)), \
                        patch.object(probe.importlib, "import_module", side_effect=modules.__getitem__), \
                        patch.dict(probe.sys.modules, {"playwright.sync_api": sync_api}), \
                        patch.object(probe.sys, "path", list(probe.sys.path)), \
                        patch.object(probe.sys, "dont_write_bytecode", True), \
                        patch.dict(probe.os.environ, {}, clear=True):
                    result = probe.run_probe()
                self.assertTrue(result["cp_authenticated"], result)
                self.assertEqual(result["status"], "SSO_REAUTH_REQUIRED" if has_entry else "SSO_ENTRY_NOT_FOUND")
                self.assertEqual(result["course_access"], "NOT_CONFIRMED")
                self.assertEqual(result["sso_handoff_attempted"], has_entry)
                self.assertEqual(control.click.call_count, int(has_entry))
                auth.attempt_password_email_login.assert_called_once()
                otp.SpringAirEmailOtpReader.from_environment.return_value.connect.assert_not_called()
                context.close.assert_called_once()
                page.locator.return_value.nth.return_value.fill.assert_not_called()

    def test_visible_form_does_not_override_permission_denial(self):
        page = self.page("https://m.yidianzhishi.com/#!/login", ["无权访问"], form=True)
        report = {}
        _, state = probe.open_course_through_site(page, Mock(pages=[page]), report)
        self.assertTrue(state["access_denied"])
        page.get_by_role.assert_not_called()
        self.assertNotIn("sso_entry_status", report)

    def test_unique_real_site_link_is_clicked_once_without_constructing_url(self):
        page = self.page("https://m.yidianzhishi.com/#!/login", ["请先登录"])
        link = self.locator(1)
        link.nth.return_value.get_attribute.return_value = "https://cas.9cair.com/login?service=site-provided"
        page.get_by_role.side_effect = lambda role, **kwargs: link if role == "link" else self.locator(0)
        def finish(**kwargs):
            page.url = probe.COURSE
            page.test_content[:] = [probe.TARGET]
        link.nth.return_value.click.side_effect = finish
        report = {}
        _, state = probe.open_course_through_site(page, Mock(pages=[page]), report)
        self.assertTrue(state["course_content_visible"])
        self.assertEqual(report["sso_entry_source"], "VISIBLE_SITE_LOGIN_ENTRY")
        link.nth.return_value.click.assert_called_once_with(timeout=10_000)
        page.goto.assert_called_once_with(probe.COURSE, wait_until="domcontentloaded", timeout=60_000)

    def test_external_or_ambiguous_login_entries_are_not_used(self):
        page = self.page("https://m.yidianzhishi.com/#!/login")
        links = self.locator(1)
        links.nth.return_value.get_attribute.return_value = "https://unrelated.invalid/login"
        page.get_by_role.side_effect = lambda role, **kwargs: links if role == "link" else self.locator(0)
        self.assertIsNone(probe.visible_site_login_entry(page))
        links.count.return_value = 2
        links.nth.return_value.get_attribute.return_value = "https://cas.9cair.com/login"
        self.assertIsNone(probe.visible_site_login_entry(page))
        links.nth.return_value.click.assert_not_called()

    def test_generic_login_submit_cannot_start_another_otp_flow(self):
        page = self.page("https://m.yidianzhishi.com/#!/login")
        button = self.locator(1)
        button.nth.return_value.get_attribute.return_value = "submit"
        for label in ("登录", "统一认证登录", "获取验证码"):
            with self.subTest(label=label):
                page.get_by_role.side_effect = lambda role, name: button if role == "button" and name.fullmatch(label) else self.locator(0)
                self.assertIsNone(probe.visible_site_login_entry(page))
        button.nth.return_value.click.assert_not_called()

    def test_popup_course_content_is_observed_in_same_context(self):
        original = self.page("https://m.yidianzhishi.com/#!/login", ["请先登录"])
        popup = self.page(probe.COURSE, [probe.TARGET])
        selected, state = probe.wait_for_course_state(original, Mock(pages=[original, popup]), [original], probe.SsoDiagnostics(), timeout_ms=0)
        self.assertIs(selected, popup)
        self.assertTrue(state["course_content_visible"])

    def test_navigation_diagnostics_are_bounded_and_never_contain_urls(self):
        page = Mock()
        diagnostics = probe.SsoDiagnostics()
        diagnostics.watch(page)
        listener = page.on.call_args.args[1]
        request = Mock(frame=page.main_frame)
        request.is_navigation_request.return_value = True
        response = Mock(request=request, status=302,
                        url="https://spring.yidianzhishi.com/api/v1/sso/ch/login/pc?ticket=synthetic-secret")
        listener(response)
        self.assertEqual(diagnostics.events, [{"stage": "TRAINING_CALLBACK",
            "domain_category": "TRAINING_TENANT", "http_status": 302, "login_page_visible": None}])
        self.assertTrue(diagnostics.handoff_seen)
        self.assertNotIn("synthetic-secret", str(diagnostics.events))
        self.assertNotIn("https://", str(diagnostics.events))
        response.body.assert_not_called()
        for i in range(100):
            diagnostics.record("OBSERVING", "TRAINING_MOBILE", login_visible=bool(i % 2))
        self.assertLessEqual(len(diagnostics.events), 40)

    def test_xhr_and_subframes_are_not_logged(self):
        page = Mock()
        diagnostics = probe.SsoDiagnostics()
        diagnostics.watch(page)
        listener = page.on.call_args.args[1]
        request = Mock(frame=page.main_frame)
        request.is_navigation_request.return_value = False
        listener(Mock(request=request))
        request.is_navigation_request.return_value = True
        request.frame = Mock()
        listener(Mock(request=request))
        self.assertEqual(diagnostics.events, [])


if __name__ == "__main__":
    unittest.main()
