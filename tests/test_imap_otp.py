from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import pytest

import authenticate_crew_session as authentication
from crew_auth_session import AuthObservation, AuthSignals, AuthStatus
from imap_otp import (
    ImapOtpReader,
    OtpMailboxError,
    OtpParseError,
    OtpTimeoutError,
    extract_otp_from_message,
    extract_otp_from_text,
)


ROOT = Path(__file__).parents[1]


def make_message(
    subject: str,
    *,
    plain: str | None = None,
    html: str | None = None,
    sent_at: datetime | None = None,
) -> bytes:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = "relay@example.invalid"
    message["To"] = "receiver@example.invalid"
    if sent_at is not None:
        message["Date"] = format_datetime(sent_at)
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


def test_connect_opens_inbox_without_provider_specific_id_and_closes() -> None:
    client = FakeImap()
    reader = ImapOtpReader(
        "configured@example.invalid",
        "configured-auth-code",
        client_factory=fake_factory(client),
    )

    with reader:
        assert reader.current_max_uid() == 7

    event_names = [event[0] for event in client.events]
    assert event_names.index("login") < event_names.index("select")
    assert "ID" not in event_names
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


def test_wait_rejects_delayed_previous_round_mail_and_used_otp() -> None:
    requested_at = datetime.now(timezone.utc)
    client = FakeImap(
        {
            8: make_message(
                "CREW_OTP",
                plain="验证码：111111",
                sent_at=requested_at - timedelta(seconds=30),
            ),
            9: make_message(
                "CREW_OTP",
                plain="验证码：111111",
                sent_at=requested_at + timedelta(seconds=1),
            ),
            10: make_message(
                "CREW_OTP",
                plain="验证码：638204",
                sent_at=requested_at + timedelta(seconds=1),
            ),
        }
    )
    client.current_uids = b"7 8 9 10"
    processed_uids: set[int] = set()
    reader = ImapOtpReader(
        "configured@example.invalid",
        "configured-auth-code",
        client_factory=fake_factory(client),
        sleeper=lambda _: None,
    )

    with reader:
        otp = reader.wait_for_new_otp(
            7,
            timeout_seconds=1,
            poll_interval_seconds=0,
            not_before=requested_at,
            clock_skew_seconds=5,
            processed_uids=processed_uids,
            used_otps={"111111"},
        )

    assert processed_uids == {8, 9, 10}
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


class RecoveryResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class RecoveryPage:
    def __init__(
        self,
        outcomes: list[tuple[str, int, AuthObservation]],
    ) -> None:
        self.url = "https://cp.9cair.com/"
        self.outcomes = list(outcomes)
        self.current_observation = AuthObservation(
            AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
            AuthSignals(),
        )
        self.goto_calls: list[str] = []
        self.waits: list[int] = []

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.waits.append(timeout_ms)

    def goto(
        self,
        url: str,
        *,
        wait_until: str,
        timeout: int,
    ) -> RecoveryResponse:
        assert wait_until == "domcontentloaded"
        assert timeout == 90_000
        self.goto_calls.append(url)
        next_url, status, observation = self.outcomes.pop(0)
        self.url = next_url
        self.current_observation = observation
        return RecoveryResponse(status)


class RecordingOtpReader:
    def __init__(self, events: list[Any]) -> None:
        self.events = events

    def current_max_uid(self) -> int:
        self.events.append(("baseline",))
        return 21

    def connect(self) -> None:
        self.events.append(("imap_connect",))

    def wait_for_new_otp(
        self,
        baseline_uid: int,
        **_: Any,
    ) -> str:
        self.events.append(("wait_for_otp", baseline_uid))
        return "482731"


