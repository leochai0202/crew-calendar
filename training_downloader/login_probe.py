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
from urllib.parse import parse_qs, quote, urljoin, urlsplit
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
PROJECT = "2026-2027年冬春季定期复训模拟机学员指导手册训练版"
# Exact user-confirmed learning-task address; never construct an SSO address.
COURSE = ("https://spring.yidianzhishi.com/personal.html#!/task/player?"
          "learning_id=117523&learning_type=1&task_id=18952008429&task_type=2&"
          "is_classes=1&attend_id=0&project_name=" + quote(PROJECT, safe=""))
TARGET = "2026-2027年冬春季定期复训模拟机学员指导手册训练版（0926）.pdf"
LOGIN_ENTRY_NAME = re.compile(r"^(?:登录|去登录|立即登录|统一认证登录|春秋统一认证登录|企业登录|SSO登录)$")
SSO_BUTTON_NAME = re.compile(r"^(?:统一认证登录|春秋统一认证登录|企业登录|SSO登录)$")


def domain_category(url: str) -> str:
    try:
        location = urlsplit(url)
        if location.scheme != "https":
            return "OTHER"
        return {"cas.9cair.com": "CAS", "cp.9cair.com": "CREW_PORTAL",
                "m.yidianzhishi.com": "TRAINING_MOBILE",
                "spring.yidianzhishi.com": "TRAINING_TENANT"}.get(location.hostname, "OTHER")
    except ValueError:
        return "OTHER"


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
    category = domain_category(page.url)
    recognized = category in {"CAS", "TRAINING_MOBILE", "TRAINING_TENANT"}
    # CAS and /login are routing hints only. A normal SSO callback contains /login.
    inputs = page.locator("input[type='password'], input[autocomplete='one-time-code']")
    login_form_visible = recognized and any(
        inputs.nth(i).is_visible() for i in range(inputs.count()))
    login_prompt_visible = recognized and visible_text(
        page, re.compile(r"请先登录|请登录后|登录已过期|重新登录|^扫码登录$|^二维码登录$|^账号密码登录$|^请完成身份验证$"))
    login_required = login_form_visible or login_prompt_visible
    denied = visible_text(page, re.compile("无权访问|暂无权限|没有权限|未授权|无学习权限"))
    route, _, query = location.fragment.partition("?")
    params = parse_qs(query)
    on_course = (category == "TRAINING_TENANT" and location.path == "/personal.html"
                 and route == "!/task/player" and all(params.get(key) == [value] for key, value in {
                     "learning_id": "117523", "learning_type": "1",
                     "task_id": "18952008429", "task_type": "2"}.items()))
    targets = page.get_by_text(TARGET, exact=True) if on_course else None
    target_visible = targets is not None and any(targets.nth(i).is_visible() for i in range(targets.count()))
    # CP success and a task URL are not evidence of an enterprise session.
    session_established = category == "TRAINING_TENANT" and not (login_required or denied) and (
        target_visible or visible_text(page, re.compile(r"^退出登录$")))
    return {"login_required": login_required, "login_page_visible": login_required,
            "login_form_visible": login_form_visible, "access_denied": denied,
            "on_target_course": on_course, "target_pdf_listed": target_visible,
            "enterprise_session_established": session_established,
            "course_content_visible": on_course and target_visible and not (login_required or denied),
            "domain_category": category}


