from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime

import pytest

from imap_otp import OtpTimeoutError
from springair_email_otp import (
    EMAIL_SUBJECT, SpringAirEmailOtpReader, extract_email_otp,
)


NOW = datetime(2026, 9, 13, 4, 0, tzinfo=timezone.utc)


def message(*, subject=EMAIL_SUBJECT,
            sender="SpringAirlines <springairlines@postmaster.springairlines.com>",
            sent_at=NOW, text="您正在进行邮箱验证，本次请求的验证码为：205083",
            html=False):
    mail = EmailMessage()
    mail["Subject"] = subject
    mail["From"] = sender
    if sent_at is not None:
        mail["Date"] = format_datetime(sent_at)
    mail.set_content(text, subtype="html" if html else "plain")
    return mail.as_bytes()


@pytest.mark.parametrize("html", [False, True])
def test_exact_email_identity_code_and_date(html):
    text = ("验证码为：<strong>205083</strong>" if html else
            "验证码为：205083（请在5分钟内完成验证）")
    assert extract_email_otp(message(text=text, html=html), not_before=NOW) == "205083"


@pytest.mark.parametrize("changes", [
    {"subject": "CREW_OTP"},
    {"subject": "其他邮箱身份验证"},
    {"sender": "springairlines@evil.example"},
    {"sender": "springairlines@postmaster.springairlines.com.evil.example"},
    {"sender": "springairlines@springairlines.com"},
    {"sender": "a@postmaster.springairlines.com, b@postmaster.springairlines.com"},
    {"sent_at": NOW - timedelta(seconds=1)},
    {"sent_at": None},
    {"text": "订单205083，有效期5分钟"},
    {"text": "验证码为：20508"},
    {"text": "验证码为：2050839"},
    {"text": "验证码为：205083；验证码为：678901"},
])
def test_rejects_wrong_identity_stale_missing_date_and_arbitrary_digits(changes):
    assert extract_email_otp(message(**changes), not_before=NOW) is None


@pytest.mark.parametrize("sent_at,expected", [
    (NOW, "205083"),
    (NOW - timedelta(seconds=1), None),
])
def test_email_date_uses_same_second_precision_but_rejects_previous_second(sent_at, expected):
    assert extract_email_otp(
        message(sent_at=sent_at), not_before=NOW.replace(microsecond=700_000),
    ) == expected


class Mailbox:
    def __init__(self, messages):
        self.messages = messages
        self.events = []

    def login(self, *_credentials):
        self.events.append("login")
        return "OK", []

    def select(self, name, *, readonly):
        self.events.append(("select", name, readonly))
        return "OK", []

    def uid(self, command, *args):
        self.events.append((command, args))
        if command == "search":
            return "OK", [b"7" if args[-1] == "ALL" else b"7 8 9"]
        assert command == "fetch"
        return "OK", [(b"metadata", self.messages[int(args[0])])]

    def noop(self):
        return "OK", []

    def unselect(self):
        return "OK", []

    def logout(self):
        return "BYE", []


def reader_with(mailbox):
    elapsed = [0.0]

    def factory(host, port, **options):
        assert (host, port) == ("imap.qq.com", 993)
        assert options["ssl_context"] is not None
        return mailbox

    def sleep(seconds):
        elapsed[0] += seconds

    return SpringAirEmailOtpReader(
        "test@example.invalid", "redacted-test-auth", client_factory=factory,
        sleeper=sleep, monotonic=lambda: elapsed[0],
    )


def test_new_uid_only_readonly_ssl_and_body_peek(capsys):
    mailbox = Mailbox({8: message(subject="CREW_OTP"), 9: message()})
    reader = reader_with(mailbox)
    with reader:
        baseline = reader.current_max_uid()
        assert reader.wait_for_new_otp(
            baseline, not_before=NOW.replace(microsecond=700_000),
        ) == "205083"
    assert ("select", "INBOX", True) in mailbox.events
    fetched = [event[1] for event in mailbox.events
               if isinstance(event, tuple) and event[0] == "fetch"]
    assert fetched == [("8", "(BODY.PEEK[])"), ("9", "(BODY.PEEK[])")]
    assert capsys.readouterr().out == ""
    assert "redacted-test-auth" not in repr(reader)


def test_old_uid_and_old_date_never_used_even_if_server_returns_them():
    mailbox = Mailbox({8: message(sent_at=NOW - timedelta(seconds=1)),
                       9: message(sender="bad@example.invalid")})
    reader = reader_with(mailbox)
    with reader, pytest.raises(OtpTimeoutError):
        reader.wait_for_new_otp(
            7, not_before=NOW.replace(microsecond=700_000), timeout_seconds=1,
        )
    assert not any(event == ("fetch", ("7", "(BODY.PEEK[])"))
                   for event in mailbox.events)
