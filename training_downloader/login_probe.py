"""One-shot login/SSO probe. No calendar entry point, downloads, or auth backup IO."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = Path(__file__).resolve().parent / ".runtime"
REQUIRED_ENV = ("CREW_USERNAME", "CREW_PASSWORD", "IMAP_EMAIL", "IMAP_AUTH_CODE")
# Reviewed GitHub blob IDs; CRLF checkouts are normalized before comparison.
REVIEWED = {
    "password_email_auth.py": "2c94000e215cb894b30113b6c1c7d1efd6370df1",
    "springair_email_otp.py": "8d7d16c2111782804b8d7a31aba6b8c6ed644e4a",
    "authenticate_crew_session.py": "5c3a2952d8a392de77ea8d2c1d436550a1b3eea9",
    "crew_auth_session.py": "c402b10897c141e3367ff3bda5b9f2e6398d1d0c",
    "imap_otp.py": "a92114b7ce2517b141c688d1993c38774eadb991",
}
COURSE = ("https://m.yidianzhishi.com/#!/course/18952008429/view?"
          "series_id=0&live_type=9&module_id=117523&module_type=1&qrcode=1&system_type=19")
SSO = ("https://cas.9cair.com/login?service="
       "https%3A%2F%2Fspring.yidianzhishi.com%2Fapi%2Fv1%2Fsso%2Fch%2Flogin%2Fpc")
TARGET = "2026-2027年冬春季定期复训模拟机学员指导手册训练版（0926）.pdf"


def preflight(root: Path = ROOT) -> dict:
    # Presence only: never load .env, backups, browser profiles, or Secret values.
    missing_env = [name for name in REQUIRED_ENV if name not in os.environ]
    missing_source, unreviewed_source = [], []
    for name, expected in REVIEWED.items():
        path = root / name
        if not path.is_file():
            missing_source.append(name)
            continue
        if path.is_symlink():
            unreviewed_source.append(name)
            continue
        data = path.read_bytes().replace(b"\r\n", b"\n")
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != expected:
            unreviewed_source.append(name)
    playwright_present = importlib.util.find_spec("playwright") is not None
    return {
        "status": "ENVIRONMENT_MISSING" if missing_env else (
            "SOURCE_NOT_READY" if missing_source or unreviewed_source else (
                "READY" if playwright_present else "BROWSER_ENVIRONMENT_MISSING")),
        "missing_environment_names": missing_env,
        "missing_source_files": missing_source,
        "unreviewed_source_files": unreviewed_source,
        "playwright_installed": playwright_present,
        "login_attempted": False,
    }


class SingleRequestReader:
    """Stop the original function before its second email-request iteration."""

    def __init__(self, reader):
        self.reader = reader
        self.started = False
        self.accepted = False
        self.received = False

    def __repr__(self):
        return "SingleRequestReader(<redacted>)"

    def connect(self):
        if self.started:
            raise RuntimeError("TRAINING_EMAIL_RETRY_DISABLED")
        self.started = True
        return self.reader.connect()

    def current_max_uid(self):
        return self.reader.current_max_uid()

    def wait_for_new_otp(self, baseline_uid, **kwargs):
        self.accepted = True
        code = self.reader.wait_for_new_otp(baseline_uid, **kwargs)
        self.received = True
        return code

    def close(self):
        return self.reader.close()


@contextlib.contextmanager
def quiet_auth():
    # Do not retain raw library output, exception text, page HTML, or screenshots.
    previous = logging.root.manager.disable
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            logging.disable(logging.CRITICAL)
            try:
                yield
            finally:
                logging.disable(previous)


def visible_text(page, pattern) -> bool:
    matches = page.get_by_text(pattern, exact=False)
    return any(matches.nth(i).is_visible() for i in range(matches.count()))


def course_observation(page) -> dict:
    location = urlsplit(page.url)
    login_required = (location.hostname == "cas.9cair.com"
                      or "/login" in location.path.lower()
                      or "/login" in location.fragment.lower()
                      or visible_text(page, re.compile("请先登录|请登录后|登录已过期|重新登录")))
    passwords = page.locator("input[type='password']")
    login_required = login_required or any(
        passwords.nth(i).is_visible() for i in range(passwords.count()))
    denied = visible_text(page, re.compile("无权访问|暂无权限|没有权限|未授权|无学习权限"))
    on_course = (location.hostname == "m.yidianzhishi.com"
                 and location.fragment.startswith("!/course/18952008429/view"))
    target_visible = visible_text(page, TARGET) if on_course else False
    return {"login_required": login_required, "access_denied": denied,
            "on_target_course": on_course, "target_pdf_listed": target_visible}


def check_before_auth(report: dict) -> None:
    """Keep the second guard mandatory and preserve only fixed failure codes."""
    try:
        from workflow_guard import check_activity, safe_failure
    except Exception:
        report.update(concurrency_failure_reason="CONCURRENCY_GUARD_IMPORT_FAILED",
                      concurrency_check="GUARD_IMPORT")
        raise RuntimeError("CONCURRENCY_CHECK_BLOCKED") from None
    try:
        check_activity()
    except Exception as exc:
        report.update(safe_failure(exc))
        raise RuntimeError("CONCURRENCY_CHECK_BLOCKED") from None


def inspect_course_and_viewer(page, context) -> dict:
    """Only follow the one visible target resource; never save a download."""
    evidence = {"course_heading_visible": False, "course_catalog_visible": False,
                "module_link_count": 0, "target_pdf_accessible": False,
                "pdf_29_pages_confirmed": False, "browser_download_blocked": False}
    headings = page.get_by_role("heading")
    evidence["course_heading_visible"] = any(
        headings.nth(i).is_visible() for i in range(headings.count()))
    evidence["course_catalog_visible"] = visible_text(page, re.compile("课程目录|课件目录|^目录$"))
    links = page.locator("a[href*='module_id=']")
    evidence["module_link_count"] = sum(
        links.nth(i).is_visible() for i in range(links.count()))
    targets = page.get_by_text(TARGET, exact=True)
    visible = [targets.nth(i) for i in range(targets.count()) if targets.nth(i).is_visible()]
    if len(visible) != 1:
        evidence["viewer_check"] = "TARGET_LINK_NOT_UNIQUE"
        return evidence

    def blocked_download(download):
        # accept_downloads=False already prevents saving; cancel the event too.
        evidence["browser_download_blocked"] = True
        download.cancel()

    def watch_page(new_page):
        new_page.on("download", blocked_download)

    previous_pages = list(context.pages)
    metadata_script = """() => {
        const doc = globalThis.PDFViewerApplication?.pdfDocument;
        return doc ? {count: doc.numPages, fingerprint: doc.fingerprints?.[0] ?? null} : null;
    }"""
    baseline = {}
    for existing in previous_pages:
        watch_page(existing)
        for frame in existing.frames:
            try:
                baseline[frame] = frame.evaluate(metadata_script)
            except Exception:
                baseline[frame] = None
    context.on("page", watch_page)
    visible[0].click(timeout=10_000)
    page.wait_for_timeout(3_000)
    viewers = [candidate for candidate in context.pages if candidate not in previous_pages] or [page]
    for viewer in viewers:
        for frame in viewer.frames:
            try:
                # Read only loaded PDF.js metadata, not its bytes, URL, or credentials.
                metadata = frame.evaluate(metadata_script)
                if not isinstance(metadata, dict) or metadata == baseline.get(frame):
                    continue  # Do not attribute an already-open document to this click.
                count = metadata.get("count")
                if isinstance(count, int) and not isinstance(count, bool) and 0 < count < 10000:
                    evidence.update(target_pdf_accessible=True, pdf_page_count=count,
                                    pdf_29_pages_confirmed=count == 29,
                                    viewer_check="LOADED_PDFJS_DOCUMENT")
                    return evidence
            except Exception:
                pass
    evidence["viewer_check"] = ("DOWNLOAD_CANCELLED" if evidence["browser_download_blocked"]
                                else "VIEWER_UNCONFIRMED_NO_CONTENT_EXPORT")
    return evidence


def run_probe(*, headed: bool = False) -> dict:
    report = preflight()
    if report["status"] != "READY":
        return report
    report.update(status="NOT_VERIFIED", cp_authenticated=False,
                  course_access="NOT_TESTED", pdf_29_pages_confirmed=False,
                  course_title_confirmed=False, module_list_confirmed=False)
    # No reuse option: every invocation gets a newly created test-only profile.
    if RUNTIME.is_symlink() or RUNTIME.resolve().parent != Path(__file__).resolve().parent:
        report["status"] = "PROFILE_ISOLATION_ERROR"
        return report
    run_dir = RUNTIME / uuid.uuid4().hex
    profile = run_dir / "edge-profile"
    state_file = run_dir / "auth-status.json"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    phase = "SOURCE_IMPORT_ERROR"
    try:
        with quiet_auth():
            auth = importlib.import_module("password_email_auth")
            otp = importlib.import_module("springair_email_otp")
            from playwright.sync_api import sync_playwright
            # Disable inherited debug logging in this test process only.
            for name in ("DEBUG", "PWDEBUG"):
                os.environ.pop(name, None)
            phase = "BROWSER_ENVIRONMENT_ERROR"
            profile.mkdir(parents=True, exist_ok=False)
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    str(profile), channel="msedge", headless=not headed,
                    accept_downloads=False, viewport={"width": 1400, "height": 1000},
                )
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    phase = "AUTH_NAVIGATION_ERROR"
                    page.goto("https://cp.9cair.com", wait_until="domcontentloaded", timeout=60_000)
                    if os.environ.get("TRAINING_REQUIRE_GUARD") == "1":
                        phase = "CONCURRENCY_CHECK_BLOCKED"
                        check_before_auth(report)
                    phase = "AUTHENTICATION_FAILED"
                    # Status only. No storage_state export, cookies, or OTP on disk.
                    with state_file.open("x", encoding="utf-8") as state:
                        json.dump({"login_attempted": True, "status": "STARTED"}, state)
                    report["login_attempted"] = True
                    reader = SingleRequestReader(otp.SpringAirEmailOtpReader.from_environment())
                    result = auth.attempt_password_email_login(
                        page, reader_factory=lambda: reader,
                    )
                    report["email_request_accepted"] = reader.accepted
                    report["email_otp_received"] = reader.received
                    report["cp_authenticated"] = result.status == auth.AuthStatus.AUTHENTICATED
                    if not report["cp_authenticated"]:
                        report["status"] = ("ADDITIONAL_VERIFICATION_REQUIRED"
                            if result.signals.additional_verification and not result.signals.password_captcha_form
                            else "AUTHENTICATION_NOT_CONFIRMED")
                        return report
                    phase = "COURSE_NAVIGATION_ERROR"
                    page.goto(COURSE, wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_timeout(3_000)
                    seen = course_observation(page)
                    report["sso_handoff_attempted"] = False
                    if seen["login_required"] and not seen["access_denied"]:
                        # One normal CAS service handoff; never request another OTP.
                        phase = "SSO_NAVIGATION_ERROR"
                        report["sso_handoff_attempted"] = True
                        page.goto(SSO, wait_until="domcontentloaded", timeout=60_000)
                        page.wait_for_timeout(3_000)
                        if course_observation(page)["login_required"]:
                            report.update(status="SSO_REAUTH_REQUIRED", course_access="NOT_CONFIRMED")
                            return report
                        page.goto(COURSE, wait_until="domcontentloaded", timeout=60_000)
                        page.wait_for_timeout(3_000)
                        seen = course_observation(page)
                    report.update(seen)
                    if seen["access_denied"]:
                        report.update(status="PERMISSION_DENIED", course_access="DENIED")
                    elif seen["login_required"]:
                        report.update(status="SSO_REAUTH_REQUIRED", course_access="NOT_CONFIRMED")
                    elif seen["on_target_course"] and seen["target_pdf_listed"]:
                        report.update(status="COURSE_TARGET_VISIBLE_INSPECTION_REQUIRED",
                                      course_access="TARGET_LIST_VISIBLE")
                        phase = "COURSE_VIEWER_INSPECTION_ERROR"
                        report.update(inspect_course_and_viewer(page, context))
                        if report["pdf_29_pages_confirmed"]:
                            report["status"] = "TARGET_PDF_ACCESS_CONFIRMED"
                    else:
                        report.update(status="COURSE_STATE_UNKNOWN", course_access="NOT_CONFIRMED")
                    # A generic heading or catalog marker is not proof of the full
                    # course title/module list; those confirmation flags stay false.
                finally:
                    context.close()
    except Exception:
        report["status"] = phase  # Never serialize exception strings/tracebacks.
    finally:
        if state_file.is_file():
            try:
                state_file.write_text(json.dumps({
                    "status": report["status"],
                    "login_attempted": report["login_attempted"],
                    "cp_authenticated": report["cp_authenticated"],
                }), encoding="utf-8")
            except Exception:
                report["state_write_failed"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="One login attempt; default is preflight only")
    parser.add_argument("--headed", action="store_true", help="Show the isolated test browser")
    args = parser.parse_args()
    try:
        report = run_probe(headed=args.headed) if args.run else preflight()
    except Exception:
        report = {"status": "PREFLIGHT_ERROR", "login_attempted": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"READY", "TARGET_PDF_ACCESS_CONFIRMED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
