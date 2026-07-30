import os
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import crew_auth_session as auth
import crew_calendar_main as calendar


class FakePage:
    def __init__(self) -> None:
        self.default_timeout = None
        self.navigation_timeout = None

    def set_default_timeout(self, timeout: int) -> None:
        self.default_timeout = timeout

    def set_default_navigation_timeout(self, timeout: int) -> None:
        self.navigation_timeout = timeout


class MissionBodyLocator:
    def __init__(self, page) -> None:
        self.page = page

    def inner_text(self, timeout: int) -> str:
        return self.page.body_text


class MissionNavigationCandidate:
    def __init__(
        self,
        page,
        *,
        visible: bool,
        y: int,
        opens_list: bool = False,
    ) -> None:
        self.page = page
        self.visible = visible
        self.y = y
        self.opens_list = opens_list
        self.clicked = 0
        self.scrolled = 0

    def is_visible(self) -> bool:
        return self.visible

    def bounding_box(self):
        if not self.visible:
            return None
        return {"x": 0, "y": self.y, "width": 100, "height": 30}

    def scroll_into_view_if_needed(self) -> None:
        self.scrolled += 1

    def click(self, timeout: int) -> None:
        self.clicked += 1
        if self.opens_list:
            self.page.body_text = "我的任务\n07月31日 周五"


class MissionNavigationCandidates:
    def __init__(self, candidates) -> None:
        self.candidates = candidates

    def count(self) -> int:
        return len(self.candidates)

    def nth(self, index: int):
        return self.candidates[index]


class MissionPage:
    def __init__(self) -> None:
        self.body_text = "首页\n我的任务"
        self.waits: list[int] = []
        self.candidates: list[MissionNavigationCandidate] = []

    def locator(self, selector: str):
        assert selector == "body"
        return MissionBodyLocator(self)

    def get_by_text(self, text: str, *, exact: bool):
        assert text == "我的任务"
        assert exact is True
        return MissionNavigationCandidates(self.candidates)

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False
        self.context: FakeContext | None = None
        self.context_options: dict = {}

    def new_context(self, **options) -> FakeContext:
        self.context_options.update(options)
        if self.context is None:
            self.context = FakeContext()
        return self.context

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_options: list[dict] = []

    def launch(self, **options) -> FakeBrowser:
        self.launch_options.append(options)
        return self.browser


class FakePlaywrightManager:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def install_fake_browser(monkeypatch):
    browser = FakeBrowser()
    manager = FakePlaywrightManager(browser)
    context = FakeContext()
    context_options: dict = {}
    browser.context = context
    browser.context_options = context_options

    monkeypatch.setattr(calendar, "sync_playwright", lambda: manager)

    def fake_create_context(passed_browser, bundle, **options):
        assert passed_browser is browser
        context_options.update(options)
        return context

    monkeypatch.setattr(
        calendar,
        "create_context_from_auth_bundle",
        fake_create_context,
    )
    return manager, browser, context, context_options


def install_valid_bundle(monkeypatch) -> None:
    monkeypatch.setenv("CREW_STORAGE_STATE_B64", "encoded-test-bundle")
    monkeypatch.setattr(
        calendar,
        "decode_auth_bundle",
        lambda encoded: SimpleNamespace(
            storage_state={},
            session_storage={},
        ),
    )


def test_open_mission_page_clicks_top_navigation_and_waits_for_day_list() -> None:
    page = MissionPage()
    hidden = MissionNavigationCandidate(page, visible=False, y=0)
    content = MissionNavigationCandidate(page, visible=True, y=300)
    top_navigation = MissionNavigationCandidate(
        page,
        visible=True,
        y=20,
        opens_list=True,
    )
    page.candidates = [hidden, content, top_navigation]

    calendar.open_mission_page(page)

    assert top_navigation.clicked == 1
    assert top_navigation.scrolled == 1
    assert content.clicked == 0
    assert "07月31日 周五" in page.body_text


def test_open_mission_page_does_not_treat_navigation_text_as_task_list() -> None:
    page = MissionPage()
    navigation = MissionNavigationCandidate(page, visible=True, y=20)
    page.candidates = [navigation]

    with pytest.raises(RuntimeError, match="未能进入任务列表页"):
        calendar.open_mission_page(page)

    assert navigation.clicked == 3


