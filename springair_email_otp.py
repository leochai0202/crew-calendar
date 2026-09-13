"""Strict password-page email OTP parsing; phone OTP behavior stays unchanged."""
from __future__ import annotations

import re
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses

from imap_otp import (
    ImapOtpReader,
    OtpTimeoutError,
    _as_utc,
    _decoded_subject,
    _message_date_utc,
    _text_parts,
)


EMAIL_SUBJECT = "春秋航空统一认证中心-邮箱身份验证"
EMAIL_SENDER_DOMAIN = "postmaster.springairlines.com"
EMAIL_CODE_RE = re.compile(r"验证码为[：:]\s*([0-9]{6})(?![0-9])")


def extract_email_otp(raw_message: bytes, *, not_before: datetime) -> str | None:
    """No broad numeric search, missing date allowance, or clock-skew grace."""
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        if EMAIL_SUBJECT not in _decoded_subject(message):
            return None
        senders = getaddresses(message.get_all("From", []))
        if len(senders) != 1:
            return None
        address = senders[0][1]
        if address.count("@") != 1:
            return None
        if address.rsplit("@", 1)[1].lower() != EMAIL_SENDER_DOMAIN:
            return None
        sent_at = _message_date_utc(message)
        if sent_at is None or sent_at < _as_utc(not_before):
            return None
        codes = {
            match.group(1)
            for part in _text_parts(message)
            for match in EMAIL_CODE_RE.finditer(part)
        }
        return next(iter(codes)) if len(codes) == 1 else None
    except Exception:
        # MIME/server exceptions may include message content. Never expose them.
        return None


class SpringAirEmailOtpReader(ImapOtpReader):
    """Reuse QQ SSL + readonly INBOX + BODY.PEEK transport, not phone parsing."""

    def __repr__(self) -> str:
        return "SpringAirEmailOtpReader(<redacted>)"

    def wait_for_new_otp(
        self,
        baseline_uid: int,
        *,
        not_before: datetime,
        timeout_seconds: float = 120,
        poll_interval_seconds: float = 3,
    ) -> str:
        if baseline_uid < 0 or timeout_seconds <= 0 or poll_interval_seconds <= 0:
            raise ValueError("EMAIL_OTP_WAIT_PARAMETERS_INVALID")
        deadline = self._monotonic() + timeout_seconds
        checked_uids: set[int] = set()
        while True:
            for uid in self._new_uids(baseline_uid):
                # Keep this hard boundary even if a server returns old UIDs.
                if uid <= baseline_uid or uid in checked_uids:
                    continue
                checked_uids.add(uid)
                code = extract_email_otp(
                    self._fetch_message(uid), not_before=not_before,
                )
                if code is not None:
                    return code
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise OtpTimeoutError("EMAIL_OTP_NEW_MATCHING_MESSAGE_TIMEOUT")
            self._sleep(min(poll_interval_seconds, remaining))
