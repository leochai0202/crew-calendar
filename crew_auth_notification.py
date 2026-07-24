from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo


BEIJING_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_STATE_FILE = Path("state/auth_notification_state.json")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

AUTHENTICATED = "AUTHENTICATED"
FAILURE_STATUSES = {
    "LOGIN_REQUIRED",
    "ADDITIONAL_VERIFICATION_REQUIRED",
    "PAGE_CHANGED_OR_UNKNOWN",
    "NETWORK_OR_SITE_ERROR",
    "SCRAPER_ERROR",
}

STATUS_EXPLANATIONS = {
    "LOGIN_REQUIRED": (
        "云端认证会话已经失效或缺失。",
        "需要在本机重新扫码登录。",
    ),
    "ADDITIONAL_VERIFICATION_REQUIRED": (
        "网站要求完成手机、短信、邮箱或其他附加验证。",
        "需要在本机浏览器中按网站提示完成人工验证。",
    ),
    "PAGE_CHANGED_OR_UNKNOWN": (
        "页面已经加载，但程序无法安全确认当前认证状态，可能存在页面结构或权限变化。",
        "暂时不要反复扫码，请先在本机检查网站页面是否发生变化。",
    ),
    "NETWORK_OR_SITE_ERROR": (
        "GitHub Runner访问网站时遇到网络或站点服务异常。",
        "当前不需要扫码；请等待下一次运行，或确认网站是否可以正常访问。",
    ),
    "SCRAPER_ERROR": (
        "正式抓取发生普通错误，本次无法确认认证与任务处理是否完整完成。",
        "这不等同于登录失效，请先查看GitHub Actions的脱敏状态。",
    ),
}


class NotificationError(RuntimeError):
    pass


@dataclass
class NotificationState:
    incident_active: bool = False
    incident_started_at: str = ""
    failure_notified_at: str = ""
    last_failure_status: str = ""
    recovery_notified_at: str = ""


@dataclass(frozen=True)
class GmailConfig:
    sender: str
    app_password: str
    recipient: str


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def isoformat_beijing(value: datetime) -> str:
    return value.astimezone(BEIJING_TZ).isoformat(timespec="seconds")


def display_time_beijing(value: datetime) -> str:
    return value.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def load_state(path: Path) -> NotificationState:
    if not path.exists():
        return NotificationState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NotificationError("通知状态文件无法安全读取") from exc
    if not isinstance(payload, dict):
        raise NotificationError("通知状态文件格式无效")

    expected = {
        "incident_active": bool,
        "incident_started_at": str,
        "failure_notified_at": str,
        "last_failure_status": str,
        "recovery_notified_at": str,
    }
    for key, expected_type in expected.items():
        if key not in payload or not isinstance(payload[key], expected_type):
            raise NotificationError("通知状态文件格式无效")
    return NotificationState(
        incident_active=payload["incident_active"],
        incident_started_at=payload["incident_started_at"],
        failure_notified_at=payload["failure_notified_at"],
        last_failure_status=payload["last_failure_status"],
        recovery_notified_at=payload["recovery_notified_at"],
    )