class SequencedOtpReader:
    def __init__(self, events: list[Any], outcomes: list[Any]) -> None:
        self.events = events
        self.outcomes = list(outcomes)
        self.baseline = 20

    def connect(self) -> None:
        self.events.append(("imap_connect",))

    def current_max_uid(self) -> int:
        self.baseline += 1
        self.events.append(("baseline", self.baseline))
        return self.baseline

    def wait_for_new_otp(
        self,
        baseline_uid: int,
        **options: Any,
    ) -> str:
        self.events.append(
            (
                "wait_for_otp",
                baseline_uid,
                options["timeout_seconds"],
                options["poll_interval_seconds"],
            )
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return str(outcome)


def install_dynamic_login_mocks(
    monkeypatch: pytest.MonkeyPatch,
    events: list[Any],
    *,
    slider_handler: Any | None = None,
) -> dict[str, RecordingLocator]:
    locators = {
        authentication.DYNAMIC_LOGIN_FORM_SELECTOR: RecordingLocator(
            "dynamic_form",
            events,
        ),
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
        lambda _, **__: events.append(("switch_dynamic_login",)),
    )
    monkeypatch.setattr(
        authentication,
        "_wait_for_phone_or_email",
        lambda *_, **__: events.append(("phone_ready",)),
    )
    monkeypatch.setattr(
        authentication,
        "_wait_for_slider_if_present",
        slider_handler
        or (lambda *_, **__: events.append(("slider_complete",))),
    )
    monkeypatch.setattr(
        authentication,
        "_unique_locator",
        lambda _page, selector, _description: locators[selector],
    )
    monkeypatch.setattr(
        authentication,
        "_recover_post_login_mission_page",
        lambda *_args, **_kwargs: AuthObservation(
            AuthStatus.AUTHENTICATED,
            AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    return locators


def test_dynamic_login_records_uid_before_single_request_and_fills_otp(
    monkeypatch,
) -> None:
    events: list[Any] = []
    stages: list[tuple[str, dict[str, Any]]] = []
    page = RecordingPage(events)
    otp_reader = RecordingOtpReader(events)
    locators = {
        authentication.DYNAMIC_LOGIN_FORM_SELECTOR: RecordingLocator(
            "dynamic_form",
            events,
        ),
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
        lambda _, **__: events.append(("switch_dynamic_login",)),
    )
    monkeypatch.setattr(
        authentication,
        "_wait_for_phone_or_email",
        lambda *_, **__: events.append(("phone_ready",)),
    )
    monkeypatch.setattr(
        authentication,
        "_wait_for_slider_if_present",
        lambda *_, **__: events.append(("slider_complete",)),
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
        "_recover_post_login_mission_page",
        lambda *_args, **_kwargs: expected,
    )

    observation = authentication.complete_dynamic_password_login(
        page,
        otp_reader,
        manual_timeout_seconds=60,
        stage_reporter=lambda stage, details: stages.append(
            (stage, details)
        ),
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
    assert stages == [
        ("LOGIN_FLOW_STARTED", {}),
        ("OTP_ATTEMPT_STARTED", {"attempt": 1}),
        ("IMAP_BASELINE_RECORDED", {"attempt": 1}),
        ("OTP_REQUEST_CLICKED", {"attempt": 1}),
        ("OTP_MAIL_RECEIVED", {"otp_length": 6}),
        ("OTP_FIELD_FILLED", {}),
        ("LOGIN_BUTTON_CLICKED", {}),
        ("SSO_HANDOFF_REACHED", {}),
        ("FINAL_PAGE_PROBED", {}),
        ("MISSION_PAGE_AUTHENTICATED", {}),
    ]


def test_post_login_handoff_waits_for_business_cookie_then_navigates_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blank = AuthObservation(
        AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
        AuthSignals(),
    )
    authenticated = AuthObservation(
        AuthStatus.AUTHENTICATED,
        AuthSignals(mission_heading=True, task_container=True),
    )
    page = RecoveryPage(
        [
            (
                "https://cp.9cair.com/html/task/mission.html",
                200,
                authenticated,
            ),
        ]
    )
    stages: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        authentication,
        "probe_page",
        lambda current_page: current_page.current_observation,
    )
    cookie_states = iter(
        [
            (
                {"cp.9cair.com|/|CP_SESSION": "new-value"},
                ["CP_SESSION"],
            )
        ]
    )
    monkeypatch.setattr(
        authentication,
        "_cp_cookie_state",
        lambda _page: next(cookie_states),
    )

    observation = authentication._recover_post_login_mission_page(
        page,
        stage_reporter=lambda stage, details: stages.append(
            (stage, details)
        ),
        baseline_cp_cookies={
            "cp.9cair.com|/|CP_SESSION": "old-value",
        },
    )

    assert observation.status == AuthStatus.AUTHENTICATED
    assert page.goto_calls == [authentication.MISSION_URL]
    assert page.waits == [2_000, 2_000]
    assert any(
        stage == "SSO_BUSINESS_COOKIE_READY"
        and details["cookie_names"] == ["CP_SESSION"]
        for stage, details in stages
    )
    assert stages[-1] == (
        "MISSION_SINGLE_NAVIGATION_RESULT",
        {
            "domain": "cp.9cair.com",
            "path": "/html/task/mission.html",
            "main_frame_domain": "",
            "main_frame_path": "",
            "http_status": 200,
            "task_area_visible": True,
        },
    )


def test_post_login_handoff_does_not_navigate_without_business_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blank = AuthObservation(
        AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
        AuthSignals(),
    )
    page = RecoveryPage(
        []
    )
    monkeypatch.setattr(
        authentication,
        "probe_page",
        lambda current_page: current_page.current_observation,
    )
    monkeypatch.setattr(
        authentication,
        "_cp_cookie_state",
        lambda _page: (
            {"cp.9cair.com|/|CP_SESSION": "unchanged"},
            ["CP_SESSION"],
        ),
    )

    observation = authentication._recover_post_login_mission_page(
        page,
        stage_reporter=None,
        baseline_cp_cookies={
            "cp.9cair.com|/|CP_SESSION": "unchanged",
        },
        timeout_seconds=1,
    )

    assert observation.status == AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert page.goto_calls == []


def test_post_login_handoff_stops_when_redirected_to_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_required = AuthObservation(
        AuthStatus.LOGIN_REQUIRED,
        AuthSignals(login_url_hint=True),
    )
    page = RecoveryPage([])
    page.url = "https://cas.9cair.com/login?service=redacted"
    page.current_observation = login_required
    monkeypatch.setattr(
        authentication,
        "probe_page",
        lambda current_page: current_page.current_observation,
    )

    observation = authentication._recover_post_login_mission_page(
        page,
        stage_reporter=None,
    )

    assert observation.status == AuthStatus.LOGIN_REQUIRED
    assert page.goto_calls == []


def test_post_login_handoff_does_not_call_cp_401_login_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unknown = AuthObservation(
        AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
        AuthSignals(),
    )
    page = RecoveryPage(
        [("https://cp.9cair.com/", 401, unknown)]
    )
    monkeypatch.setattr(
        authentication,
        "probe_page",
        lambda current_page: current_page.current_observation,
    )
    monkeypatch.setattr(
        authentication,
        "_cp_cookie_state",
        lambda _page: (
            {"cp.9cair.com|/|CP_SESSION": "new-value"},
            ["CP_SESSION"],
        ),
    )

    observation = authentication._recover_post_login_mission_page(
        page,
        stage_reporter=None,
        baseline_cp_cookies={},
    )

    assert observation.status == AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert page.goto_calls == [authentication.MISSION_URL]


def test_post_login_handoff_stops_on_explicit_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unavailable = AuthObservation(
        AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
        AuthSignals(),
    )
    page = RecoveryPage(
        [
            ("https://cp.9cair.com/", 503, unavailable),
        ]
    )
    monkeypatch.setattr(
        authentication,
        "probe_page",
        lambda current_page: current_page.current_observation,
    )
    monkeypatch.setattr(
        authentication,
        "_cp_cookie_state",
        lambda _page: (
            {"cp.9cair.com|/|CP_SESSION": "new-value"},
            ["CP_SESSION"],
        ),
    )

    observation = authentication._recover_post_login_mission_page(
        page,
        stage_reporter=None,
        baseline_cp_cookies={},
    )

    assert observation.status == AuthStatus.NETWORK_OR_SITE_ERROR
    assert page.goto_calls == [authentication.MISSION_URL]


def test_post_login_handoff_does_not_navigate_when_task_is_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = RecoveryPage([])
    page.current_observation = AuthObservation(
        AuthStatus.AUTHENTICATED,
        AuthSignals(mission_heading=True, task_container=True),
    )
    monkeypatch.setattr(
        authentication,
        "probe_page",
        lambda current_page: current_page.current_observation,
    )

    observation = authentication._recover_post_login_mission_page(
        page,
        stage_reporter=None,
    )

    assert observation.status == AuthStatus.AUTHENTICATED
    assert page.goto_calls == []
    assert page.waits == []


def test_dynamic_login_retries_timeout_at_most_twice_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[Any] = []
    stages: list[tuple[str, dict[str, Any]]] = []
    page = RecordingPage(events)
    otp_reader = SequencedOtpReader(
        events,
        [
            OtpTimeoutError("timeout one"),
            OtpTimeoutError("timeout two"),
            "482731",
        ],
    )
    install_dynamic_login_mocks(monkeypatch, events)

    observation = authentication.complete_dynamic_password_login(
        page,
        otp_reader,
        manual_timeout_seconds=60,
        otp_timeout_seconds=45,
        max_otp_attempts=3,
        request_recovery_timeout_seconds=70,
        save_diagnostics=False,
        stage_reporter=lambda stage, details: stages.append(
            (stage, details)
        ),
    )

    assert observation.status == AuthStatus.AUTHENTICATED
    assert events.count(("click", "request")) == 3
    assert events.count(("wait_for_enabled",)) == 3
    assert events.count(("fill", "dynamic_password", "482731")) == 1
    assert events.count(("click", "login")) == 1
    assert [
        details["attempt"]
        for stage, details in stages
        if stage == "OTP_ATTEMPT_TIMEOUT"
    ] == [1, 2]


def test_dynamic_login_stops_after_three_mail_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[Any] = []
    page = RecordingPage(events)
    otp_reader = SequencedOtpReader(
        events,
        [
            OtpTimeoutError("timeout one"),
            OtpTimeoutError("timeout two"),
            OtpTimeoutError("timeout three"),
        ],
    )
    install_dynamic_login_mocks(monkeypatch, events)

    with pytest.raises(OtpTimeoutError, match="timeout three"):
        authentication.complete_dynamic_password_login(
            page,
            otp_reader,
            manual_timeout_seconds=60,
            otp_timeout_seconds=45,
            max_otp_attempts=3,
            request_recovery_timeout_seconds=70,
            save_diagnostics=False,
        )

    assert events.count(("click", "request")) == 3
    assert events.count(("wait_for_enabled",)) == 3
    assert not any(event[0] == "fill" for event in events)
    assert ("click", "login") not in events


def test_dynamic_login_never_retries_when_slider_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[Any] = []
    page = RecordingPage(events)
    otp_reader = SequencedOtpReader(events, ["482731"])

    def slider_required(*_: Any, **__: Any) -> None:
        raise authentication.AdditionalVerificationRequiredError(
            "slider required"
        )

    install_dynamic_login_mocks(
        monkeypatch,
        events,
        slider_handler=slider_required,
    )

    with pytest.raises(
        authentication.AdditionalVerificationRequiredError,
        match="slider required",
    ):
        authentication.complete_dynamic_password_login(
            page,
            otp_reader,
            manual_timeout_seconds=60,
            save_diagnostics=False,
        )

    assert events.count(("click", "request")) == 1
    assert not any(event[0] == "wait_for_otp" for event in events)


def test_dynamic_login_never_requests_when_imap_baseline_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[Any] = []
    page = RecordingPage(events)

    class BrokenReader(SequencedOtpReader):
        def current_max_uid(self) -> int:
            raise OtpMailboxError("imap unavailable")

    otp_reader = BrokenReader(events, [])
    install_dynamic_login_mocks(monkeypatch, events)

    with pytest.raises(OtpMailboxError, match="imap unavailable"):
        authentication.complete_dynamic_password_login(
            page,
            otp_reader,
            manual_timeout_seconds=60,
            save_diagnostics=False,
        )

    assert ("click", "request") not in events


def test_safe_login_page_snapshot_omits_query_and_sensitive_content() -> None:
    class Locator:
        def __init__(self, visible: bool) -> None:
            self.visible = visible

        def count(self) -> int:
            return 1

        def nth(self, _index: int):
            return self

        def is_visible(self, **_: Any) -> bool:
            return self.visible

    class Page:
        url = (
            "https://cas.9cair.com/login/path"
            "?phone=13000000000&token=secret"
        )
        frames: list[Any] = []

        def title(self) -> str:
            return "统一认证中心"

        def locator(self, selector: str) -> Locator:
            return Locator(
                selector
                in {
                    authentication.DYNAMIC_LOGIN_TAB_SELECTOR,
                    authentication.PHONE_OR_EMAIL_SELECTOR,
                }
            )

        def get_by_text(self, text: str, *, exact: bool) -> Locator:
            assert exact is True
            return Locator(text == authentication.QR_LOGIN_HEADING)

    snapshot = authentication.collect_safe_login_page_snapshot(Page())

    assert snapshot["domain"] == "cas.9cair.com"
    assert snapshot["path"] == "/login/path"
    assert snapshot["title"] == "统一认证中心"
    assert snapshot["visible_elements"]["qr_login_page"] is True
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "13000000000" not in serialized
    assert "secret" not in serialized


def test_dynamic_login_selectors_match_verified_dom_contract() -> None:
    assert (
        authentication.ACCOUNT_LOGIN_TOGGLE_SELECTOR
        == ".login-badge .badge-icon"
    )
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
        "CREW_PERSISTENT_PROFILE_DIR="
        "C:\\crew-calendar-data\\browser-profile\n"
        "CREW_AUTH_BACKUP_PATH="
        "C:\\crew-calendar-data\\auth-backup\\crew-auth-session.json\n"
        "CREW_BROWSER_CHANNEL=msedge\n"
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


def test_qr_login_switches_to_account_then_dynamic_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    stages: list[str] = []

    class Locator:
        def __init__(self, name: str, visible: bool = False) -> None:
            self.name = name
            self.visible = visible

        def count(self) -> int:
            return 1

        def nth(self, _index: int):
            return self

        def is_visible(self, **_: Any) -> bool:
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
        authentication.DYNAMIC_LOGIN_TAB_SELECTOR: Locator("dynamic_tab"),
        # A retained visible-looking form must not override the real QR page.
        authentication.DYNAMIC_LOGIN_FORM_SELECTOR: Locator(
            "dynamic_form",
            True,
        ),
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

    def fake_open_account_panel(
        _page: Any,
        _heading: Any,
        *,
        stage_reporter: Any,
    ) -> tuple[Locator, Locator]:
        stage_reporter(
            "TOGGLE_CANDIDATES_INSPECTED",
            {
                "diagnostic": {
                    "login_badge_count": 2,
                    "badge_icon_count": 2,
                    "visible_badge_icon_count": 1,
                    "eligible_toggle_count": 1,
                    "candidates": [],
                }
            },
        )
        stage_reporter("TOGGLE_CLICK_BADGE_ICON", {})
        stage_reporter("ACCOUNT_LOGIN_TOGGLE_CLICKED", {})
        locators[authentication.PASSWORD_LOGIN_TAB_SELECTOR].visible = True
        locators[authentication.DYNAMIC_LOGIN_TAB_SELECTOR].visible = True
        return (
            locators[authentication.PASSWORD_LOGIN_TAB_SELECTOR],
            locators[authentication.DYNAMIC_LOGIN_TAB_SELECTOR],
        )

    monkeypatch.setattr(
        authentication,
        "_open_account_login_panel",
        fake_open_account_panel,
    )

    authentication._switch_to_dynamic_password_login(
        Page(),
        stage_reporter=lambda stage, _details: stages.append(stage),
    )

    assert ("wait", "phone") in events
    assert ("wait", "request") in events
    assert stages == [
        "LOGIN_STATE_WAIT_STARTED",
        "QR_HEADING_FIRST_SEEN_MS",
        "LOGIN_STATE_CONFIRMED",
        "QR_LOGIN_PAGE_DETECTED",
        "TOGGLE_CANDIDATES_INSPECTED",
        "TOGGLE_CLICK_BADGE_ICON",
        "ACCOUNT_LOGIN_TOGGLE_CLICKED",
        "PASSWORD_TAB_VISIBLE",
        "LOGIN_PAGE_SWITCHED",
        "ACCOUNT_LOGIN_PANEL_VISIBLE",
        "DYNAMIC_TAB_CLICKED",
        "DYNAMIC_TAB_OPENED",
    ]


class SequencedLoginStatePage:
    def __init__(self, states: list[set[str]]) -> None:
        self.states = states
        self.index = 0
        self.elapsed_ms = 0

    @property
    def current(self) -> set[str]:
        return self.states[min(self.index, len(self.states) - 1)]

    def wait_for_timeout(self, milliseconds: int) -> None:
        assert milliseconds == authentication.LOGIN_STATE_POLL_INTERVAL_MS
        self.elapsed_ms += milliseconds
        self.index = min(self.index + 1, len(self.states) - 1)

    def locator(self, selector: str):
        mapping = {
            authentication.PASSWORD_LOGIN_TAB_SELECTOR: "account",
            authentication.DYNAMIC_LOGIN_TAB_SELECTOR: "account",
            authentication.DYNAMIC_LOGIN_FORM_SELECTOR: "dynamic",
            authentication.PHONE_OR_EMAIL_SELECTOR: "dynamic",
            authentication.DYNAMIC_PASSWORD_SELECTOR: "dynamic",
            authentication.REQUEST_DYNAMIC_PASSWORD_SELECTOR: "dynamic",
        }
        return SequencedLoginStateLocator(
            self,
            mapping.get(selector, ""),
        )

    def get_by_text(self, text: str, *, exact: bool):
        assert text == authentication.QR_LOGIN_HEADING
        assert exact is True
        return SequencedLoginStateLocator(self, "qr")


class SequencedLoginStateLocator:
    def __init__(
        self,
        page: SequencedLoginStatePage,
        state_name: str,
    ) -> None:
        self.page = page
        self.state_name = state_name

    def count(self) -> int:
        return 1

    def nth(self, _index: int):
        return self

    def is_visible(self, **_: Any) -> bool:
        return self.state_name in self.page.current

    def wait_for(self, **_: Any) -> None:
        return None

    def click(self) -> None:
        return None


def test_qr_heading_delayed_two_seconds_is_confirmed_and_clicked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = SequencedLoginStatePage(
        [set() for _ in range(10)]
        + [{"qr"}, {"qr"}]
    )
    stages: list[tuple[str, dict[str, Any]]] = []
    opened: list[bool] = []
    monkeypatch.setattr(
        authentication.time,
        "monotonic",
        lambda: page.elapsed_ms / 1000,
    )

    def fake_open(
        _page: Any,
        _heading: Any,
        *,
        stage_reporter: Any,
    ):
        opened.append(True)
        stage_reporter(
            "TOGGLE_CANDIDATES_INSPECTED",
            {"diagnostic": {}},
        )
        stage_reporter("TOGGLE_CLICK_LOGIN_BADGE", {})
        stage_reporter("ACCOUNT_LOGIN_TOGGLE_CLICKED", {})
        return (
            SequencedLoginStateLocator(page, "account"),
            SequencedLoginStateLocator(page, "account"),
        )

    monkeypatch.setattr(
        authentication,
        "_open_account_login_panel",
        fake_open,
    )

    authentication._switch_to_dynamic_password_login(
        page,
        stage_reporter=lambda stage, details: stages.append(
            (stage, details)
        ),
    )

    assert opened == [True]
    assert (
        "QR_HEADING_FIRST_SEEN_MS",
        {"elapsed_ms": 2000},
    ) in stages
    assert (
        "LOGIN_STATE_CONFIRMED",
        {"state": "QR"},
    ) in stages


def test_qr_state_wins_over_residual_dynamic_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = SequencedLoginStatePage(
        [
            {"qr", "dynamic"},
            {"qr", "dynamic"},
        ]
    )
    monkeypatch.setattr(
        authentication.time,
        "monotonic",
        lambda: page.elapsed_ms / 1000,
    )

    state, _heading = (
        authentication._wait_for_stable_login_page_state(
            page,
            stage_reporter=None,
        )
    )

    assert state == "QR"


def test_transient_login_states_do_not_confirm_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = SequencedLoginStatePage(
        [
            {"account"},
            set(),
            {"dynamic"},
            {"qr"},
            {"qr"},
        ]
    )
    reports: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        authentication.time,
        "monotonic",
        lambda: page.elapsed_ms / 1000,
    )

    state, _heading = (
        authentication._wait_for_stable_login_page_state(
            page,
            stage_reporter=lambda stage, details: reports.append(
                (stage, details)
            ),
        )
    )

    assert state == "QR"
    confirmed = [
        details["state"]
        for stage, details in reports
        if stage == "LOGIN_STATE_CONFIRMED"
    ]
    assert confirmed == ["QR"]


def test_transient_account_state_waits_for_qr_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = SequencedLoginStatePage(
        [{"account"} for _ in range(5)]
        + [{"qr"}, {"qr"}]
    )
    monkeypatch.setattr(
        authentication.time,
        "monotonic",
        lambda: page.elapsed_ms / 1000,
    )

    state, _heading = (
        authentication._wait_for_stable_login_page_state(
            page,
            stage_reporter=None,
        )
    )

    assert state == "QR"


def test_login_page_state_timeout_has_exact_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = SequencedLoginStatePage([set()])
    monkeypatch.setattr(
        authentication.time,
        "monotonic",
        lambda: page.elapsed_ms / 1000,
    )

    with pytest.raises(authentication.LoginPageStateError) as caught:
        authentication._wait_for_stable_login_page_state(
            page,
            stage_reporter=None,
            timeout_seconds=0.4,
        )

    assert caught.value.category == "LOGIN_PAGE_STATE_TIMEOUT"


def test_toggle_candidate_filter_selects_only_visible_top_right_icon() -> None:
    class Element:
        def __init__(
            self,
            *,
            visible: bool,
            box: dict[str, float] | None,
            style: dict[str, str] | None = None,
            parent: Any = None,
        ) -> None:
            self.visible = visible
            self.box = box
            self.style = style or {
                "display": "block",
                "visibility": "visible",
                "pointer_events": "auto",
            }
            self.parent = parent

        def count(self) -> int:
            return 1

        def nth(self, _index: int):
            return self

        def is_visible(self, **_: Any) -> bool:
            return self.visible

        def bounding_box(self):
            return self.box

        def evaluate(self, _script: str):
            return self.style

        def locator(self, selector: str):
            assert selector.startswith("xpath=ancestor::")
            return self.parent

    class Collection:
        def __init__(self, items: list[Element]) -> None:
            self.items = items

        def count(self) -> int:
            return len(self.items)

        def nth(self, index: int) -> Element:
            return self.items[index]

    hidden_badge = Element(
        visible=False,
        box=None,
    )
    visible_badge = Element(
        visible=True,
        box={"x": 180, "y": 75, "width": 50, "height": 50},
    )
    hidden_icon = Element(
        visible=False,
        box={"x": 190, "y": 85, "width": 20, "height": 20},
        style={
            "display": "none",
            "visibility": "hidden",
            "pointer_events": "none",
        },
        parent=hidden_badge,
    )
    visible_icon = Element(
        visible=True,
        box={"x": 195, "y": 90, "width": 20, "height": 20},
        parent=visible_badge,
    )
    badges = Collection([hidden_badge, visible_badge])
    icons = Collection([hidden_icon, visible_icon])

    class Page:
        def locator(self, selector: str):
            if selector == ".login-badge":
                return badges
            if selector == ".badge-icon":
                return icons
            raise AssertionError(selector)

    heading = Element(
        visible=True,
        box={"x": 100, "y": 100, "width": 100, "height": 20},
    )

    icon, badge, diagnostic = (
        authentication._inspect_toggle_candidates(Page(), heading)
    )

    assert icon is visible_icon
    assert badge is visible_badge
    assert diagnostic["login_badge_count"] == 2
    assert diagnostic["badge_icon_count"] == 2
    assert diagnostic["visible_badge_icon_count"] == 1
    assert diagnostic["eligible_toggle_count"] == 1
    assert diagnostic["candidates"][0] == {
        "index": 0,
        "visible": False,
        "bounding_box_exists": True,
        "display": "none",
        "visibility": "hidden",
        "pointer_events": "none",
        "inside_login_badge": True,
        "top_right_region": False,
    }


def test_multiple_visible_top_right_toggles_are_rejected() -> None:
    class Element:
        def __init__(self, x: float) -> None:
            self.x = x
            self.parent: Any = None

        def count(self) -> int:
            return 1

        def is_visible(self, **_: Any) -> bool:
            return True

        def bounding_box(self):
            return {
                "x": self.x,
                "y": 90,
                "width": 20,
                "height": 20,
            }

        def evaluate(self, _script: str):
            return {
                "display": "block",
                "visibility": "visible",
                "pointer_events": "auto",
            }

        def locator(self, _selector: str):
            return self.parent

    class Collection:
        def __init__(self, items: list[Element]) -> None:
            self.items = items

        def count(self) -> int:
            return len(self.items)

        def nth(self, index: int):
            return self.items[index]

    icons = [Element(190), Element(215)]
    badges = [Element(180), Element(205)]
    for icon, badge in zip(icons, badges):
        badge.bounding_box = lambda badge=badge: {
            "x": badge.x,
            "y": 75,
            "width": 50,
            "height": 50,
        }
        icon.parent = badge

    class Page:
        def locator(self, selector: str):
            return Collection(
                badges if selector == ".login-badge" else icons
            )

    heading = Element(100)
    heading.bounding_box = lambda: {
        "x": 100,
        "y": 100,
        "width": 100,
        "height": 20,
    }

    with pytest.raises(authentication.LoginToggleError) as caught:
        authentication._inspect_toggle_candidates(Page(), heading)

    assert caught.value.category == "MULTIPLE_VISIBLE_TOGGLES"
    assert caught.value.diagnostic["eligible_toggle_count"] == 2


def test_toggle_click_prefers_visible_icon_then_badge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    badge = object()
    icon = object()
    clicks: list[object] = []
    stages: list[str] = []
    checks = iter((False, True))

    monkeypatch.setattr(
        authentication,
        "_inspect_toggle_candidates",
        lambda *_: (
            icon,
            badge,
            {
                "login_badge_count": 2,
                "badge_icon_count": 2,
                "visible_badge_icon_count": 1,
                "eligible_toggle_count": 1,
                "candidates": [],
            },
        ),
    )
    monkeypatch.setattr(
        authentication,
        "_ordinary_toggle_click",
        lambda target: clicks.append(target),
    )
    monkeypatch.setattr(
        authentication,
        "_wait_for_account_tabs",
        lambda *args, **kwargs: next(checks),
    )

    class Page:
        def locator(self, _selector: str):
            return object()

    authentication._open_account_login_panel(
        Page(),
        object(),
        stage_reporter=lambda stage, _details: stages.append(stage),
    )

    assert clicks == [icon, badge]
    assert stages[-3:] == [
        "TOGGLE_CLICK_BADGE_ICON",
        "TOGGLE_CLICK_LOGIN_BADGE",
        "ACCOUNT_LOGIN_TOGGLE_CLICKED",
    ]


def test_toggle_failure_happens_before_imap_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class Reader:
        def connect(self) -> None:
            events.append("connect")

    monkeypatch.setattr(
        authentication,
        "_switch_to_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            authentication.LoginToggleError("TOGGLE_NOT_FOUND")
        ),
    )

    with pytest.raises(authentication.LoginToggleError):
        authentication.complete_dynamic_password_login(
            object(),
            Reader(),
            manual_timeout_seconds=1,
        )

    assert events == []


def test_already_dynamic_login_does_not_repeat_switch() -> None:
    events: list[tuple[str, str]] = []

    class Locator:
        def __init__(self, name: str, visible: bool = True) -> None:
            self.name = name
            self.visible = visible

        def count(self) -> int:
            return 1

        def nth(self, _index: int):
            return self

        def is_visible(self, **_: Any) -> bool:
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

        def wait_for_timeout(self, _milliseconds: int) -> None:
            return None

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
