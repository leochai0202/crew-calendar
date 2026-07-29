from __future__ import annotations

import os
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

import authenticate_crew_session as authentication
from crew_auth_session import AuthObservation, AuthSignals, AuthStatus
from imap_otp import (
    ImapOtpReader,
    OtpParseError,
    extract_otp_from_message,
    extract_otp_from_text,
)


ROOT = Path(__file__).parents[1]


def make_message(
    subject: str,
    *,
    plain: str | None = None,
    html: str | None = None,
) -> bytes:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = "relay@example.invalid"
    message["To"] = "receiver@example.invalid"
    if plain is not None:
        message.set_content(plain)
    else:
        message.set_content("HTML message")
    if html is not None:
        message.add_alternative(html, subtype="html")
    return message.as_bytes()


class FakeImap:
    def __init__(
        self,
        messages: dict[int, bytes] | None = None,
    ) -> None:
        self.events: list[Any] = []
        self.messages = messages or {}
        self.baseline_uids = b"2 7"
        self.current_uids = b"2 7"

    def login(self, email_address: str, auth_code: str):
        self.events.append(("login", bool(email_address), bool(auth_code)))
        return "OK", [b"logged in"]

    def _simple_command(self, command: str, payload: str):
        self.events.append((command, "CrewCalendar" in payload))
        return "OK", [b"ID accepted"]

    def select(self, mailbox: str, readonly: bool = False):
        self.events.append(("select", mailbox, readonly))
        return "OK", [b"0"]

    def uid(self, command: str, *args: Any):
        self.events.append(("uid", command, args))
        if command == "search" and args[-1] == "ALL":
            return "OK", [self.baseline_uids]
        if command == "search":
            return "OK", [self.current_uids]
        if command == "fetch":
            uid = int(args[0])
            raw = self.messages[uid]
            return "OK", [(b"message", raw), b")"]
        raise AssertionError(f"Unexpected UID command: {command}")

    def noop(self):
        self.events.append(("noop",))
        return "OK", [b""]

    def unselect(self):
        self.events.append(("unselect",))
        return "OK", [b""]

    def logout(self):
        self.events.append(("logout",))
        return "BYE", [b""]


def fake_factory(client: FakeImap):
    def factory(
        host: str,
        port: int,
        **options: Any,
    ) -> FakeImap:
        client.events.append(
            (
                "connect",
                host,
                port,
                "ssl_context" in options,
                options.get("timeout"),
            )
        )
        return client

    return factory


def test_extracts_four_to_eight_digit_otp_from_plain_and_html() -> None:
    plain = make_message("notice CREW_OTP", plain="验证码：482731")
    html = make_message(
        "CREW_OTP",
        html="<html><body>验证码：<strong>7654</strong></body></html>",
    )

    assert extract_otp_from_message(plain) == "482731"
    assert extract_otp_from_message(html) == "7654"
    assert extract_otp_from_text("验证码 12345678") == "12345678"
    assert extract_otp_from_text("编号 123456789") is None


def test_ignores_message_with_unrelated_subject() -> None:
    raw = make_message("OTHER", plain="验证码：482731")

    assert extract_otp_from_message(raw) is None


def test_connect_sends_163_id_before_opening_inbox_and_closes() -> None:
    client = FakeImap()
    reader = ImapOtpReader(
        "configured@example.invalid",
        "configured-auth-code",
        host="imap.163.com",
        client_factory=fake_factory(client),
    )

    with reader:
        assert reader.current_max_uid() == 7

    event_names = [event[0] for event in client.events]
    assert event_names.index("login") < event_names.index("ID")
    assert event_names.index("ID") < event_names.index("select")
    assert ("select", "INBOX", True) in client.events
    assert event_names[-2:] == ["unselect", "logout"]
    assert "configured-auth-code" not in repr(reader)


def test_qq_connect_opens_inbox_without_sending_163_id() -> None:
    client = FakeImap()
    reader = ImapOtpReader(
        "configured@example.invalid",
        "configured-auth-code",
        host="imap.qq.com",
        port=993,
        client_factory=fake_factory(client),
    )

    with reader:
        assert reader.current_max_uid() == 7

    event_names = [event[0] for event in client.events]
    assert event_names.index("login") < event_names.index("select")
    assert "ID" not in event_names
    assert ("connect", "imap.qq.com", 993, True, 30) in client.events
    assert ("select", "INBOX", True) in client.events


