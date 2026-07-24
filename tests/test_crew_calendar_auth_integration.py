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
        (auth.AuthStatus.LOGIN_REQUIRED, 3),
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

    assert calendar.run() == exit_code

    assert capsys.readouterr().out == f"AUTH_STATUS={status.value}\n"
    assert calls == []
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context.closed is True
    assert browser.closed is True


@pytest.mark.parametrize("secret", ["", "not-valid-base64"])
def test_missing_or_corrupt_secret_is_login_required_without_browser_or_write(
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
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "sync_playwright",
        lambda: (_ for _ in ()).throw(
            AssertionError("browser must not start")
        ),
    )

    assert calendar.run() == 3

    assert capsys.readouterr().out == "AUTH_STATUS=LOGIN_REQUIRED\n"
    assert calls == []
    assert existing.read_text(encoding="utf-8") == "existing-calendar"


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

    for forbidden in (
        "login(",
        "solve_captcha",
        "extract_captcha_bytes",
        "pytesseract",
        "ddddocr",
        "screenshot(",
        "page_text(",
    ):
        assert forbidden not in source
