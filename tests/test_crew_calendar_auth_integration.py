import os
import inspect
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

    assert capsys.readouterr().out == f"AUTH_STATUS={status.value}\n"
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

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
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

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
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


def test_processing_exception_returns_one_and_closes_resources(
    monkeypatch,
    tmp_path: Path,
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
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda page: (_ for _ in ()).throw(RuntimeError("page changed")),
    )

    assert calendar.run() == 1
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