def test_wait_only_fetches_uid_newer_than_baseline() -> None:
    client = FakeImap(
        {
            8: make_message("OTHER", plain="历史验证码：111111"),
            9: make_message(
                "CREW_OTP",
                html="<p>验证码</p><b>638204</b>",
            ),
        }
    )
    client.current_uids = b"2 7 8 9"
    reader = ImapOtpReader(
        "configured@example.invalid",
        "configured-auth-code",
        client_factory=fake_factory(client),
        sleeper=lambda _: None,
    )

    with reader:
        baseline = reader.current_max_uid()
        otp = reader.wait_for_new_otp(
            baseline,
            timeout_seconds=1,
            poll_interval_seconds=0,
        )

    fetched_uids = [
        int(event[2][0])
        for event in client.events
        if event[0:2] == ("uid", "fetch")
    ]
    assert baseline == 7
    assert fetched_uids == [8, 9]
    assert otp == "638204"


def test_matching_new_mail_without_code_reports_parse_error() -> None:
    client = FakeImap(
        {8: make_message("CREW_OTP", plain="没有数字验证码")}
    )
    client.current_uids = b"7 8"
    clock_value = [0.0]

    def monotonic() -> float:
        return clock_value[0]

    def sleeper(seconds: float) -> None:
        clock_value[0] += max(seconds, 0.1)

    reader = ImapOtpReader(
        "configured@example.invalid",
        "configured-auth-code",
        client_factory=fake_factory(client),
        sleeper=sleeper,
        monotonic=monotonic,
    )

    with reader:
        with pytest.raises(OtpParseError, match="未找到4到8位"):
            reader.wait_for_new_otp(
                7,
                timeout_seconds=0.2,
                poll_interval_seconds=0.1,
            )


class RecordingLocator:
    def __init__(self, name: str, events: list[Any]) -> None:
        self.name = name
        self.events = events

    def wait_for(self, **_: Any) -> None:
        self.events.append(("wait", self.name))

    def click(self) -> None:
        self.events.append(("click", self.name))

    def fill(self, value: str) -> None:
        self.events.append(("fill", self.name, value))


class RecordingPage:
    def __init__(self, events: list[Any]) -> None:
        self.events = events

    def wait_for_function(self, *_: Any, **__: Any) -> None:
        self.events.append(("wait_for_enabled",))

    def wait_for_url(self, *_: Any, **__: Any) -> None:
        self.events.append(("wait_for_login_navigation",))


class RecordingOtpReader:
    def __init__(self, events: list[Any]) -> None:
        self.events = events

    def current_max_uid(self) -> int:
        self.events.append(("baseline",))
        return 21

    def wait_for_new_otp(
        self,
        baseline_uid: int,
        **_: Any,
    ) -> str:
        self.events.append(("wait_for_otp", baseline_uid))
        return "482731"


