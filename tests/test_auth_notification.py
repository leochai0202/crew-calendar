import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import crew_auth_notification as notification


FIXED_TIME = datetime(
    2026,
    7,
    24,
    18,
    30,
    tzinfo=ZoneInfo("Asia/Shanghai"),
)


def recording_sender(messages: list[tuple[str, str, datetime]]):
    def send(subject: str, body: str, sent_at: datetime) -> None:
        messages.append((subject, body, sent_at))

    return send


def test_first_failure_sends_one_chinese_message_and_creates_state(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state" / "auth_notification_state.json"
    messages: list[tuple[str, str, datetime]] = []

    result = notification.handle_auth_status(
        "LOGIN_REQUIRED",
        state_path,
        recording_sender(messages),
        FIXED_TIME,
    )

    assert result == "FAILURE_SENT"
    assert len(messages) == 1
    subject, body, sent_at = messages[0]
    assert "认证需要处理" in subject
    assert "检测时间（北京时间）" in body
    assert "原有日历继续保留" in body
    assert "运行 python authenticate_crew_session.py" in body
    assert "安全更新 GitHub Secret CREW_STORAGE_STATE_B64" in body
    assert sent_at is FIXED_TIME

    state = notification.load_state(state_path)
    assert state.incident_active is True
    assert state.last_failure_status == "LOGIN_REQUIRED"
    assert state.failure_notified_at == "2026-07-24T18:30:00+08:00"
    assert state.recovery_notified_at == ""


@pytest.mark.parametrize(
    ("status", "required_text"),
    [
        ("LOGIN_REQUIRED", "重新扫码登录"),
        ("ADDITIONAL_VERIFICATION_REQUIRED", "附加验证"),
        ("PAGE_CHANGED_OR_UNKNOWN", "暂时不要反复扫码"),
        ("NETWORK_OR_SITE_ERROR", "当前不需要扫码"),
        ("SCRAPER_ERROR", "不等同于登录失效"),
    ],
)
def test_failure_messages_are_status_specific_and_contain_no_auth_material(
    status: str,
    required_text: str,
) -> None:
    _, body = notification.build_failure_message(status, FIXED_TIME)

    assert required_text in body
    assert "flight.ics" in body
    assert "Cookie" in body
    for forbidden in (
        "secret-cookie-value",
        "secret-token-value",
        "secret-app-password",
        '"storage_state"',
    ):
        assert forbidden not in body


def test_active_incident_never_sends_a_second_failure_message(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    messages: list[tuple[str, str, datetime]] = []
    sender = recording_sender(messages)

    assert (
        notification.handle_auth_status(
            "LOGIN_REQUIRED",
            state_path,
            sender,
            FIXED_TIME,
        )
        == "FAILURE_SENT"
    )
    assert (
        notification.handle_auth_status(
            "LOGIN_REQUIRED",
            state_path,
            sender,
            FIXED_TIME,
        )
        == "NO_ACTION"
    )
    assert (
        notification.handle_auth_status(
            "ADDITIONAL_VERIFICATION_REQUIRED",
            state_path,
            sender,
            FIXED_TIME,
        )
        == "INCIDENT_STATUS_UPDATED"
    )

    assert len(messages) == 1
    state = notification.load_state(state_path)
    assert state.incident_active is True
    assert state.last_failure_status == "ADDITIONAL_VERIFICATION_REQUIRED"


def test_recovery_after_incident_sends_exactly_one_message(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    messages: list[tuple[str, str, datetime]] = []
    sender = recording_sender(messages)
    notification.handle_auth_status(
        "NETWORK_OR_SITE_ERROR",
        state_path,
        sender,
        FIXED_TIME,
    )

    first = notification.handle_auth_status(
        "AUTHENTICATED",
        state_path,
        sender,
        FIXED_TIME,
    )
    second = notification.handle_auth_status(
        "AUTHENTICATED",
        state_path,
        sender,
        FIXED_TIME,
    )

    assert first == "RECOVERY_SENT"
    assert second == "NO_ACTION"
    assert len(messages) == 2
    assert "认证已恢复" in messages[-1][0]
    assert "当前不需要再次扫码" in messages[-1][1]
    state = notification.load_state(state_path)
    assert state.incident_active is False
    assert state.recovery_notified_at == "2026-07-24T18:30:00+08:00"


def test_email_failure_does_not_create_or_advance_state(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"

    def fail_send(subject: str, body: str, sent_at: datetime) -> None:
        raise RuntimeError("smtp failed")

    with pytest.raises(RuntimeError, match="smtp failed"):
        notification.handle_auth_status(
            "LOGIN_REQUIRED",
            state_path,
            fail_send,
            FIXED_TIME,
        )
    assert not state_path.exists()

    existing = notification.NotificationState(
        incident_active=True,
        incident_started_at="2026-07-24T17:30:00+08:00",
        failure_notified_at="2026-07-24T17:30:00+08:00",
        last_failure_status="LOGIN_REQUIRED",
        recovery_notified_at="",
    )
    notification.save_state(state_path, existing)
    before = state_path.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="smtp failed"):
        notification.handle_auth_status(
            "AUTHENTICATED",
            state_path,
            fail_send,
            FIXED_TIME,
        )
    assert state_path.read_text(encoding="utf-8") == before


def test_corrupt_state_is_preserved_and_sends_nothing(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{invalid-json", encoding="utf-8")
    messages: list[tuple[str, str, datetime]] = []

    with pytest.raises(notification.NotificationError):
        notification.handle_auth_status(
            "LOGIN_REQUIRED",
            state_path,
            recording_sender(messages),
            FIXED_TIME,
        )

    assert messages == []
    assert state_path.read_text(encoding="utf-8") == "{invalid-json"


def test_unrelated_status_does_not_create_state_or_send_email(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    messages: list[tuple[str, str, datetime]] = []

    result = notification.handle_auth_status(
        "UNRELATED_STATUS",
        state_path,
        recording_sender(messages),
        FIXED_TIME,
    )

    assert result == "NO_ACTION"
    assert messages == []
    assert not state_path.exists()


def test_main_logs_only_safe_error_marker(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    secret_value = "secret-app-password"
    monkeypatch.setenv("GMAIL_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", secret_value)
    monkeypatch.setenv("GMAIL_NOTIFY_TO", "recipient@example.com")
    monkeypatch.setattr(notification, "beijing_now", lambda: FIXED_TIME)
    monkeypatch.setattr(
        notification,
        "send_gmail",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError(secret_value)
        ),
    )
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crew_auth_notification.py",
            "--auth-status",
            "LOGIN_REQUIRED",
            "--state-file",
            str(state_path),
        ],
    )

    assert notification.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "AUTH_NOTIFICATION=ERROR\n"
    assert secret_value not in captured.err
    assert not state_path.exists()


def test_state_file_contains_only_expected_non_sensitive_fields(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    notification.save_state(
        state_path,
        notification.NotificationState(
            incident_active=True,
            incident_started_at="start",
            failure_notified_at="notified",
            last_failure_status="LOGIN_REQUIRED",
            recovery_notified_at="",
        ),
    )

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "incident_active",
        "incident_started_at",
        "failure_notified_at",
        "last_failure_status",
        "recovery_notified_at",
    }
    assert not list(state_path.parent.glob(".*.tmp"))
