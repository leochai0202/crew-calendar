from __future__ import annotations

import imaplib
import os
import re
import ssl
import time
from datetime import datetime, timedelta, timezone
from email import policy
from email.header import decode_header
from email.message import Message
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any, Callable


IMAP_HOST = "imap.qq.com"
IMAP_PORT = 993
OTP_SUBJECT = "CREW_OTP"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_POLL_INTERVAL_SECONDS = 3
OTP_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


class OtpError(RuntimeError):
    pass


class OtpConfigurationError(OtpError):
    pass


class OtpMailboxError(OtpError):
    pass


class OtpTimeoutError(OtpError):
    pass


class OtpParseError(OtpError):
    pass


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return unescape("".join(self.parts))


def _decoded_subject(message: Message) -> str:
    raw_subject = message.get("Subject", "")
    decoded: list[str] = []
    for value, charset in decode_header(str(raw_subject)):
        if isinstance(value, bytes):
            decoded.append(
                value.decode(charset or "utf-8", errors="replace")
            )
        else:
            decoded.append(value)
    return "".join(decoded)


def extract_otp_from_text(text: str) -> str | None:
    match = OTP_PATTERN.search(text or "")
    return match.group(1) if match else None


def _text_parts(message: Message) -> list[str]:
    parts: list[str] = []
    candidates = message.walk() if message.is_multipart() else (message,)
    for part in candidates:
        if part.is_multipart():
            continue
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes):
                continue
            content = payload.decode(
                part.get_content_charset() or "utf-8",
                errors="replace",
            )
        if not isinstance(content, str):
            continue
        if content_type == "text/html":
            parser = _HTMLTextExtractor()
            try:
                parser.feed(content)
                content = parser.text()
            except Exception:
                content = re.sub(r"<[^>]+>", "", content)
        parts.append(content)
    return parts


def extract_otp_from_message(
    raw_message: bytes,
    *,
    expected_subject: str = OTP_SUBJECT,
) -> str | None:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
    except Exception as exc:
        raise OtpParseError("验证码邮件无法解析") from exc
    if expected_subject not in _decoded_subject(message):
        return None
    for text in _text_parts(message):
        otp = extract_otp_from_text(text)
        if otp:
            return otp
    return None