def save_state(path: Path, state: NotificationState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                asdict(state),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_recovery_steps(status: str) -> list[str]:
    if status == "NETWORK_OR_SITE_ERROR":
        return [
            "1. 暂时无需扫码或更新认证Secret；",
            "2. 检查网站是否可以正常访问；",
            "3. 等待下一次定时运行，必要时手动运行认证检查工作流。",
        ]
    if status == "PAGE_CHANGED_OR_UNKNOWN":
        return [
            "1. 打开电脑并进入 D:\\GGITHUB\\crew-calendar；",
            "2. 运行 python authenticate_crew_session.py --validate-existing；",
            "3. 如本机认证有效，请检查网站页面结构或权限是否发生变化；",
            "4. 如本机也要求登录，再运行 python authenticate_crew_session.py 完成人工认证；",
            "5. 安全更新 CREW_STORAGE_STATE_B64，并手动运行认证检查。",
        ]
    if status == "SCRAPER_ERROR":
        return [
            "1. 打开GitHub Actions并查看本次运行的脱敏状态；",
            "2. 不要从日志复制或发送Cookie、Token或认证包；",
            "3. 如认证检查失败，再按本机人工认证流程恢复。",
        ]
    return [
        "1. 打开电脑；",
        "2. 进入 D:\\GGITHUB\\crew-calendar；",
        "3. 运行 python authenticate_crew_session.py；",
        "4. 在弹出的浏览器中正常扫码，并完成网站要求的短信或邮箱验证；",
        "5. 等待程序显示 AUTHENTICATED；",
        "6. 安全更新 GitHub Secret CREW_STORAGE_STATE_B64；",
        "7. 手动运行 auth-session-check；",
        "8. 确认云端检查恢复为 AUTHENTICATED。",
    ]


def build_failure_message(status: str, detected_at: datetime) -> tuple[str, str]:
    explanation, verification = STATUS_EXPLANATIONS[status]
    body = [
        "Crew Calendar 认证状态提醒",
        "",
        f"当前状态：{status}",
        f"检测时间（北京时间）：{display_time_beijing(detected_at)}",
        "",
        f"当前发生了什么：{explanation}",
        f"是否需要验证：{verification}",
        "",
        "保护结果：本次失败运行不会清洗、生成、提交或覆盖正式 flight.ics，原有日历继续保留。",
        "",
        "恢复步骤：",
        *build_recovery_steps(status),
        "",
        "安全提示：请勿通过邮件或日志发送Cookie、Token、密码或完整认证包。",
    ]
    return "[crew-calendar] 航班日历认证需要处理", "\n".join(body)


def build_recovery_message(
    previous_status: str,
    detected_at: datetime,
) -> tuple[str, str]:
    body = [
        "Crew Calendar 认证恢复提醒",
        "",
        "当前状态：AUTHENTICATED",
        f"检测时间（北京时间）：{display_time_beijing(detected_at)}",
        f"上一故障状态：{previous_status or 'UNKNOWN'}",
        "",
        "当前发生了什么：GitHub Runner已经重新确认认证有效，正式任务处理流程可以继续。",
        "保护结果：故障期间原有 flight.ics 没有被失败运行覆盖。",
        "是否需要验证：当前不需要再次扫码、短信或邮箱验证。",
        "",
        "后续操作：无需处理；如任务解析正常，日历将继续按原有流程更新。",
        "",
        "安全提示：本邮件不包含Cookie、Token、密码或认证包。",
    ]
    return "[crew-calendar] 航班日历认证已恢复", "\n".join(body)


def gmail_config_from_environment() -> GmailConfig:
    sender = os.environ.get("GMAIL_SMTP_USER", "").strip()
    app_password = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "")
    recipient = os.environ.get("GMAIL_NOTIFY_TO", "").strip()
    if not sender or not app_password or not recipient:
        raise NotificationError("Gmail通知配置缺失")
    return GmailConfig(sender, app_password, recipient)


def send_gmail(
    config: GmailConfig,
    subject: str,
    body: str,
    sent_at: datetime,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.sender
    message["To"] = config.recipient
    message["Date"] = format_datetime(sent_at.astimezone(BEIJING_TZ))
    message.set_content(body, subtype="plain", charset="utf-8")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        SMTP_HOST,
        SMTP_PORT,
        timeout=30,
        context=context,
    ) as smtp:
        smtp.login(config.sender, config.app_password)
        smtp.send_message(message)


def handle_auth_status(
    status: str,
    state_path: Path,
    send_email: Callable[[str, str, datetime], None],
    detected_at: datetime,
) -> str:
    normalized = (status or "SCRAPER_ERROR").strip().upper()
    state = load_state(state_path)

    if normalized in FAILURE_STATUSES:
        if state.incident_active:
            if state.last_failure_status != normalized:
                state.last_failure_status = normalized
                save_state(state_path, state)
                return "INCIDENT_STATUS_UPDATED"
            return "NO_ACTION"

        subject, body = build_failure_message(normalized, detected_at)
        send_email(subject, body, detected_at)
        timestamp = isoformat_beijing(detected_at)
        save_state(
            state_path,
            NotificationState(
                incident_active=True,
                incident_started_at=timestamp,
                failure_notified_at=timestamp,
                last_failure_status=normalized,
                recovery_notified_at="",
            ),
        )
        return "FAILURE_SENT"

    if normalized == AUTHENTICATED and state.incident_active:
        subject, body = build_recovery_message(
            state.last_failure_status,
            detected_at,
        )
        send_email(subject, body, detected_at)
        state.incident_active = False
        state.recovery_notified_at = isoformat_beijing(detected_at)
        save_state(state_path, state)
        return "RECOVERY_SENT"

    return "NO_ACTION"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send deduplicated Chinese authentication notifications."
    )
    parser.add_argument("--auth-status", required=True)
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    detected_at = beijing_now()

    def send_email(subject: str, body: str, sent_at: datetime) -> None:
        send_gmail(
            gmail_config_from_environment(),
            subject,
            body,
            sent_at,
        )

    try:
        result = handle_auth_status(
            args.auth_status,
            Path(args.state_file),
            send_email,
            detected_at,
        )
    except Exception:
        print("AUTH_NOTIFICATION=ERROR", file=sys.stderr, flush=True)
        return 1

    print(f"AUTH_NOTIFICATION={result}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
