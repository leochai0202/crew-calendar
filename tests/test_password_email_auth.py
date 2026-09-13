import inspect
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

import crew_calendar_email_entry as entry
import crew_calendar_main as calendar
import password_email_auth as email_auth
from crew_auth_session import AuthObservation, AuthSignals, AuthStatus
from test_crew_calendar_auth_integration import install_fake_browser, install_valid_bundle


AUTHENTICATED = AuthObservation(AuthStatus.AUTHENTICATED, AuthSignals())
LOGIN_REQUIRED = AuthObservation(AuthStatus.LOGIN_REQUIRED_PASSWORD_CAPTCHA, AuthSignals())


class Collection:
    def __init__(self, *items):
        self.items = items

    def count(self):
        return len(self.items)

    def nth(self, i):
        return self.items[i]

    def __getattr__(self, name):
        assert len(self.items) == 1
        return getattr(self.items[0], name)


class Element:
    def __init__(self, *, attrs=None, click=None):
        self.attrs = attrs or {}
        self.value = ""
        self.text = ""
        self.checked = False
        self.enabled = True
        self.action = click or (lambda: None)
        self.clicks = 0

    def is_visible(self):
        return True

    def is_enabled(self):
        return self.enabled

    def get_attribute(self, key):
        return self.attrs.get(key)

    def text_content(self, **_kwargs):
        return self.text

    def fill(self, text, **_kwargs):
        self.value = text

    def check(self, **_kwargs):
        self.checked = True

    def is_checked(self):
        return self.checked

    def click(self, **_kwargs):
        assert self.enabled
        self.clicks += 1
        self.action()

    def wait_for(self, **_kwargs):
        pass


class Form(Element):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.username = Element()
        self.password = Element()
        self.code = Element()
        self.radio = Element(attrs={"type": "radio", "name": "sendType"})
        self.request = Element(click=page.send)
        self.submit = Element(click=page.submit)

    def locator(self, selector):
        assert "phone" not in selector.lower()
        return Collection({
            email_auth.PASSWORD_USERNAME_SELECTOR: self.username,
            email_auth.PASSWORD_INPUT_SELECTOR: self.password,
            email_auth.EMAIL_CODE_SELECTOR: self.code,
            email_auth.EMAIL_REQUEST_SELECTOR: self.request,
            email_auth.EMAIL_SUBMIT_SELECTOR: self.submit,
        }[selector])

    def get_by_label(self, text, **_kwargs):
        assert text == "邮箱验证"
        return Collection(self.radio)

    def get_by_text(self, text, **_kwargs):
        assert text == email_auth.COUNTDOWN_RE
        return Collection()


class Page:
    def __init__(self, results=("countdown",)):
        self.url = "https://cas.9cair.com/login"
        self.events = []
        self.results = results
        self.result = "none"
        self.form = Form(self)
        self.tab = Element()

    def send(self):
        assert self.form.radio.is_checked()
        assert self.form.username.value == "private-crew-account"
        assert self.form.password.value == "private-crew-password"
        self.events.append("send")
        self.result = self.results[min(self.events.count("send") - 1, len(self.results) - 1)]
        self.form.request.text = "42秒后重新获取" if self.result == "countdown" else "获取动态密码"
        self.form.request.enabled = self.result != "disabled"

    def submit(self):
        assert self.form.code.value == "205083"
        self.events.append("submit")
        self.url = calendar.MISSION_URL

    def locator(self, selector):
        assert selector in (email_auth.PASSWORD_FORM_SELECTOR,
                            email_auth.PASSWORD_LOGIN_TAB_SELECTOR)
        return Collection(self.form if selector == email_auth.PASSWORD_FORM_SELECTOR else self.tab)

    def get_by_text(self, text, **_kwargs):
        assert text == "发送验证码失败"
        return Collection(Element()) if self.result == "failure" else Collection()

    def wait_for_timeout(self, _ms):
        pass

    def wait_for_url(self, _url, **_kwargs):
        assert self.url == calendar.MISSION_URL

    def goto(self, url, **_kwargs):
        assert not self.form.password.value
        self.events.append("fresh-login-entry")
        self.url = url