def forbid_legacy_and_processing(monkeypatch, calls: list[str]) -> None:
    def forbidden(name: str):
        def fail(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not be called")

        return fail

    for name in (
        "login",
        "solve_captcha",
        "solve_captcha_with_ddddocr",
        "solve_captcha_with_tesseract",
        "snapshot_existing_calendars",
        "rebuild_airport_indexes",
        "open_mission_page",
        "detect_page_year",
        "collect_day_blocks",
        "create_multi_calendars_from_blocks",
    ):
        monkeypatch.setattr(calendar, name, forbidden(name))


def test_authenticated_status_enters_existing_processing_flow(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    manager, browser, context, context_options = install_fake_browser(
        monkeypatch
    )
    calls: list[str] = []

    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page: (_ for _ in ()).throw(
            AssertionError("valid session must not use QQ IMAP")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy login must not be called")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "solve_captcha",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("OCR must not be called")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "snapshot_existing_calendars",
        lambda: calls.append("snapshot"),
    )
    monkeypatch.setattr(
        calendar,
        "rebuild_airport_indexes",
        lambda: calls.append("rebuild"),
    )
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda page: calls.append("open"),
    )
    monkeypatch.setattr(
        calendar,
        "detect_page_year",
        lambda page: calls.append("year") or 2026,
    )
    monkeypatch.setattr(
        calendar,
        "collect_day_blocks",
        lambda page: calls.append("collect") or ["day-block"],
    )
    monkeypatch.setattr(
        calendar,
        "create_multi_calendars_from_blocks",
        lambda blocks, year: calls.append("create"),
    )

    assert calendar.run() == 0

    assert capsys.readouterr().out == "AUTH_STATUS=AUTHENTICATED\n"
    assert calls == [
        "snapshot",
        "rebuild",
        "open",
        "year",
        "collect",
        "create",
    ]
    assert manager.chromium.launch_options == [{"headless": True}]
    assert context_options == {"viewport": {"width": 1400, "height": 1000}}
    assert context.closed is True
    assert browser.closed is True


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [
        (auth.AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED, 4),
        (auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN, 5),
        (auth.AuthStatus.NETWORK_OR_SITE_ERROR, 6),
    ],
)
def test_non_authenticated_status_never_processes_or_writes_ics(
    status: auth.AuthStatus,
    exit_code: int,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    _, browser, context, _ = install_fake_browser(monkeypatch)
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: auth.AuthObservation(status, auth.AuthSignals()),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page: (_ for _ in ()).throw(
            AssertionError("non-login auth status must not use QQ IMAP")
        ),
    )

    assert calendar.run() == exit_code

    output = capsys.readouterr().out
    assert output.endswith(f"AUTH_STATUS={status.value}\n")
    if status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN:
        assert "LOGIN_ERROR_CATEGORY=LOGIN_RESULT_UNKNOWN" in output
        assert "LOGIN_PAGE_PATH=" in output
        assert "LOGIN_VISIBLE_MISSION_AREA=false" in output
    else:
        assert output == f"AUTH_STATUS={status.value}\n"
    assert calls == []
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context.closed is True
    assert browser.closed is True


@pytest.mark.parametrize("secret", ["", "not-valid-base64"])
def test_missing_or_corrupt_secret_falls_back_without_writing(
    secret: str,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    if secret:
        monkeypatch.setenv("CREW_STORAGE_STATE_B64", secret)
    else:
        monkeypatch.delenv("CREW_STORAGE_STATE_B64", raising=False)
    _, browser, context, context_options = install_fake_browser(monkeypatch)
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
    )

    assert calendar.run() == 3

    assert capsys.readouterr().out == "AUTH_STATUS=LOGIN_REQUIRED\n"
    assert calls == []
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context_options == {"viewport": {"width": 1400, "height": 1000}}
    assert context.closed is True
    assert browser.closed is True