class SsoDiagnostics:
    """Bounded navigation metadata only; never retain URLs, headers, or bodies."""

    STAGES = frozenset({"COURSE_OPEN", "CAS_NAVIGATION", "TRAINING_CALLBACK",
                        "TRAINING_NAVIGATION", "OTHER_NAVIGATION", "OBSERVING",
                        "OBSERVATION_UNAVAILABLE", "SITE_LOGIN_ENTRY_CLICK",
                        "COURSE_RETURN", "COURSE_CONTENT_VISIBLE", "LOGIN_UI_VISIBLE",
                        "ACCESS_DENIED", "TRANSITION_TIMEOUT", "NAVIGATION_ERROR",
                        "LEARNING_CENTER", "LEARNING_PLAN", "PLAN_PAGE_2",
                        "PLAN_DETAILS", "LEARNING_STAGE_1", "SITE_NAVIGATION_UNCONFIRMED"})

    def __init__(self):
        self.events = []
        self.handoff_seen = False
        self.listeners = []

    def record(self, stage, category, status=None, login_visible=None):
        if stage not in self.STAGES:
            return
        if category not in {"CAS", "CREW_PORTAL", "TRAINING_MOBILE", "TRAINING_TENANT", "OTHER"}:
            category = "OTHER"
        event = {"stage": stage, "domain_category": category,
                 "http_status": status if type(status) is int and 100 <= status <= 599 else None,
                 "login_page_visible": login_visible if type(login_visible) is bool else None}
        if self.events and self.events[-1] == event:
            return
        if len(self.events) < 40:
            self.events.append(event)

    def watch(self, page):
        def on_response(response):
            try:
                request = response.request
                if not request.is_navigation_request() or request.frame != page.main_frame:
                    return
                category = domain_category(response.url)
                path = urlsplit(response.url).path.lower()  # Used transiently, not stored.
                if category == "CAS":
                    stage = "CAS_NAVIGATION"
                elif category in {"TRAINING_MOBILE", "TRAINING_TENANT"}:
                    stage = "TRAINING_CALLBACK" if "/sso/" in path else "TRAINING_NAVIGATION"
                else:
                    stage = "OTHER_NAVIGATION"
                self.handoff_seen |= stage in {"CAS_NAVIGATION", "TRAINING_CALLBACK"}
                self.record(stage, category, response.status)
            except Exception:
                pass  # Do not serialize event errors or Playwright objects.
        page.on("response", on_response)
        self.listeners.append((page, on_response))

    def close(self):
        for page, listener in self.listeners:
            try:
                page.remove_listener("response", listener)
            except Exception:
                pass


