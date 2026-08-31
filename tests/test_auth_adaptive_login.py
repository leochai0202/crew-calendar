import json
from datetime import datetime, timezone
from pathlib import Path

import crew_auth_session as auth
import crew_calendar_main as calendar


class FakeElement:
    def __init__(self, *, text: str = "", image: bytes = b"captcha") -> None:
        self.text = text
        self.image = image
        self.value = ""
        self.clicks = 0

    def inner_text(self, timeout: int = 0) -> str:
        return self.text

    def is_visible(self, timeout: int = 0) -> bool:
        return True

    def fill(self, value: str) -> None:
        self.value = value

    def click(self, timeout: int = 0) -> None:
        self.clicks += 1

    def screenshot(self, **_kwargs) -> bytes:
        return self.image

    def get_attribute(self, _name: str, timeout: int = 0):
        return None


class FakeLocator:
    def __init__(self, elements: list[FakeElement]) -> None:
        self.elements = elements

    def count(self) -> int:
        return len(self.elements)

    def nth(self, index: int) -> FakeElement:
        return self.elements[index]

    def inner_text(self, timeout: int = 0) -> str:
        return self.elements[0].inner_text(timeout) if self.elements else ""


class FakeAuthPage:
    def __init__(self, fields: dict[str, FakeElement] | None = None) -> None:
        self.url = "https://cas.9cair.com/login"
        self.fields = fields or {}
        self.waits: list[int] = []
        self.saved_screenshot: Path | None = None

    def locator(self, selector: str) -> FakeLocator:
        if selector == "body":
            return FakeLocator([FakeElement(text="春秋航空统一认证中心")])
        element = self.fields.get(selector)
        return FakeLocator([element] if element is not None else [])

    def wait_for_load_state(self, *_args, **_kwargs) -> None:
        return None

    def wait_for_timeout(self, delay: int) -> None:
        self.waits.append(delay)

    def screenshot(self, *, path: str, **_kwargs) -> None:
        for selector in (
            auth.PASSWORD_USERNAME_SELECTOR,
            auth.PASSWORD_INPUT_SELECTOR,
            auth.PASSWORD_CAPTCHA_INPUT_SELECTOR,
        ):
            assert self.fields[selector].value == ""
        self.saved_screenshot = Path(path)
        self.saved_screenshot.write_bytes(b"safe-diagnostic")


def password_page() -> tuple[FakeAuthPage, dict[str, FakeElement]]:
    fields = {
        auth.PASSWORD_USERNAME_SELECTOR: FakeElement(),
        auth.PASSWORD_INPUT_SELECTOR: FakeElement(),
        auth.PASSWORD_CAPTCHA_INPUT_SELECTOR: FakeElement(),
        calendar.PASSWORD_CAPTCHA_IMAGE_SELECTOR: FakeElement(),
        calendar.PASSWORD_LOGIN_BUTTON_SELECTOR: FakeElement(),
    }
    return FakeAuthPage(fields), fields


def test_probe_identifies_password_captcha_page() -> None:
    page, _fields = password_page()

    observation = auth.probe_page(page)

    assert observation.status == auth.AuthStatus.LOGIN_REQUIRED_PASSWORD_CAPTCHA
    assert observation.signals.password_captcha_form is True
    assert observation.signals.dynamic_otp_form is False


def test_probe_identifies_dynamic_otp_page() -> None:
    page = FakeAuthPage(
        {
            auth.DYNAMIC_PHONE_SELECTOR: FakeElement(),
            auth.DYNAMIC_OTP_SELECTOR: FakeElement(),
            auth.DYNAMIC_REQUEST_SELECTOR: FakeElement(),
        }
    )

    observation = auth.probe_page(page)

    assert observation.status == auth.AuthStatus.LOGIN_REQUIRED_DYNAMIC_OTP
    assert observation.signals.dynamic_otp_form is True
    assert observation.signals.password_captcha_form is False