def test_dynamic_login_records_uid_before_single_request_and_fills_otp(
    monkeypatch,
) -> None:
    events: list[Any] = []
    page = RecordingPage(events)
    otp_reader = RecordingOtpReader(events)
    locators = {
        authentication.REQUEST_DYNAMIC_PASSWORD_SELECTOR: RecordingLocator(
            "request",
            events,
        ),
        authentication.DYNAMIC_PASSWORD_SELECTOR: RecordingLocator(
            "dynamic_password",
            events,
        ),
        authentication.SUBMIT_DYNAMIC_LOGIN_SELECTOR: RecordingLocator(
            "login",
            events,
        ),
    }
    monkeypatch.setattr(
        authentication,
        "_switch_to_dynamic_password_login",
        lambda _: events.append(("switch_dynamic_login",)),
    )
    monkeypatch.setattr(
        authentication,
        "_wait_for_phone_or_email",
        lambda *_: events.append(("phone_ready",)),
    )
    monkeypatch.setattr(
        authentication,
        "_wait_for_slider_if_present",
        lambda *_: events.append(("slider_complete",)),
    )
    monkeypatch.setattr(
        authentication,
        "_unique_locator",
        lambda _page, selector, _description: locators[selector],
    )
    expected = AuthObservation(
        AuthStatus.AUTHENTICATED,
        AuthSignals(mission_heading=True, task_container=True),
    )
    monkeypatch.setattr(
        authentication,
        "navigate_and_probe",
        lambda *_: expected,
    )

    observation = authentication.complete_dynamic_password_login(
        page,
        otp_reader,
        manual_timeout_seconds=60,
    )

    assert observation == expected
    assert events.count(("click", "request")) == 1
    assert events.index(("baseline",)) < events.index(("click", "request"))
    assert events.index(("click", "request")) < events.index(
        ("wait_for_otp", 21)
    )
    assert events.index(("wait_for_otp", 21)) < events.index(
        ("fill", "dynamic_password", "482731")
    )
    assert events.index(("fill", "dynamic_password", "482731")) < (
        events.index(("click", "login"))
    )


def test_dynamic_login_selectors_match_verified_dom_contract() -> None:
    assert authentication.PASSWORD_LOGIN_TAB_SELECTOR == "#div1"
    assert authentication.DYNAMIC_LOGIN_TAB_SELECTOR == "#div2"
    assert authentication.PHONE_OR_EMAIL_SELECTOR == "#phone"
    assert authentication.DYNAMIC_PASSWORD_SELECTOR == "#dynamic"
    assert (
        authentication.REQUEST_DYNAMIC_PASSWORD_SELECTOR
        == "#btnGetDynamic"
    )
    assert authentication.SUBMIT_DYNAMIC_LOGIN_SELECTOR == "#loginBtn2"
    assert authentication.SHUMEI_SLIDER_SELECTOR == "#shu-mei-outer"


def test_environment_example_and_gitignore_contain_no_real_values() -> None:
    assert (ROOT / ".env.example").read_text(encoding="utf-8") == (
        "IMAP_HOST=imap.qq.com\n"
        "IMAP_PORT=993\n"
        "IMAP_EMAIL=\n"
        "IMAP_AUTH_CODE=\n"
        "CREW_LOGIN_PHONE=\n"
    )
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore


def test_load_local_imap_configuration_uses_existing_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'IMAP_HOST="imap.qq.com"\n'
        'IMAP_PORT="993"\n'
        'IMAP_EMAIL="crew@example.invalid"\n'
        'IMAP_AUTH_CODE="local-test-code"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("IMAP_EMAIL", raising=False)
    monkeypatch.delenv("IMAP_AUTH_CODE", raising=False)

    assert authentication.load_local_imap_configuration(env_file) is True
    assert authentication._imap_otp_environment_present() is True
    assert os.environ["IMAP_HOST"] == "imap.qq.com"
    assert os.environ["IMAP_PORT"] == "993"


def test_local_env_overrides_inherited_imap_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'IMAP_EMAIL="file@example.invalid"\n'
        'IMAP_AUTH_CODE="file-test-code"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("IMAP_EMAIL", "stale@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "stale-test-code")

    assert authentication.load_local_imap_configuration(env_file) is True
    assert os.environ["IMAP_EMAIL"] == "file@example.invalid"
    assert os.environ["IMAP_AUTH_CODE"] == "file-test-code"


def test_ensure_local_imap_configuration_skips_prompt_when_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'IMAP_EMAIL="crew@example.invalid"\n'
        'IMAP_AUTH_CODE="local-test-code"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("IMAP_EMAIL", raising=False)
    monkeypatch.delenv("IMAP_AUTH_CODE", raising=False)

    def unexpected_prompt(_initial_email: str = "") -> tuple[str, str]:
        raise AssertionError("existing .env must not open the prompt")

    monkeypatch.setattr(
        authentication,
        "prompt_for_imap_configuration",
        unexpected_prompt,
    )

    authentication.ensure_local_imap_configuration(env_file)


