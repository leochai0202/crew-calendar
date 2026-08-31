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
    "LOGIN_REQUIRED_PASSWORD_CAPTCHA_FAILED",
    "LOGIN_REQUIRED_DYNAMIC_OTP",
    "ADDITIONAL_VERIFICATION_REQUIRED",
    "PAGE_CHANGED_OR_UNKNOWN",
}

STATUS_EXPLANATIONS = {
    "LOGIN_REQUIRED": (
        "云端认证会话已经失效或缺失。",
        "需要在本机重新扫码登录。",
    ),
    "LOGIN_REQUIRED_PASSWORD_CAPTCHA_FAILED": (
        "账号密码图片验证码登录连续三次未能完成。",
        "请检查账号密码配置及安全诊断截图；程序没有请求动态验证码。",
    ),
    "LOGIN_REQUIRED_DYNAMIC_OTP": (
        "网站已确认显示动态验证码登录页，但动态验证码登录未能启动。",
        "请检查手机和QQ邮箱验证码配置。",
    ),
    "ADDITIONAL_VERIFICATION_REQUIRED": (
        "网站要求完成手机、短信、邮箱或其他附加验证。",
        "需要在本机浏览器中按网站提示完成人工验证。",
    ),
    "PAGE_CHANGED_OR_UNKNOWN": (
        "页面已经加载，但程序无法安全确认当前认证状态，可能存在页面结构或权限变化。",
        "暂时不要反复扫码，请先在本机检查网站页面是否发生变化。",
    ),
}

FAILURE_SUBJECTS = {
    "LOGIN_REQUIRED": "【Crew Calendar】登录认证已失效",
    "LOGIN_REQUIRED_PASSWORD_CAPTCHA_FAILED": (
        "【Crew Calendar】账号密码图片验证码登录失败"
    ),
    "LOGIN_REQUIRED_DYNAMIC_OTP": (
        "【Crew Calendar】动态验证码登录未能启动"
    ),
    "ADDITIONAL_VERIFICATION_REQUIRED": "【Crew Calendar】需要人工完成附加验证",
    "PAGE_CHANGED_OR_UNKNOWN": "【Crew Calendar】无法安全确认登录状态",
}

CREW_TASK_URL = "https://cp.9cair.com/html/task/mission.html"
GITHUB_ACTIONS_URL = (
    "https://github.com/leochai0202/crew-calendar/actions"
)
GITHUB_ACTIONS_SECRETS_URL = (
    "https://github.com/leochai0202/crew-calendar/settings/secrets/actions"
)


class NotificationError(RuntimeError):
    pass


class MissingGmailConfiguration(NotificationError):
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


def build_recovery_steps() -> list[str]:
    return [
        "1. 使用电脑打开项目目录：",
        "   D:\\GGITHUB\\crew-calendar",
        "",
        "2. 在该目录打开终端，运行：",
        "   python authenticate_crew_session.py",
        "",
        "3. 浏览器打开后，按照网站提示正常扫码登录；如出现短信、邮箱或其他验证，人工完成验证。",
        "   程序不得自动绕过任何验证。",
        "",
        "4. 等待终端显示：",
        "   AUTHENTICATED",
        "",
        "5. 在项目目录的PowerShell中运行下面整条命令，把新的认证内容复制到剪贴板：",
        "   python -c \"from pathlib import Path; from crew_auth_session import load_auth_bundle_file, encode_auth_bundle; print(encode_auth_bundle(load_auth_bundle_file(Path(r'playwright/.auth/crew-auth-session.storage-state.json'))).decode('ascii'))\" | Set-Clipboard",
        "",
        "   然后，按以下操作更新GitHub Secret：",
        "   - 打开：",
        f"     {GITHUB_ACTIONS_SECRETS_URL}",
        "   - 找到：",
        "     CREW_STORAGE_STATE_B64",
        "   - 点击Update；",
        "   - 将剪贴板内容粘贴进去；",
        "   - 点击Update secret保存。",
        "",
        "   安全提醒：上述剪贴板内容属于完整认证包；不要粘贴到邮件、聊天、日志或其他地方。",
        "   更新Secret后继续执行原来的第6至第9步。",
        "   邮件中不会显示任何真实认证内容。",
        "",
        "6. 打开仓库Actions页面：",
        f"   {GITHUB_ACTIONS_URL}",
        "",
        "7. 运行：",
        "   Crew authentication session check",
        "",
        "8. 检查结果是否为绿色成功，并确认日志状态为：",
        "   AUTHENTICATED",
        "",
        "9. 验证成功后，可以等待下一次自动更新；如需立即更新日历，再手动运行：",
        "   Update Crew Calendar",
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
        "保护结果：认证失败期间 flight.ics 不会被覆盖，清洗和ICS提交被门控阻止，现有手机日历会继续保留。",
        "",
        "【你需要怎么做】",
        "",
        *build_recovery_steps(),
        "",
        "快捷链接：",
        "机组任务页面：",
        CREW_TASK_URL,
        "",
        "GitHub Secrets设置页面：",
        GITHUB_ACTIONS_SECRETS_URL,
        "",
        "GitHub Actions页面：",
        GITHUB_ACTIONS_URL,
        "",
        "重要提醒：",
        "- 只在网页中重新登录，不能自动恢复GitHub云端认证。",
        "- 必须重新运行 authenticate_crew_session.py 并更新 CREW_STORAGE_STATE_B64。",
        "- 认证失败期间 flight.ics 不会被覆盖，现有手机日历会继续保留。",
        "- 不要通过邮件、聊天或日志发送Cookie、Token、密码或完整认证包。",
    ]
    return FAILURE_SUBJECTS[status], "\n".join(body)


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
        "保护结果：故障期间正式 flight.ics 未被覆盖，清洗和ICS提交曾被门控阻止。",
        "是否需要验证：当前不需要再次扫码、短信或邮箱验证。",
        "",
        "后续操作：无需处理；如任务解析正常，日历将继续按原有流程更新。",
        "如以后需要恢复，请运行 python authenticate_crew_session.py，更新 CREW_STORAGE_STATE_B64，并确认云端状态为 AUTHENTICATED。",
        "",
        "程序不会自动绕过扫码、短信、邮箱或二次验证。",
        "安全提示：本邮件不包含Cookie、Token、密码或认证包。",
    ]
    return "【Crew Calendar】登录认证已恢复", "\n".join(body)


def gmail_config_from_environment() -> GmailConfig:
    sender = os.environ.get("GMAIL_SMTP_USER", "").strip()
    app_password = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "")
    recipient = os.environ.get("CREW_NOTIFY_EMAIL", "").strip()
    if not sender or not app_password or not recipient:
        raise MissingGmailConfiguration("邮件配置缺失")
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

    if normalized not in FAILURE_STATUSES and normalized != AUTHENTICATED:
        return "NO_ACTION"

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
    except MissingGmailConfiguration:
        print("邮件配置缺失，跳过通知", flush=True)
        return 0
    except Exception:
        print("AUTH_NOTIFICATION=ERROR", file=sys.stderr, flush=True)
        return 1

    print(f"AUTH_NOTIFICATION={result}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
