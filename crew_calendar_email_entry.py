"""Thin production entry: existing session recovery, email first, original phone fallback."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import crew_calendar_main as calendar
from crew_auth_session import AuthObservation, AuthSignals, AuthStatus
from password_email_auth import attempt_password_email_login


_ORIGINAL_DYNAMIC_PHONE_LOGIN = calendar.attempt_cloud_dynamic_password_login


def email_first_then_original_phone(
    page: Any, *, auth_control_path: Path | None = None, now: datetime | None = None,
) -> AuthObservation:
    observation = attempt_password_email_login(page)
    if observation.status == AuthStatus.AUTHENTICATED:
        # Email returns through run()'s unchanged profile/backup persistence.
        print("OTP_REQUESTS=0")
        print("IMAP_READS=0")
        return observation
    print("EMAIL_LOGIN_FALLBACK=EXISTING_DYNAMIC_PASSWORD_PHONE")
    try:
        # Discard the password tab's state. Never select its phone radio.
        page.goto(calendar.LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    except Exception:
        print("EMAIL_LOGIN_FALLBACK_NAVIGATION=NETWORK_OR_SITE_ERROR")
        return AuthObservation(AuthStatus.NETWORK_OR_SITE_ERROR, AuthSignals())
    return _ORIGINAL_DYNAMIC_PHONE_LOGIN(
        page, auth_control_path=auth_control_path, now=now,
    )


def run() -> int:
    original = calendar.attempt_cloud_dynamic_password_login
    calendar.attempt_cloud_dynamic_password_login = email_first_then_original_phone
    try:
        return calendar.run()
    finally:
        calendar.attempt_cloud_dynamic_password_login = original


if __name__ == "__main__":
    raise SystemExit(run())