def wait_for_course_state(page, context, known_pages, diagnostics, *, timeout_ms=20_000):
    """Give automatic CAS/callback redirects time; a transient login UI is not final."""
    observed = None
    active = page
    for poll in range(timeout_ms // 500 + 1):
        candidates = [page] + [p for p in context.pages if p not in known_pages and p != page]
        observations = []
        for candidate in candidates:
            try:
                if candidate.is_closed():
                    continue
                state = course_observation(candidate)
                diagnostics.record("OBSERVING", state["domain_category"], login_visible=state["login_page_visible"])
                observations.append((candidate, state))
                if state["course_content_visible"]:
                    diagnostics.record("COURSE_CONTENT_VISIBLE", state["domain_category"], login_visible=False)
                    return candidate, state
            except Exception:
                # A destroyed execution context during navigation is not failed authentication.
                diagnostics.record("OBSERVATION_UNAVAILABLE", "OTHER")
        if observations:
            active, observed = observations[-1]
        else:
            observed = None
        if poll < timeout_ms // 500:
            active.wait_for_timeout(500)
    if observed:
        stage = ("ACCESS_DENIED" if observed["access_denied"] else
                 "LOGIN_UI_VISIBLE" if observed["login_page_visible"] else "TRANSITION_TIMEOUT")
        diagnostics.record(stage, observed["domain_category"], login_visible=observed["login_page_visible"])
    return active, observed


def visible_site_login_entry(page, *, sso_only=False):
    """Select one real site's login control. Never construct a service/callback URL."""
    if domain_category(page.url) not in {"TRAINING_MOBILE", "TRAINING_TENANT"}:
        return None
    matches = []
    for role in ("link", "button"):
        # A generic "登录" submit button could start another credential/OTP flow.
        controls = page.get_by_role(role, name=LOGIN_ENTRY_NAME if role == "link" and not sso_only else SSO_BUTTON_NAME)
        for index in range(controls.count()):
            control = controls.nth(index)
            if not control.is_visible():
                continue
            if role == "button" and control.get_attribute("type") == "submit":
                continue
            if role == "button" and control.evaluate(
                    "element => element.tagName === 'BUTTON' && element.type === 'submit' && element.form !== null"):
                continue  # A button inside a form defaults to submit without a type attribute.
            if role == "link":
                href = control.get_attribute("href") or ""
                # A regular app link or JS click handler is used as rendered;
                # external authentication providers require separate review.
                if href and href not in {"#", "javascript:;", "javascript:void(0)", "javascript:void(0);"}:
                    resolved = urljoin(page.url, href)
                    if domain_category(resolved) not in {"CAS", "TRAINING_MOBILE", "TRAINING_TENANT"}:
                        continue
                    if "/logout" in urlsplit(resolved).path.lower():
                        continue
            matches.append(control)
    return matches[0] if len(matches) == 1 else None


def follow_learning_plan(page, context, known_pages, diagnostics, state):
    """Bounded fallback through the user's confirmed UI; no inferred URLs."""
    def unique(controls):
        visible = [controls.nth(i) for i in range(controls.count()) if controls.nth(i).is_visible()]
        return visible[0] if len(visible) == 1 else None

    stages = ("LEARNING_CENTER", "LEARNING_PLAN", "PLAN_PAGE_2", "PLAN_DETAILS", "LEARNING_STAGE_1")
    # A direct task may simply have a collapsed first learning stage.
    if state and state["on_target_course"] and unique(page.get_by_text("学习阶段1", exact=True)) is not None:
        stages = ("LEARNING_STAGE_1",)
    for stage in stages:
        if (not state or state["course_content_visible"] or state["login_required"] or
                state["access_denied"] or state["domain_category"] != "TRAINING_TENANT"):
            break
        if stage == "PLAN_PAGE_2":
            if unique(page.get_by_text(PROJECT, exact=True)) is not None:
                continue
            controls = page.locator('[class*="pagination"], [aria-label*="分页"]').get_by_text("2", exact=True)
        elif stage == "PLAN_DETAILS":
            title = unique(page.get_by_text(PROJECT, exact=True))
            if title is None:
                diagnostics.record("SITE_NAVIGATION_UNCONFIRMED", "TRAINING_TENANT")
                break
            # Nearest real container with this title and its own details action.
            controls = title.locator("xpath=ancestor::*[.//*[normalize-space(text())='查看详情']][1]").get_by_text("查看详情", exact=True)
        else:
            label = {"LEARNING_CENTER": "学习中心", "LEARNING_PLAN": "学习计划",
                     "LEARNING_STAGE_1": "学习阶段1"}[stage]
            controls = page.get_by_text(label, exact=True)
        control = unique(controls)
        if control is None or control.evaluate("element => !!element.closest('form')"):
            diagnostics.record("SITE_NAVIGATION_UNCONFIRMED", "TRAINING_TENANT")
            break
        href = control.evaluate("element => element.closest('a')?.getAttribute('href') || ''")
        if href and href not in {"#", "javascript:;", "javascript:void(0)", "javascript:void(0);"}:
            resolved = urljoin(page.url, href)
            if domain_category(resolved) != "TRAINING_TENANT" or "/logout" in urlsplit(resolved).path.lower():
                diagnostics.record("SITE_NAVIGATION_UNCONFIRMED", "TRAINING_TENANT")
                break
        diagnostics.record(stage, "TRAINING_TENANT", login_visible=False)
        control.click(timeout=10_000)
        page, state = wait_for_course_state(page, context, known_pages, diagnostics)
    return page, state


def open_course_through_site(page, context, report):
    diagnostics = SsoDiagnostics()
    report.update(sso_handoff_attempted=False, sso_entry_source="COURSE_NATURAL_FLOW",
                  sso_diagnostics=diagnostics.events)
    known_pages = list(context.pages)
    diagnostics.watch(page)
    context.on("page", diagnostics.watch)
    try:
        diagnostics.record("COURSE_OPEN", "TRAINING_TENANT")
        page.goto(COURSE, wait_until="domcontentloaded", timeout=60_000)
        active, state = wait_for_course_state(page, context, known_pages, diagnostics)
        if state and not (state["course_content_visible"] or state["access_denied"]):
            # A credential form may sit beside the enterprise SSO control.
            # In that case inspect only explicit SSO controls, never generic login.
            entry = visible_site_login_entry(active, sso_only=state["login_form_visible"])
            if entry is not None:
                diagnostics.record("SITE_LOGIN_ENTRY_CLICK", state["domain_category"], login_visible=state["login_page_visible"])
                report.update(sso_handoff_attempted=True, sso_entry_source="VISIBLE_SITE_LOGIN_ENTRY")
                entry.click(timeout=10_000)  # One site login action, never an OTP request.
                active, state = wait_for_course_state(page, context, known_pages, diagnostics)
            elif state["login_required"] and state["domain_category"] in {"TRAINING_MOBILE", "TRAINING_TENANT"}:
                report["sso_entry_status"] = "SSO_ENTRY_NOT_FOUND"
        # A site callback may end at its home page. Return once only after it has
        # settled on a training page without visible login UI or a callback path.
        if state and not (state["course_content_visible"] or state["login_required"] or state["access_denied"]):
            location = urlsplit(active.url)
            callback_pending = "/sso/" in location.path.lower() or "/login" in location.path.lower()
            if state["domain_category"] in {"TRAINING_MOBILE", "TRAINING_TENANT"} and not state["on_target_course"] and not callback_pending:
                diagnostics.record("COURSE_RETURN", "TRAINING_TENANT", login_visible=False)
                page.goto(COURSE, wait_until="domcontentloaded", timeout=60_000)
                active, state = wait_for_course_state(page, context, known_pages, diagnostics)
        if state and not (state["course_content_visible"] or state["login_required"] or state["access_denied"]):
            path = urlsplit(active.url).path.lower()
            if state["domain_category"] == "TRAINING_TENANT" and "/sso/" not in path and "/login" not in path:
                active, state = follow_learning_plan(active, context, known_pages, diagnostics, state)
        return active, state
    except Exception:
        diagnostics.record("NAVIGATION_ERROR", "OTHER")
        raise RuntimeError("SSO_NAVIGATION_ERROR") from None
    finally:
        report["sso_handoff_attempted"] |= diagnostics.handoff_seen
        try:
            context.remove_listener("page", diagnostics.watch)
        except Exception:
            pass
        diagnostics.close()


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
                "pdf_29_pages_confirmed": False, "target_pdf_name_confirmed": False,
                "browser_download_blocked": False}
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
    evidence["target_pdf_name_confirmed"] = True
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
    report.update(status="NOT_VERIFIED", cp_authenticated=False, enterprise_session_established=False,
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
                    phase = "ENTERPRISE_SESSION_NOT_ESTABLISHED"
                    page, seen = open_course_through_site(page, context, report)
                    if seen is None:
                        report.update(status="ENTERPRISE_SESSION_NOT_ESTABLISHED", course_access="NOT_CONFIRMED")
                        return report
                    report.update(seen)
                    if seen["access_denied"]:
                        report.update(status="PERMISSION_DENIED", course_access="DENIED")
                    elif seen["login_required"]:
                        report.update(status="ENTERPRISE_SESSION_NOT_ESTABLISHED", course_access="NOT_CONFIRMED")
                    elif seen["course_content_visible"]:
                        report.update(status="PDF_VIEWER_UNCONFIRMED",
                                      course_access="TARGET_LIST_VISIBLE")
                        phase = "COURSE_VIEWER_INSPECTION_ERROR"
                        report.update(inspect_course_and_viewer(page, context))
                        if report["target_pdf_name_confirmed"] and report["pdf_29_pages_confirmed"]:
                            report["status"] = "PDF_VIEWER_CONFIRMED"
                    else:
                        report.update(status=("TARGET_COURSE_NOT_CONFIRMED" if seen["enterprise_session_established"]
                            else "ENTERPRISE_SESSION_NOT_ESTABLISHED"), course_access="NOT_CONFIRMED")
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
    return 0 if report["status"] in {"READY", "PDF_VIEWER_CONFIRMED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
