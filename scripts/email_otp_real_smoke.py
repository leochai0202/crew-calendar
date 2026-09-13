"""One isolated, email-only CAS smoke test using the merged implementation."""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def _safe_dom_attribute(raw: str | None) -> str:
    """Only bounded structural identifiers; never log user data in attributes."""
    if not raw:
        return "NONE"
    if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,79}", raw)
            or re.search(r"[0-9]{6}", raw)):
        return "REDACTED"
    for name in ("CREW_USERNAME", "CREW_PASSWORD", "IMAP_EMAIL", "IMAP_AUTH_CODE"):
        secret = os.environ.get(name, "")
        if secret and secret.casefold() in raw.casefold():
            return "REDACTED"
    return raw


def _report_dom_locator(name, locator) -> None:
    try:
        count = locator.count()
        visible = sum(locator.nth(i).is_visible() for i in range(count))
    except Exception:
        count = visible = "UNAVAILABLE"
    print(f"SMOKE_DOM_{name}_COUNT={count}")
    print(f"SMOKE_DOM_{name}_VISIBLE={visible}")


def diagnose_failed_email_dom(page, auth) -> None:
    """Read counts and whitelisted attributes only, after formal login cleanup."""
    try:
        form = page.locator(auth.PASSWORD_FORM_SELECTOR)
        locators = (
            ("PASSWORD_TAB", page.locator(auth.PASSWORD_LOGIN_TAB_SELECTOR)),
            ("PASSWORD_FORM", form),
            ("USERNAME", form.locator(auth.PASSWORD_USERNAME_SELECTOR)),
            ("PASSWORD", form.locator(auth.PASSWORD_INPUT_SELECTOR)),
            ("EMAIL_LABEL", page.get_by_label("邮箱验证", exact=True)),
            ("SENDTYPE", page.locator("input[name='sendType']")),
            ("EMAIL_CODE", form.locator(auth.EMAIL_CODE_SELECTOR)),
            ("EMAIL_REQUEST", form.locator(auth.EMAIL_REQUEST_SELECTOR)),
            ("EMAIL_SUBMIT", form.locator(auth.EMAIL_SUBMIT_SELECTOR)),
            # These mirror the formal email-radio resolution's form scope.
            ("FORM_EMAIL_LABEL", form.get_by_label("邮箱验证", exact=True)),
            ("FORM_SENDTYPE", form.locator("input[name='sendType']")),
        )
        for name, locator in locators:
            _report_dom_locator(name, locator)
    except Exception:
        print("SMOKE_DOM_LOCATORS_DIAGNOSTIC=SAFE_FAILURE")

    for selector, kind, limit in (("form", "FORM", 10), ("input", "INPUT", 20)):
        try:
            elements = page.locator(selector)
            recorded = 0
            for i in range(elements.count()):
                element = elements.nth(i)
                if not element.is_visible():
                    continue
                recorded += 1
                if kind == "FORM":
                    # The exact `form` selector establishes the tag without HTML.
                    print(f"SMOKE_DOM_FORM_{recorded}_TAG=FORM")
                attributes = ("id", "name") if kind == "FORM" else ("id", "name", "type")
                for attribute in attributes:
                    safe = _safe_dom_attribute(element.get_attribute(attribute))
                    print(f"SMOKE_DOM_{kind}_{recorded}_{attribute.upper()}={safe}")
                if recorded >= limit:
                    break
        except Exception:
            print(f"SMOKE_DOM_{kind}_DIAGNOSTIC=SAFE_FAILURE")


def main() -> int:
    # Process-local only: never read production recovery state or phone secrets.
    for name in (
        "CREW_PHONE", "CREW_LOGIN_PHONE", "CREW_STORAGE_STATE_B64",
        "CREW_PERSISTENT_PROFILE_DIR", "CREW_AUTH_BACKUP_PATH",
        "CREW_AUTH_CONTROL_PATH", "CREW_AUTH_DIAGNOSTIC_PATH",
        "DEBUG", "PWDEBUG", "GITHUB_TOKEN",
    ):
        os.environ.pop(name, None)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    status = "NOT_STARTED"
    reason = "SMOKE_SETUP_SAFE_FAILURE"
    try:
        from playwright.sync_api import sync_playwright

        import password_email_auth
        from crew_auth_session import AuthStatus

        # This controls the real merged function, not a copied login flow.
        password_email_auth.MAX_EMAIL_REQUESTS = 1
        with tempfile.TemporaryDirectory(prefix="crew-email-smoke-") as profile:
            with sync_playwright() as playwright:
                context = None
                try:
                    context = playwright.chromium.launch_persistent_context(
                        user_data_dir=profile, channel="msedge", headless=True,
                    )
                    page = context.new_page()
                    reason = "SMOKE_NAVIGATION_SAFE_FAILURE"
                    page.goto(
                        "https://cp.9cair.com", wait_until="domcontentloaded",
                        timeout=90_000,
                    )
                    page.wait_for_url(
                        "https://cas.9cair.com/**", wait_until="domcontentloaded",
                        timeout=45_000,
                    )
                    reason = "SMOKE_AUTH_SAFE_FAILURE"
                    observation = password_email_auth.attempt_password_email_login(page)
                    status = observation.status.value
                    authenticated = observation.status == AuthStatus.AUTHENTICATED
                    if not authenticated:
                        diagnose_failed_email_dom(page, password_email_auth)
                    final = urlsplit(page.url)
                    print(f"SMOKE_FINAL_HOST={final.hostname or ''}")
                    print(f"SMOKE_FINAL_PATH={final.path or '/'}")
                finally:
                    if context is not None:
                        context.close()
        # Closing the context and deleting the disposable profile precede success.
        print("SMOKE_TEMP_PROFILE_DELETED=true")
        print(f"SMOKE_AUTH_STATUS={status}")
        print(f"SMOKE_RESULT={'SUCCESS' if authenticated else 'FAILED'}")
        return 0 if authenticated else 1
    except Exception:
        # Never expose Playwright/IMAP exception payloads, URLs or secret values.
        print(f"EMAIL_LOGIN_FAILURE_REASON={reason}")
        print(f"SMOKE_AUTH_STATUS={status}")
        print("SMOKE_RESULT=FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
