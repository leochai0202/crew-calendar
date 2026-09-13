"""One isolated, email-only CAS smoke test using the merged implementation."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


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
                    final = urlsplit(page.url)
                    print(f"SMOKE_FINAL_HOST={final.hostname or ''}")
                    print(f"SMOKE_FINAL_PATH={final.path or '/'}")
                    authenticated = observation.status == AuthStatus.AUTHENTICATED
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