@pytest.mark.parametrize(
    "initial_content",
    ("", "IMAP_EMAIL=\nIMAP_AUTH_CODE=\n"),
)
def test_missing_or_empty_env_prompts_once_and_saves_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial_content: str,
) -> None:
    env_file = tmp_path / ".env"
    if initial_content:
        env_file.write_text(initial_content, encoding="utf-8")
    monkeypatch.delenv("IMAP_EMAIL", raising=False)
    monkeypatch.delenv("IMAP_AUTH_CODE", raising=False)
    prompts: list[str] = []

    def fake_prompt(initial_email: str = "") -> tuple[str, str]:
        prompts.append(initial_email)
        return "crew@example.invalid", "local-test-code"

    monkeypatch.setattr(
        authentication,
        "prompt_for_imap_configuration",
        fake_prompt,
    )

    authentication.ensure_local_imap_configuration(env_file)

    assert prompts == [""]
    assert authentication.load_local_imap_configuration(env_file) is True
    saved = env_file.read_text(encoding="utf-8")
    assert 'IMAP_EMAIL="crew@example.invalid"' in saved
    assert 'IMAP_AUTH_CODE="local-test-code"' in saved
    assert not list(tmp_path.glob(".env.*.tmp"))


def test_saving_local_imap_configuration_preserves_unrelated_entries(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local settings\n"
        "UNCHANGED=value\n"
        "IMAP_EMAIL=old@example.invalid\n"
        "IMAP_AUTH_CODE=old-test-code\n",
        encoding="utf-8",
    )

    authentication.save_local_imap_configuration(
        "new@example.invalid",
        "new-test-code",
        env_file,
    )

    saved = env_file.read_text(encoding="utf-8")
    assert "# local settings\nUNCHANGED=value\n" in saved
    assert saved.count("IMAP_EMAIL=") == 1
    assert saved.count("IMAP_AUTH_CODE=") == 1
    assert "old@example.invalid" not in saved
    assert "old-test-code" not in saved


def test_qr_login_switches_to_account_then_dynamic_password() -> None:
    events: list[tuple[str, str]] = []

    class Locator:
        def __init__(self, name: str, visible: bool = False) -> None:
            self.name = name
            self.visible = visible

        def count(self) -> int:
            return 1

        def is_visible(self) -> bool:
            return self.visible

        def wait_for(self, **_: Any) -> None:
            events.append(("wait", self.name))
            self.visible = True

        def click(self) -> None:
            events.append(("click", self.name))
            if self.name == "account_toggle":
                locators[authentication.DYNAMIC_LOGIN_TAB_SELECTOR].visible = (
                    True
                )
            if self.name == "dynamic_tab":
                locators[
                    authentication.DYNAMIC_LOGIN_FORM_SELECTOR
                ].visible = True

    locators = {
        authentication.PASSWORD_LOGIN_TAB_SELECTOR: Locator("password_tab"),
        authentication.ACCOUNT_LOGIN_TOGGLE_SELECTOR: Locator(
            "account_toggle",
            True,
        ),
        authentication.DYNAMIC_LOGIN_TAB_SELECTOR: Locator("dynamic_tab"),
        authentication.DYNAMIC_LOGIN_FORM_SELECTOR: Locator("dynamic_form"),
        authentication.PHONE_OR_EMAIL_SELECTOR: Locator("phone"),
        authentication.REQUEST_DYNAMIC_PASSWORD_SELECTOR: Locator("request"),
        authentication.DYNAMIC_PASSWORD_SELECTOR: Locator(
            "dynamic_password",
        ),
    }

    class Page:
        def locator(self, selector: str) -> Locator:
            return locators[selector]

        def get_by_text(self, text: str, *, exact: bool) -> Locator:
            assert text == authentication.QR_LOGIN_HEADING
            assert exact is True
            return Locator("qr_heading", True)

    authentication._switch_to_dynamic_password_login(Page())

    assert events.index(("click", "account_toggle")) < events.index(
        ("click", "dynamic_tab")
    )
    assert ("wait", "phone") in events
    assert ("wait", "request") in events