def test_password_captcha_login_uses_preferred_credentials_without_otp(
    monkeypatch,
    capsys,
    caplog,
) -> None:
    page, fields = password_page()
    monkeypatch.setenv("CREW_USERNAME", "preferred-user")
    monkeypatch.setenv("CREW_PASSWORD", "preferred-password")
    monkeypatch.setenv("USERNAME", "legacy-user")
    monkeypatch.setenv("PASSWORD", "legacy-password")
    monkeypatch.setattr(
        calendar,
        "prepare_login_page_for_auth_method",
        lambda *_args, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED_PASSWORD_CAPTCHA,
            auth.AuthSignals(password_captcha_form=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "solve_password_captcha_safely",
        lambda _image: "A1B2",
    )
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda *_args, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("password login must not request OTP or read IMAP")
        ),
    )
    monkeypatch.setattr(calendar, "_write_cloud_auth_diagnostic", lambda *a, **k: None)

    observation = calendar.attempt_cloud_adaptive_login(page)

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert fields[auth.PASSWORD_USERNAME_SELECTOR].value == "preferred-user"
    assert fields[auth.PASSWORD_INPUT_SELECTOR].value == "preferred-password"
    assert fields[auth.PASSWORD_CAPTCHA_INPUT_SELECTOR].value == "A1B2"
    assert fields[calendar.PASSWORD_LOGIN_BUTTON_SELECTOR].clicks == 1
    output = capsys.readouterr().out
    assert "AUTH_PAGE_TYPE=PASSWORD_CAPTCHA" in output
    assert "AUTH_METHOD=PASSWORD_CAPTCHA" in output
    assert "OTP_REQUESTS=0" in output
    assert "IMAP_READS=0" in output
    safe_logs = output + caplog.text
    for secret in (
        "preferred-user",
        "preferred-password",
        "legacy-user",
        "legacy-password",
        "A1B2",
    ):
        assert secret not in safe_logs


def test_password_captcha_failure_stops_after_three_and_saves_safe_image(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    page, fields = password_page()
    diagnostic = tmp_path / "password-captcha.png"
    monkeypatch.setenv("CREW_USERNAME", "private-user")
    monkeypatch.setenv("CREW_PASSWORD", "private-password")
    monkeypatch.setenv(
        calendar.AUTH_PASSWORD_SCREENSHOT_PATH_ENV,
        str(diagnostic),
    )
    monkeypatch.setattr(
        calendar,
        "prepare_login_page_for_auth_method",
        lambda *_args, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED_PASSWORD_CAPTCHA,
            auth.AuthSignals(password_captcha_form=True),
        ),
    )
    attempts: list[bytes] = []
    monkeypatch.setattr(
        calendar,
        "solve_password_captcha_safely",
        lambda image: attempts.append(image) or "",
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("password failure must not fall through to OTP")
        ),
    )
    monkeypatch.setattr(calendar, "_write_cloud_auth_diagnostic", lambda *a, **k: None)

    observation = calendar.attempt_cloud_adaptive_login(page)

    assert observation.status == (
        auth.AuthStatus.LOGIN_REQUIRED_PASSWORD_CAPTCHA_FAILED
    )
    assert len(attempts) == 3
    assert fields[calendar.PASSWORD_CAPTCHA_IMAGE_SELECTOR].clicks == 3
    assert fields[calendar.PASSWORD_LOGIN_BUTTON_SELECTOR].clicks == 0
    assert diagnostic.read_bytes() == b"safe-diagnostic"
    assert page.saved_screenshot == diagnostic
    output = capsys.readouterr().out
    assert "OTP_REQUESTS=0" in output
    assert "IMAP_READS=0" in output
    assert "private-user" not in output
    assert "private-password" not in output


def test_explicit_dynamic_page_uses_only_existing_otp_flow(monkeypatch, capsys) -> None:
    page = FakeAuthPage()
    monkeypatch.setattr(
        calendar,
        "prepare_login_page_for_auth_method",
        lambda *_args, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED_DYNAMIC_OTP,
            auth.AuthSignals(dynamic_otp_form=True),
        ),
    )
    events: list[str] = []
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda *_args, **_kwargs: events.append("dynamic")
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_password_captcha_login",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dynamic page must not use password captcha")
        ),
    )

    observation = calendar.attempt_cloud_adaptive_login(page)

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert events == ["dynamic"]
    output = capsys.readouterr().out
    assert "AUTH_PAGE_TYPE=DYNAMIC_OTP" in output
    assert "AUTH_METHOD=DYNAMIC_OTP" in output


def test_password_captcha_login_ignores_active_otp_cooldown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    control_path = tmp_path / "auth-control.json"
    control_path.write_text(
        json.dumps(
            {
                "format": calendar.AUTH_CONTROL_FORMAT,
                "last_otp_request_at": "2026-08-31T00:00:00Z",
                "last_otp_result": "FAILED",
                "last_failure_reason": "OTP_REQUEST_FAILED",
            }
        ),
        encoding="utf-8",
    )
    page = FakeAuthPage()
    monkeypatch.setattr(
        calendar,
        "prepare_login_page_for_auth_method",
        lambda *_args, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED_PASSWORD_CAPTCHA,
            auth.AuthSignals(password_captcha_form=True),
        ),
    )
    events: list[str] = []
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_password_captcha_login",
        lambda *_args, **_kwargs: events.append("password")
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("OTP cooldown is irrelevant to password login")
        ),
    )
    monkeypatch.setattr(calendar, "_write_cloud_auth_diagnostic", lambda *a, **k: None)

    observation = calendar.attempt_cloud_adaptive_login(
        page,
        auth_control_path=control_path,
        now=datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc),
    )

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert events == ["password"]
