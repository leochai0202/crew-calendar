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

EXPECTED_SUBJECTS = {
    "LOGIN_REQUIRED": "【Crew Calendar】登录认证已失效",
    "ADDITIONAL_VERIFICATION_REQUIRED": "【Crew Calendar】需要人工完成附加验证",
    "PAGE_CHANGED_OR_UNKNOWN": "【Crew Calendar】无法安全确认登录状态",
}
RECOVERY_SUBJECT = "【Crew Calendar】登录认证已恢复"
REQUIRED_LINKS = (
    "https://cp.9cair.com/html/task/mission.html",
    "https://github.com/leochai0202/crew-calendar/actions",
    "https://github.com/leochai0202/crew-calendar/settings/secrets/actions",
)
REQUIRED_STEP_HEADINGS = tuple(f"{number}." for number in range(1, 10))


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
    assert subject == EXPECTED_SUBJECTS["LOGIN_REQUIRED"]
    assert "检测时间（北京时间）" in body
    assert "现有手机日历会继续保留" in body
    assert "python authenticate_crew_session.py" in body
    assert "更新GitHub Secret" in body
    assert "CREW_STORAGE_STATE_B64" in body
    assert sent_at is FIXED_TIME

    state = notification.load_state(state_path)
    assert state.incident_active is True
    assert state.last_failure_status == "LOGIN_REQUIRED"
    assert state.failure_notified_at == "2026-07-24T18:30:00+08:00"
    assert state.recovery_notified_at == ""


@pytest.mark.parametrize(
    ("status", "required_text", "expected_subject"),
    [
        (
            "LOGIN_REQUIRED",
            "重新扫码登录",
            "【Crew Calendar】登录认证已失效",
        ),
        (
            "ADDITIONAL_VERIFICATION_REQUIRED",
            "附加验证",
            "【Crew Calendar】需要人工完成附加验证",
        ),
        (
            "PAGE_CHANGED_OR_UNKNOWN",
            "暂时不要反复扫码",
            "【Crew Calendar】无法安全确认登录状态",
        ),
    ],
)
def test_failure_messages_have_exact_subject_and_complete_recovery_guide(
    status: str,
    required_text: str,
    expected_subject: str,
) -> None:
    subject, body = notification.build_failure_message(status, FIXED_TIME)

    assert subject == expected_subject
    assert required_text in body
    assert "【你需要怎么做】" in body
    step_positions = [
        body.index(step_heading)
        for step_heading in REQUIRED_STEP_HEADINGS
    ]
    assert step_positions == sorted(step_positions)
    for link in REQUIRED_LINKS:
        assert link in body
    for required_text in (
        "D:\\GGITHUB\\crew-calendar",
        "python authenticate_crew_session.py",
        "程序不得自动绕过任何验证",
        "from crew_auth_session import load_auth_bundle_file, encode_auth_bundle",
        "load_auth_bundle_file",
        "encode_auth_bundle",
        "playwright/.auth/crew-auth-session.storage-state.json",
        "Set-Clipboard",
        "CREW_STORAGE_STATE_B64",
        "点击Update",
        "将剪贴板内容粘贴进去",
        "点击Update secret保存",
        "安全提醒",
        "上述剪贴板内容属于完整认证包",
        "不要粘贴到邮件、聊天、日志或其他地方",
        "更新Secret后继续执行原来的第6至第9步",
        "邮件中不会显示任何真实认证内容",
        "Crew authentication session check",
        "检查结果是否为绿色成功",
        "AUTHENTICATED",
        "Update Crew Calendar",
        "只在网页中重新登录，不能自动恢复GitHub云端认证",
        "必须重新运行 authenticate_crew_session.py 并更新 CREW_STORAGE_STATE_B64",
        "认证失败期间 flight.ics 不会被覆盖",
        "现有手机日历会继续保留",
        "清洗和ICS提交被门控阻止",
        "不要通过邮件、聊天或日志发送Cookie、Token、密码或完整认证包",
    ):
        assert required_text in body
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


@pytest.mark.parametrize(
    "status",
    ["NETWORK_OR_SITE_ERROR", "SCRAPER_ERROR"],
)
def test_non_auth_failure_does_not_send_or_create_state(
    status: str,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    messages: list[tuple[str, str, datetime]] = []

    result = notification.handle_auth_status(
        status,
        state_path,
        recording_sender(messages),
        FIXED_TIME,
    )

    assert result == "NO_ACTION"
    assert messages == []
    assert not state_path.exists()


def test_non_auth_failures_preserve_incident_and_recovery_sends_once(
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
    before = state_path.read_bytes()

    for status in ("NETWORK_OR_SITE_ERROR", "SCRAPER_ERROR"):
        assert (
            notification.handle_auth_status(
                status,
                state_path,
                sender,
                FIXED_TIME,
            )
            == "NO_ACTION"
        )
        assert state_path.read_bytes() == before

    first_recovery = notification.handle_auth_status(
        "AUTHENTICATED",
        state_path,
        sender,
        FIXED_TIME,
    )
    second_recovery = notification.handle_auth_status(
        "AUTHENTICATED",
        state_path,
        sender,
        FIXED_TIME,
    )

    assert first_recovery == "RECOVERY_SENT"
    assert second_recovery == "NO_ACTION"
    assert len(messages) == 2
    assert messages[-1][0] == RECOVERY_SUBJECT
    assert "当前不需要再次扫码" in messages[-1][1]
    for required_text in (
        "当前状态：AUTHENTICATED",
        "检测时间（北京时间）",
        "flight.ics 未被覆盖",
        "清洗和ICS提交曾被门控阻止",
        "python authenticate_crew_session.py",
        "CREW_STORAGE_STATE_B64",
        "AUTHENTICATED",
        "不会自动绕过扫码、短信、邮箱或二次验证",
    ):
        assert required_text in messages[-1][1]
    state = notification.load_state(state_path)
    assert state.incident_active is False
    assert state.last_failure_status == "LOGIN_REQUIRED"
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


@pytest.mark.parametrize(
    ("status", "existing_incident"),
    [
        ("LOGIN_REQUIRED", False),
        ("AUTHENTICATED", True),
    ],
)
def test_main_missing_mail_config_is_safe_and_preserves_state(
    status: str,
    existing_incident: bool,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    for variable in (
        "GMAIL_SMTP_USER",
        "GMAIL_SMTP_APP_PASSWORD",
        "CREW_NOTIFY_EMAIL",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(notification, "beijing_now", lambda: FIXED_TIME)
    state_path = tmp_path / "state.json"
    if existing_incident:
        notification.save_state(
            state_path,
            notification.NotificationState(
                incident_active=True,
                incident_started_at="2026-07-24T17:30:00+08:00",
                failure_notified_at="2026-07-24T17:30:00+08:00",
                last_failure_status="LOGIN_REQUIRED",
                recovery_notified_at="",
            ),
        )
        before = state_path.read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crew_auth_notification.py",
            "--auth-status",
            status,
            "--state-file",
            str(state_path),
        ],
    )

    assert notification.main() == 0
    captured = capsys.readouterr()
    assert captured.out == "邮件配置缺失，跳过通知\n"
    assert captured.err == ""
    if existing_incident:
        assert state_path.read_bytes() == before
    else:
        assert not state_path.exists()


def test_main_logs_only_safe_error_marker(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    secret_value = "secret-app-password"
    monkeypatch.setenv("GMAIL_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", secret_value)
    monkeypatch.setenv("CREW_NOTIFY_EMAIL", "recipient@example.com")
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