class Reader:
    def __init__(self, page):
        self.page = page
        self.polls = 0
        self.closed = False

    def connect(self):
        self.page.events.append("connect-metadata")

    def current_max_uid(self):
        self.page.events.append("baseline")
        return 7

    def wait_for_new_otp(self, baseline_uid, *, not_before):
        assert baseline_uid == 7
        assert not_before.tzinfo is not None
        assert self.page.result in ("countdown", "disabled")
        self.page.events.append("poll")
        self.polls += 1
        return "205083"

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("CREW_USERNAME", "private-crew-account")
    monkeypatch.setenv("CREW_PASSWORD", "private-crew-password")
    monkeypatch.setenv("IMAP_EMAIL", "private-mail@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "private-mail-auth")
    monkeypatch.setattr(email_auth, "prepare_login_page_for_auth_method",
                        lambda *_args, **_kwargs: LOGIN_REQUIRED)
    monkeypatch.setattr(email_auth, "_cp_cookie_state", lambda _page: ({"session": "private-cookie"}, []))
    monkeypatch.setattr(email_auth, "_recover_post_login_mission_page",
                        lambda *_args, **_kwargs: AUTHENTICATED)


@pytest.mark.parametrize("result", ["countdown", "disabled"])
def test_request_must_be_accepted_before_body_polling(result, capsys):
    page = Page((result,))
    reader = Reader(page)
    assert email_auth.attempt_password_email_login(page, reader_factory=lambda: reader) == AUTHENTICATED
    assert page.events.index("baseline") < page.events.index("send") < page.events.index("poll")
    assert reader.closed
    assert page.form.password.value == page.form.username.value == page.form.code.value == ""
    output = capsys.readouterr().out
    assert "EMAIL_OTP_REQUEST_ACCEPTED=true" in output
    for sensitive in ("private-crew-account", "private-crew-password", "205083",
                      "private-cookie", "private-mail", "private-mail-auth"):
        assert sensitive not in output


@pytest.mark.parametrize("result", ["failure", "none"])
def test_failed_or_ambiguous_request_never_polls_mailbox(result, capsys):
    page = Page((result,))
    reader = Reader(page)
    result = email_auth.attempt_password_email_login(page, reader_factory=lambda: reader)
    assert result.status == AuthStatus.LOGIN_REQUIRED
    assert reader.polls == 0
    assert page.events.count("send") == 2
    assert "EMAIL_OTP_REQUEST_ACCEPTED=false" in capsys.readouterr().out


def test_explicit_failure_wins_over_disabled_state():
    page = Page(("failure",))
    page.result = "failure"
    page.form.request.enabled = False
    assert not email_auth.email_request_accepted(page, page.form, page.form.request)


def test_failed_requests_call_original_phone_exactly_once_after_fresh_navigation(monkeypatch):
    page = Page(("none",))
    reader = Reader(page)
    monkeypatch.setattr(email_auth.SpringAirEmailOtpReader, "from_environment", lambda: reader)
    phone = Mock(return_value=AUTHENTICATED)
    monkeypatch.setattr(entry, "_ORIGINAL_DYNAMIC_PHONE_LOGIN", phone)
    control = Path("auth-control.json")
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    assert entry.email_first_then_original_phone(page, auth_control_path=control, now=now) == AUTHENTICATED
    phone.assert_called_once_with(page, auth_control_path=control, now=now)
    assert page.events[-1] == "fresh-login-entry"
    assert page.events.count("send") == 2
    assert reader.polls == 0


def test_email_success_never_calls_phone_even_with_existing_phone_cooldown(monkeypatch, capsys):
    page = Page()
    reader = Reader(page)
    monkeypatch.setattr(email_auth.SpringAirEmailOtpReader, "from_environment", lambda: reader)
    phone = Mock()
    monkeypatch.setattr(entry, "_ORIGINAL_DYNAMIC_PHONE_LOGIN", phone)
    assert entry.email_first_then_original_phone(page, auth_control_path=Path("cooldown.json")) == AUTHENTICATED
    phone.assert_not_called()
    output = capsys.readouterr().out
    assert "OTP_REQUESTS=0\nIMAP_READS=0" in output


def test_only_crew_secrets_no_windows_username_or_password_fallback(monkeypatch, capsys):
    monkeypatch.delenv("CREW_USERNAME")
    monkeypatch.delenv("CREW_PASSWORD")
    monkeypatch.setenv("USERNAME", "private-windows-user")
    monkeypatch.setenv("PASSWORD", "private-windows-password")
    page = Page()
    reader = Mock()
    result = email_auth.attempt_password_email_login(page, reader_factory=lambda: reader)
    assert result.status == AuthStatus.LOGIN_REQUIRED
    reader.connect.assert_not_called()
    assert "send" not in page.events
    output = capsys.readouterr().out
    assert "EMAIL_LOGIN_CREDENTIALS_MISSING" in output
    assert "private-windows" not in output


def test_unresolvable_email_radio_never_requests_or_uses_phone_radio(monkeypatch):
    page = Page()
    page.form.radio.attrs["name"] = "unrelated"
    reader = Mock()
    assert email_auth.attempt_password_email_login(page, reader_factory=lambda: reader).status == AuthStatus.LOGIN_REQUIRED
    reader.connect.assert_not_called()
    assert "send" not in page.events
    assert "手机号验证" not in inspect.getsource(email_auth._select_email_verification)
    assert "_switch_to_dynamic_password_login" not in inspect.getsource(email_auth)


def test_imap_exception_never_exposes_exception_payload(monkeypatch, capsys):
    page = Page()
    reader = Mock()
    reader.connect.side_effect = RuntimeError("private-password cookie token POST payload")
    assert email_auth.attempt_password_email_login(page, reader_factory=lambda: reader).status == AuthStatus.LOGIN_REQUIRED
    output = capsys.readouterr().out
    assert "EMAIL_LOGIN_SAFE_FAILURE" in output
    assert "private-password" not in output


def test_http_or_untrusted_cas_origin_never_receives_credentials():
    for url in ("http://cas.9cair.com/login", "https://cas.9cair.com.evil.invalid/login"):
        page = Page()
        page.url = url
        reader = Mock()
        result = email_auth.attempt_password_email_login(page, reader_factory=lambda: reader)
        assert result.status == AuthStatus.LOGIN_REQUIRED
        assert not page.form.username.value and not page.form.password.value
        reader.connect.assert_not_called()


def test_asynchronous_acceptance_and_exact_request_timestamp():
    page = Page(("none",))
    reader = Reader(page)
    timestamp = datetime(2026, 9, 13, 4, 0, 0, 500_000, tzinfo=timezone.utc)
    waits = []

    def wait(ms):
        waits.append(ms)
        page.result = "countdown"
        page.form.request.text = "42秒后重新获取"

    page.wait_for_timeout = wait
    poll = Mock(wraps=reader.wait_for_new_otp)
    reader.wait_for_new_otp = poll
    assert email_auth.attempt_password_email_login(
        page, reader_factory=lambda: reader, clock=lambda: timestamp,
    ) == AUTHENTICATED
    assert waits
    poll.assert_called_once_with(7, not_before=timestamp)


def test_mailbox_cleanup_error_is_safe_and_does_not_break_success(capsys):
    page = Page()
    reader = Reader(page)
    reader.close = Mock(side_effect=RuntimeError("private-mail-auth"))
    assert email_auth.attempt_password_email_login(page, reader_factory=lambda: reader) == AUTHENTICATED
    output = capsys.readouterr().out
    assert "EMAIL_IMAP_CLOSE=SAFE_FAILURE" in output
    assert "private-mail-auth" not in output


def test_session_valid_wrapper_keeps_both_otp_routes_unused(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    install_fake_browser(monkeypatch)
    email = Mock()
    phone = Mock()
    monkeypatch.setattr(entry, "attempt_password_email_login", email)
    monkeypatch.setattr(entry, "_ORIGINAL_DYNAMIC_PHONE_LOGIN", phone)
    monkeypatch.setattr(calendar, "navigate_and_probe", lambda *_args, **_kwargs: AUTHENTICATED)
    for name in ("snapshot_existing_calendars", "rebuild_airport_indexes", "open_mission_page"):
        monkeypatch.setattr(calendar, name, Mock())
    monkeypatch.setattr(calendar, "detect_page_year", lambda _page: 2026)
    monkeypatch.setattr(calendar, "get_day_headers", lambda _page: [])
    monkeypatch.setattr(calendar, "collect_day_blocks", lambda _page: ["task"])
    monkeypatch.setattr(calendar, "create_multi_calendars_from_blocks", Mock())
    original = calendar.attempt_cloud_dynamic_password_login
    assert entry.run() == 0
    email.assert_not_called()
    phone.assert_not_called()
    assert calendar.attempt_cloud_dynamic_password_login is original


def test_phone_cooldown_and_failure_returned_unchanged(monkeypatch):
    page = Page()
    monkeypatch.setattr(entry, "attempt_password_email_login", lambda _page: LOGIN_REQUIRED)
    for status in (AuthStatus.AUTH_DEFERRED_OTP_COOLDOWN, AuthStatus.LOGIN_REQUIRED_DYNAMIC_OTP):
        phone_result = AuthObservation(status, AuthSignals())
        phone = Mock(return_value=phone_result)
        monkeypatch.setattr(entry, "_ORIGINAL_DYNAMIC_PHONE_LOGIN", phone)
        assert entry.email_first_then_original_phone(page) is phone_result
        phone.assert_called_once()


def test_wrapper_restores_original_hook_on_exception(monkeypatch):
    original = calendar.attempt_cloud_dynamic_password_login
    monkeypatch.setattr(calendar, "run", Mock(side_effect=RuntimeError("safe-test")))
    with pytest.raises(RuntimeError):
        entry.run()
    assert calendar.attempt_cloud_dynamic_password_login is original


def test_email_success_uses_existing_persistent_profile_and_backup(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    manager, _, context, _ = install_fake_browser(monkeypatch)
    profile = tmp_path / "runner-data" / "browser-profile"
    backup = tmp_path / "runner-data" / "auth-backup" / "session.json"
    events = []
    monkeypatch.setattr(calendar, "resolve_persistent_profile_dir", lambda: profile)
    monkeypatch.setattr(calendar, "resolve_auth_backup_path", lambda _profile: backup)
    monkeypatch.setattr(calendar, "resolve_auth_control_path", lambda _profile: tmp_path / "auth-control.json")
    monkeypatch.setattr(calendar, "_load_local_auth_backup", lambda _path: None)
    monkeypatch.setattr(calendar, "navigate_and_probe", lambda *_args, **_kwargs: LOGIN_REQUIRED)
    monkeypatch.setattr(calendar, "_recover_persistent_authentication", lambda *_args, **_kwargs: LOGIN_REQUIRED)
    monkeypatch.setattr(entry, "attempt_password_email_login", lambda _page: AUTHENTICATED)
    phone = Mock()
    monkeypatch.setattr(entry, "_ORIGINAL_DYNAMIC_PHONE_LOGIN", phone)

    def save(passed_context, path):
        assert passed_context is context and path == backup
        events.append("existing-backup")

    monkeypatch.setattr(calendar, "_write_filtered_auth_backup", save)
    monkeypatch.setattr(calendar, "snapshot_existing_calendars", lambda: events.append("snapshot"))
    monkeypatch.setattr(calendar, "rebuild_airport_indexes", Mock())
    monkeypatch.setattr(calendar, "open_mission_page", Mock())
    monkeypatch.setattr(calendar, "detect_page_year", lambda _page: 2026)
    monkeypatch.setattr(calendar, "get_day_headers", lambda _page: [])
    monkeypatch.setattr(calendar, "collect_day_blocks", lambda _page: ["task"])
    monkeypatch.setattr(calendar, "create_multi_calendars_from_blocks", Mock())
    assert entry.run() == 0
    phone.assert_not_called()
    assert manager.chromium.persistent_launch_options[0]["user_data_dir"] == str(profile)
    assert events == ["existing-backup", "snapshot", "existing-backup"]
    assert context.closed


@pytest.mark.parametrize("phone_status", [AuthStatus.AUTH_DEFERRED_OTP_COOLDOWN,
                                         AuthStatus.LOGIN_REQUIRED_DYNAMIC_OTP])
def test_email_and_phone_failure_preserves_last_good_ics(monkeypatch, tmp_path, phone_status):
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    _, _, context, _ = install_fake_browser(monkeypatch)
    context.page.goto = Mock()
    for filename in ("flight.ics", "crew_schedule.ics"):
        (tmp_path / filename).write_bytes(b"last-good-calendar")
    monkeypatch.setattr(calendar, "navigate_and_probe", lambda *_args, **_kwargs: LOGIN_REQUIRED)
    monkeypatch.setattr(entry, "attempt_password_email_login", lambda _page: LOGIN_REQUIRED)
    monkeypatch.setattr(entry, "_ORIGINAL_DYNAMIC_PHONE_LOGIN",
                        Mock(return_value=AuthObservation(phone_status, AuthSignals())))
    snapshot = Mock()
    create = Mock()
    monkeypatch.setattr(calendar, "snapshot_existing_calendars", snapshot)
    monkeypatch.setattr(calendar, "create_multi_calendars_from_blocks", create)
    assert entry.run() == calendar.STATUS_EXIT_CODES[phone_status]
    snapshot.assert_not_called()
    create.assert_not_called()
    for filename in ("flight.ics", "crew_schedule.ics"):
        assert (tmp_path / filename).read_bytes() == b"last-good-calendar"