def test_already_dynamic_login_does_not_repeat_switch() -> None:
    events: list[tuple[str, str]] = []

    class Locator:
        def __init__(self, name: str, visible: bool = True) -> None:
            self.name = name
            self.visible = visible

        def count(self) -> int:
            return 1

        def is_visible(self) -> bool:
            return self.visible

        def wait_for(self, **_: Any) -> None:
            events.append(("wait", self.name))

        def click(self) -> None:
            events.append(("click", self.name))

    locators = {
        authentication.DYNAMIC_LOGIN_FORM_SELECTOR: Locator("dynamic_form"),
        authentication.PHONE_OR_EMAIL_SELECTOR: Locator("phone"),
        authentication.REQUEST_DYNAMIC_PASSWORD_SELECTOR: Locator("request"),
        authentication.DYNAMIC_PASSWORD_SELECTOR: Locator(
            "dynamic_password",
        ),
    }

    class Page:
        def locator(self, selector: str) -> Locator:
            if selector == authentication.ACCOUNT_LOGIN_TOGGLE_SELECTOR:
                raise AssertionError("account toggle must not be used")
            if selector == authentication.DYNAMIC_LOGIN_TAB_SELECTOR:
                raise AssertionError("dynamic tab must not be clicked again")
            return locators[selector]

    authentication._switch_to_dynamic_password_login(Page())

    assert events == [
        ("wait", "phone"),
        ("wait", "request"),
        ("wait", "dynamic_password"),
    ]


def test_phone_is_loaded_from_env_and_filled_automatically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        authentication,
        "ensure_local_login_phone",
        lambda: "13000000000",
    )
    events: list[tuple[str, str]] = []

    class PhoneLocator:
        def count(self) -> int:
            return 1

        def wait_for(self, **_: Any) -> None:
            events.append(("wait", "phone"))

        def input_value(self) -> str:
            return ""

        def fill(self, value: str) -> None:
            events.append(("fill", value))

    class Page:
        def locator(self, selector: str) -> PhoneLocator:
            assert selector == authentication.PHONE_OR_EMAIL_SELECTOR
            return PhoneLocator()

    authentication._wait_for_phone_or_email(Page(), 60)

    assert events == [("wait", "phone"), ("fill", "13000000000")]


def test_missing_phone_prompts_once_and_preserves_imap_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'IMAP_EMAIL="crew@example.invalid"\n'
        'IMAP_AUTH_CODE="local-test-code"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("CREW_LOGIN_PHONE", raising=False)
    prompts: list[str] = []
    monkeypatch.setattr(
        authentication,
        "prompt_for_login_phone",
        lambda initial="": prompts.append(initial) or "13000000000",
    )

    assert authentication.ensure_local_login_phone(env_file) == "13000000000"
    saved = env_file.read_text(encoding="utf-8")
    assert prompts == [""]
    assert 'IMAP_EMAIL="crew@example.invalid"' in saved
    assert 'IMAP_AUTH_CODE="local-test-code"' in saved
    assert 'CREW_LOGIN_PHONE="13000000000"' in saved


def test_visible_slider_in_iframe_waits_for_manual_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[tuple[str, str]] = []

    class Slider:
        def count(self) -> int:
            return 1

        def is_visible(self) -> bool:
            return True

        def wait_for(self, *, state: str, timeout: int) -> None:
            events.append((state, str(timeout)))

    class Frame:
        def locator(self, selector: str) -> Slider:
            assert selector == authentication.SHUMEI_SLIDER_SELECTOR
            return Slider()

    class Page:
        frames = [Frame()]

    authentication._wait_for_slider_if_present(
        Page(),
        60,
        detection_timeout_seconds=0,
    )

    assert events == [("hidden", "60000")]
    assert "需要人工完成一次滑块" in capsys.readouterr().out


def test_absent_slider_continues_without_waiting() -> None:
    class MissingSlider:
        def count(self) -> int:
            return 0

        def is_visible(self) -> bool:
            raise AssertionError("invisible locator must not be queried")

    class Frame:
        def locator(self, selector: str) -> MissingSlider:
            assert selector == authentication.SHUMEI_SLIDER_SELECTOR
            return MissingSlider()

    class Page:
        frames = [Frame()]

    authentication._wait_for_slider_if_present(
        Page(),
        60,
        detection_timeout_seconds=0,
    )