def _message_date_utc(message: Message) -> datetime | None:
    raw_date = message.get("Date")
    if not raw_date:
        return None
    try:
        parsed = parsedate_to_datetime(str(raw_date))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ImapOtpReader:
    def __init__(
        self,
        email_address: str,
        auth_code: str,
        *,
        host: str = IMAP_HOST,
        port: int = IMAP_PORT,
        client_factory: Callable[..., Any] = imaplib.IMAP4_SSL,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not email_address or not auth_code:
            raise OtpConfigurationError("163邮箱IMAP配置不完整")
        self._email_address = email_address
        self._auth_code = auth_code
        self._host = host.strip().lower()
        self._port = port
        self._client_factory = client_factory
        self._sleep = sleeper
        self._monotonic = monotonic
        self._client: Any | None = None
        self._mailbox_selected = False

    def __repr__(self) -> str:
        return "ImapOtpReader(<redacted>)"

    @classmethod
    def from_environment(cls, **kwargs: Any) -> "ImapOtpReader":
        return cls(
            os.environ.get("IMAP_EMAIL", "").strip(),
            os.environ.get("IMAP_AUTH_CODE", ""),
            host=IMAP_HOST,
            port=IMAP_PORT,
            **kwargs,
        )

    def connect(self) -> None:
        if self._client is not None:
            return
        client: Any | None = None
        try:
            client = self._client_factory(
                self._host,
                self._port,
                ssl_context=ssl.create_default_context(),
                timeout=30,
            )
            status, _ = client.login(
                self._email_address,
                self._auth_code,
            )
            if status != "OK":
                raise OtpMailboxError("163邮箱IMAP登录失败")
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise OtpMailboxError("163邮箱收件箱无法打开")
            self._client = client
            self._mailbox_selected = True
        except OtpError:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
            raise OtpMailboxError("163邮箱IMAP连接失败") from exc

    def close(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        if self._mailbox_selected:
            try:
                if hasattr(client, "unselect"):
                    client.unselect()
                else:
                    client.close()
            except Exception:
                pass
        self._mailbox_selected = False
        try:
            client.logout()
        except Exception:
            pass

    def __enter__(self) -> "ImapOtpReader":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _require_client(self) -> Any:
        if self._client is None:
            raise OtpMailboxError("163邮箱IMAP尚未连接")
        return self._client

    def current_max_uid(self) -> int:
        client = self._require_client()
        try:
            status, data = client.uid("search", None, "ALL")
        except Exception as exc:
            raise OtpMailboxError("无法读取163邮箱UID基准") from exc
        if status != "OK":
            raise OtpMailboxError("无法读取163邮箱UID基准")
        uids = _parse_uid_search(data)
        return max(uids, default=0)

    def _new_uids(self, baseline_uid: int) -> list[int]:
        client = self._require_client()
        try:
            client.noop()
            status, data = client.uid(
                "search",
                None,
                "UID",
                f"{baseline_uid + 1}:*",
            )
        except Exception as exc:
            raise OtpMailboxError("无法检查新的验证码邮件") from exc
        if status != "OK":
            raise OtpMailboxError("无法检查新的验证码邮件")
        return sorted(
            uid for uid in _parse_uid_search(data) if uid > baseline_uid
        )

    def _fetch_message(self, uid: int) -> bytes:
        client = self._require_client()
        try:
            status, data = client.uid(
                "fetch",
                str(uid),
                "(BODY.PEEK[])",
            )
        except Exception as exc:
            raise OtpMailboxError("新的验证码邮件读取失败") from exc
        if status != "OK":
            raise OtpMailboxError("新的验证码邮件读取失败")
        for item in data or []:
            if (
                isinstance(item, tuple)
                and len(item) >= 2
                and isinstance(item[1], bytes)
            ):
                return item[1]
        raise OtpParseError("新的验证码邮件内容为空")

    def wait_for_new_otp(
        self,
        baseline_uid: int,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        not_before: datetime | None = None,
        clock_skew_seconds: float = 5,
        processed_uids: set[int] | None = None,
        used_otps: set[str] | None = None,
    ) -> str:
        if (
            timeout_seconds <= 0
            or poll_interval_seconds < 0
            or clock_skew_seconds < 0
        ):
            raise ValueError("验证码等待参数无效")
        deadline = self._monotonic() + timeout_seconds
        checked_uids = (
            processed_uids if processed_uids is not None else set()
        )
        rejected_otps = used_otps if used_otps is not None else set()
        earliest_message_time = (
            _as_utc(not_before) - timedelta(seconds=clock_skew_seconds)
            if not_before is not None
            else None
        )
        matching_message_without_code = False

        while True:
            for uid in self._new_uids(baseline_uid):
                if uid in checked_uids:
                    continue
                checked_uids.add(uid)
                raw_message = self._fetch_message(uid)
                try:
                    message = BytesParser(
                        policy=policy.default
                    ).parsebytes(raw_message)
                except Exception as exc:
                    raise OtpParseError("新的验证码邮件无法解析") from exc
                if OTP_SUBJECT not in _decoded_subject(message):
                    continue
                if earliest_message_time is not None:
                    message_time = _message_date_utc(message)
                    if (
                        message_time is None
                        or message_time < earliest_message_time
                    ):
                        continue
                otp = extract_otp_from_message(raw_message)
                if otp:
                    if otp in rejected_otps:
                        continue
                    return otp
                matching_message_without_code = True

            remaining = deadline - self._monotonic()
            if remaining <= 0:
                break
            self._sleep(min(poll_interval_seconds, remaining))

        if matching_message_without_code:
            raise OtpParseError(
                "收到新的CREW_OTP邮件，但未找到4到8位数字验证码"
            )
        raise OtpTimeoutError("等待新的CREW_OTP验证码邮件超时")


def _parse_uid_search(data: Any) -> list[int]:
    if not isinstance(data, (list, tuple)):
        return []
    uids: list[int] = []
    for item in data:
        if not isinstance(item, bytes):
            continue
        for value in item.split():
            try:
                uids.append(int(value))
            except ValueError:
                continue
    return uids
