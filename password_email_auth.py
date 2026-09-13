"""Isolated #div1 password/email login; never select its phone-verification radio."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

from authenticate_crew_session import (
    PASSWORD_LOGIN_TAB_SELECTOR,
    _cp_cookie_state,
    _recover_post_login_mission_page,
    prepare_login_page_for_auth_method,
)
from crew_auth_session import (
    AuthObservation,
    AuthSignals,
    AuthStatus,
    PASSWORD_INPUT_SELECTOR,
    PASSWORD_USERNAME_SELECTOR,
    is_login_required_status,
)
from springair_email_otp import SpringAirEmailOtpReader


# IDs documented by the read-only CAS DOM inspection, not speculative selectors.
PASSWORD_FORM_SELECTOR = "#fm1"
EMAIL_CODE_SELECTOR = "#networkCode"
EMAIL_REQUEST_SELECTOR = "#btnGetNetworkCode"
EMAIL_SUBMIT_SELECTOR = "#loginBtn1"
MAX_EMAIL_REQUESTS = 2
COUNTDOWN_RE = re.compile(r"[0-9]+\s*(?:秒|s\b)", re.IGNORECASE)


class EmailLoginError(RuntimeError):
    """Only fixed reason codes may escape the new login implementation."""


def _unique_visible(locator: Any) -> Any:
    visible = [locator.nth(i) for i in range(locator.count())
               if locator.nth(i).is_visible()]
    if len(visible) != 1:
        raise EmailLoginError("EMAIL_LOGIN_ELEMENT_UNRESOLVED")
    return visible[0]


def _stage(stage: str, _details: dict[str, Any]) -> None:
    # Existing stage names only; never print details that might contain input.
    print(f"EMAIL_LOGIN_STAGE={stage}")


def _select_email_verification(form: Any) -> None:
    # Resolve semantics from the actual label association, never radio index/value.
    radios = form.get_by_label("邮箱验证", exact=True)
    if radios.count() == 0:
        label = _unique_visible(form.locator("label").filter(
            has_text=re.compile(r"^\s*邮箱验证\s*$"),
        ))
        target_id = label.get_attribute("for")
        radios = (
            form.locator(f"input[id={json.dumps(target_id)}]")
            if target_id else label.locator("input[type='radio']")
        )
    radio = _unique_visible(radios)
    if (radio.get_attribute("type") != "radio"
            or radio.get_attribute("name") != "sendType"):
        raise EmailLoginError("EMAIL_VERIFICATION_METHOD_UNRESOLVED")
    radio.check(timeout=5_000)
    if not radio.is_checked():
        raise EmailLoginError("EMAIL_VERIFICATION_METHOD_UNRESOLVED")
    print("EMAIL_VERIFICATION_METHOD=EMAIL")


def _visible(locator: Any) -> bool:
    return any(locator.nth(i).is_visible() for i in range(locator.count()))


def email_request_accepted(page: Any, form: Any, button: Any) -> bool:
    """Require a resend countdown, not temporary disablement; failure wins."""
    for check in range(26):
        if _visible(page.get_by_text("发送验证码失败", exact=False)):
            return False
        button_text = button.text_content(timeout=1_000) or ""
        button_value = button.get_attribute("value") or ""
        if (COUNTDOWN_RE.search(button_text + button_value)
                or _visible(form.get_by_text(COUNTDOWN_RE))):
            return True
        if check < 25:
            page.wait_for_timeout(200)
    return False


def clear_password_email_inputs(page: Any) -> None:
    """No new screenshots; clear secrets before any existing fallback diagnostics."""
    for selector in (PASSWORD_USERNAME_SELECTOR, PASSWORD_INPUT_SELECTOR,
                     EMAIL_CODE_SELECTOR):
        try:
            inputs = page.locator(PASSWORD_FORM_SELECTOR).locator(selector)
            for i in range(inputs.count()):
                inputs.nth(i).fill("", timeout=1_000)
        except Exception:
            # Fallback performs a fresh navigation before invoking the original flow.
            pass


def attempt_password_email_login(
    page: Any,
    *,
    reader_factory: Callable[[], SpringAirEmailOtpReader] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> AuthObservation:
    reader = None
    requests = 0
    polls = 0
    observation = AuthObservation(AuthStatus.LOGIN_REQUIRED, AuthSignals())
    try:
        observation = prepare_login_page_for_auth_method(page, stage_reporter=_stage)
        if observation.status == AuthStatus.AUTHENTICATED:
            return observation
        if not is_login_required_status(observation.status):
            raise EmailLoginError("EMAIL_LOGIN_PAGE_NOT_READY")
        origin = urlsplit(page.url)
        if origin.scheme != "https" or origin.hostname != "cas.9cair.com":
            raise EmailLoginError("EMAIL_LOGIN_ORIGIN_NOT_ALLOWED")
        username = os.environ.get("CREW_USERNAME", "").strip()
        password = os.environ.get("CREW_PASSWORD", "")
        if not username or not password:
            raise EmailLoginError("EMAIL_LOGIN_CREDENTIALS_MISSING")
        if not os.environ.get("IMAP_EMAIL") or not os.environ.get("IMAP_AUTH_CODE"):
            raise EmailLoginError("EMAIL_LOGIN_MAILBOX_CONFIGURATION_MISSING")

        _unique_visible(page.locator(PASSWORD_LOGIN_TAB_SELECTOR)).click(timeout=5_000)
        form = page.locator(PASSWORD_FORM_SELECTOR)
        form.wait_for(state="visible", timeout=10_000)
        form = _unique_visible(form)
        _unique_visible(form.locator(PASSWORD_USERNAME_SELECTOR)).fill(username)
        _unique_visible(form.locator(PASSWORD_INPUT_SELECTOR)).fill(password)
        _select_email_verification(form)
        code_input = _unique_visible(form.locator(EMAIL_CODE_SELECTOR))
        request_button = _unique_visible(form.locator(EMAIL_REQUEST_SELECTOR))
        submit_button = _unique_visible(form.locator(EMAIL_SUBMIT_SELECTOR))
        print("AUTH_PAGE_TYPE=PASSWORD_EMAIL_OTP")
        print("AUTH_METHOD=PASSWORD_EMAIL_OTP")
        reader = (reader_factory or SpringAirEmailOtpReader.from_environment)()

        for _ in range(MAX_EMAIL_REQUESTS):
            if not request_button.is_enabled():
                raise EmailLoginError("EMAIL_REQUEST_BUTTON_NOT_READY")
            # Baseline is metadata-only. No BODY.PEEK/poll until accepted=true.
            reader.connect()
            baseline_uid = reader.current_max_uid()
            print("EMAIL_IMAP_BASELINE_RECORDED=true")
            # The reader compares this timestamp at RFC Date's whole-second precision.
            requested_at = (clock or (lambda: datetime.now(timezone.utc)))()
            requests += 1
            request_button.click(timeout=5_000)
            accepted = email_request_accepted(page, form, request_button)
            print(f"EMAIL_OTP_REQUEST_ACCEPTED={str(accepted).lower()}")
            if not accepted:
                continue
            polls += 1
            code = reader.wait_for_new_otp(baseline_uid, not_before=requested_at)
            code_input.fill(code)
            baseline_cookies, _ = _cp_cookie_state(page)
            submit_button.click(timeout=5_000)
            try:
                page.wait_for_url("https://cp.9cair.com/**", timeout=30_000,
                                  wait_until="domcontentloaded")
            except Exception:
                pass
            observation = _recover_post_login_mission_page(
                page, stage_reporter=_stage, baseline_cp_cookies=baseline_cookies,
            )
            if observation.status != AuthStatus.AUTHENTICATED:
                raise EmailLoginError("EMAIL_LOGIN_NOT_AUTHENTICATED")
            print("EMAIL_LOGIN_STAGE=MISSION_PAGE_AUTHENTICATED")
            return observation
        raise EmailLoginError("EMAIL_REQUEST_NOT_ACCEPTED")
    except Exception as exc:
        reason = str(exc) if isinstance(exc, EmailLoginError) else "EMAIL_LOGIN_SAFE_FAILURE"
        print(f"EMAIL_LOGIN_FAILURE_REASON={reason}")
        return AuthObservation(AuthStatus.LOGIN_REQUIRED, observation.signals)
    finally:
        clear_password_email_inputs(page)
        if reader is not None:
            try:
                reader.close()
            except Exception:
                print("EMAIL_IMAP_CLOSE=SAFE_FAILURE")
        print(f"EMAIL_OTP_REQUESTS={requests}")
        print(f"EMAIL_IMAP_READS={polls}")