def test_confirmed_login_required_uses_cloud_fallback_then_processes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    install_fake_browser(monkeypatch)
    calls: list[str] = []
    observations = iter(
        [
            auth.AuthObservation(
                auth.AuthStatus.LOGIN_REQUIRED,
                auth.AuthSignals(login_url_hint=True),
            )
        ]
    )
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: next(observations),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page: calls.append("fallback")
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "snapshot_existing_calendars",
        lambda: calls.append("snapshot"),
    )
    monkeypatch.setattr(
        calendar,
        "rebuild_airport_indexes",
        lambda: calls.append("rebuild"),
    )
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda page: calls.append("open"),
    )
    monkeypatch.setattr(calendar, "detect_page_year", lambda page: 2026)
    monkeypatch.setattr(
        calendar,
        "collect_day_blocks",
        lambda page: ["day-block"],
    )
    monkeypatch.setattr(
        calendar,
        "create_multi_calendars_from_blocks",
        lambda blocks, year: calls.append("create"),
    )

    assert calendar.run() == 0
    assert calls == [
        "fallback",
        "snapshot",
        "rebuild",
        "open",
        "create",
    ]


def test_cloud_fallback_uses_fixed_qq_imap_and_secret_phone(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    captured: dict = {}

    class Reader:
        def __init__(self, email, auth_code, *, host, port) -> None:
            captured["reader"] = (email, auth_code, host, port)

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda page, reader, **options: captured.update(options)
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert captured["reader"] == (
        "crew@example.invalid",
        "test-auth-code",
        "imap.qq.com",
        993,
    )
    assert captured["phone_number"] == "13000000000"
    assert captured["allow_manual_slider"] is False
    assert captured["save_diagnostics"] is False
    assert captured["expected_otp_length"] == 6


def test_cloud_fallback_missing_secret_does_not_connect_imap(
    monkeypatch,
) -> None:
    monkeypatch.delenv("CREW_PHONE", raising=False)
    monkeypatch.delenv("IMAP_EMAIL", raising=False)
    monkeypatch.delenv("IMAP_AUTH_CODE", raising=False)
    monkeypatch.setattr(
        calendar,
        "ImapOtpReader",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("missing cloud config must not connect IMAP")
        ),
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.LOGIN_REQUIRED


def test_cloud_slider_requires_additional_verification(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.AdditionalVerificationRequiredError(
                "manual slider required"
            )
        ),
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert (
        observation.status
        == auth.AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED
    )


def test_cloud_toggle_failure_keeps_exact_category_and_closes_reader(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    events: list[str] = []

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def connect(self) -> None:
            events.append("connect")

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.LoginToggleError("ACCOUNT_PANEL_NOT_OPENED")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "登录春秋统一认证",
            "visible_elements": {},
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert events == ["close"]
    assert "LOGIN_ERROR_CATEGORY=ACCOUNT_PANEL_NOT_OPENED" in (
        capsys.readouterr().out
    )


def test_cloud_login_state_timeout_keeps_exact_category(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.LoginPageStateError("LOGIN_PAGE_STATE_TIMEOUT")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "登录春秋统一认证",
            "visible_elements": {},
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert "LOGIN_ERROR_CATEGORY=LOGIN_PAGE_STATE_TIMEOUT" in (
        capsys.readouterr().out
    )


def test_cloud_unknown_writes_only_safe_staged_diagnostic(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    diagnostic_path = tmp_path / "crew-auth-diagnostic.json"
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    monkeypatch.setenv(
        calendar.AUTH_DIAGNOSTIC_PATH_ENV,
        str(diagnostic_path),
    )

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    def fake_login(_page, _reader, **options):
        reporter = options["stage_reporter"]
        reporter(
            "TOGGLE_CANDIDATES_INSPECTED",
            {
                "diagnostic": {
                    "login_badge_count": 2,
                    "badge_icon_count": 2,
                    "visible_badge_icon_count": 1,
                    "eligible_toggle_count": 1,
                    "candidates": [
                        {
                            "index": 0,
                            "visible": False,
                            "bounding_box_exists": False,
                            "display": "none",
                            "visibility": "hidden",
                            "pointer_events": "none",
                            "inside_login_badge": True,
                            "top_right_region": False,
                        }
                    ],
                }
            },
        )
        for stage in (
            "LOGIN_FLOW_STARTED",
            "LOGIN_PAGE_SWITCHED",
            "DYNAMIC_TAB_OPENED",
            "PHONE_FILLED",
            "IMAP_BASELINE_RECORDED",
            "OTP_REQUEST_CLICKED",
            "SLIDER_ABSENT",
        ):
            reporter(stage, {})
        reporter("OTP_MAIL_RECEIVED", {"otp_length": 6})
        for stage in (
            "OTP_FIELD_FILLED",
            "LOGIN_BUTTON_CLICKED",
            "SSO_HANDOFF_REACHED",
            "MISSION_PAGE_REQUESTED",
            "FINAL_PAGE_PROBED",
        ):
            reporter(stage, {})
        return auth.AuthObservation(
            auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
            auth.AuthSignals(),
        )

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        fake_login,
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "统一认证中心",
            "visible_elements": {
                "qr_login_page": False,
                "password_login_tab": True,
                "dynamic_login_tab": True,
                "phone_field": True,
                "otp_request_button": True,
                "otp_field": True,
                "slider": False,
                "mission_area": False,
            },
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    output = capsys.readouterr().out
    assert (
        'LOGIN_TOGGLE_DIAGNOSTIC={"badge_icon_count":2'
        in output
    )
    assert "LOGIN_STAGE=OTP_MAIL_RECEIVED OTP_LENGTH=6" in output
    assert (
        "LOGIN_ERROR_CATEGORY=POST_LOGIN_HANDOFF_INCOMPLETE"
        in output
    )
    assert "LOGIN_PAGE_DOMAIN=cas.9cair.com" in output
    assert "LOGIN_PAGE_PATH=/login" in output
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert payload["last_stage"] == "FINAL_PAGE_PROBED"
    assert payload["error_category"] == "POST_LOGIN_HANDOFF_INCOMPLETE"
    assert payload["auth_status"] == "PAGE_CHANGED_OR_UNKNOWN"
    serialized = json.dumps(payload, ensure_ascii=False)
    for sensitive in (
        "13000000000",
        "crew@example.invalid",
        "test-auth-code",
        "token",
        "cookie",
        "otp_value",
    ):
        assert sensitive not in serialized.lower()


def test_cloud_otp_error_reports_stage_specific_category(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    diagnostic_path = tmp_path / "crew-auth-diagnostic.json"
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    monkeypatch.setenv(
        calendar.AUTH_DIAGNOSTIC_PATH_ENV,
        str(diagnostic_path),
    )

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.OtpError("safe test failure")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "",
            "visible_elements": {},
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert "LOGIN_ERROR_CATEGORY=LOGIN_SWITCH_FAILED" in (
        capsys.readouterr().out
    )
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert payload["error_category"] == "LOGIN_SWITCH_FAILED"


def test_processing_exception_returns_one_and_closes_resources(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    _, browser, context, _ = install_fake_browser(monkeypatch)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(),
        ),
    )
    monkeypatch.setattr(calendar, "snapshot_existing_calendars", lambda: None)
    monkeypatch.setattr(calendar, "rebuild_airport_indexes", lambda: None)
    monkeypatch.setenv("IMAP_AUTH_CODE", "secret-auth-code")
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda page: (_ for _ in ()).throw(
            RuntimeError("page changed secret-auth-code")
        ),
    )

    assert calendar.run() == 1
    assert "RuntimeError" in caplog.text
    assert "page changed <redacted>" in caplog.text
    assert "secret-auth-code" not in caplog.text
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context.closed is True
    assert browser.closed is True


def test_context_creation_exception_returns_one_and_closes_browser(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    manager, browser, _, _ = install_fake_browser(monkeypatch)
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "create_context_from_auth_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("context creation failed")
        ),
    )

    assert calendar.run() == 1
    assert capsys.readouterr().out == ""
    assert calls == []
    assert manager.chromium.launch_options == [{"headless": True}]
    assert browser.closed is True
    assert existing.read_text(encoding="utf-8") == "existing-calendar"


def test_import_does_not_touch_repository_debug_output(
    tmp_path: Path,
) -> None:
    debug_dir = tmp_path / "debug_output"
    debug_dir.mkdir()
    sentinel = debug_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    env = os.environ.copy()
    env.pop("CREW_LEGACY_DIAGNOSTICS", None)
    root = Path(__file__).parents[1]
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(root), env.get("PYTHONPATH", "")])
    )

    result = subprocess.run(
        [sys.executable, "-c", "import crew_calendar_main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "playwright" / ".auth-diagnostics").exists()


def test_formal_run_has_no_legacy_login_or_ocr_call_path() -> None:
    source = inspect.getsource(calendar.run)

    assert "attempt_cloud_dynamic_password_login(" in source
    for forbidden in (
        "solve_captcha",
        "extract_captcha_bytes",
        "pytesseract",
        "ddddocr",
        "screenshot(",
        "page_text(",
    ):
        assert forbidden not in source
