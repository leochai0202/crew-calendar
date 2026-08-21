from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from crew_auth_session import (
    ALLOWED_AUTH_ORIGINS,
    AuthBundle,
    AuthBundleError,
    AuthObservation,
    AuthSignals,
    AuthStatus,
    MISSION_URL,
    STATUS_EXIT_CODES,
    auth_bundle_to_dict,
    emit_safe_status,
    filter_session_storage,
    filter_storage_state,
    load_auth_bundle_file,
    navigate_and_probe,
    probe_page,
    restore_auth_bundle_to_existing_context,
    verify_auth_bundle,
)
from imap_otp import (
    IMAP_HOST,
    IMAP_PORT,
    ImapOtpReader,
    OtpConfigurationError,
    OtpError,
    OtpMailboxError,
    OtpParseError,
    OtpTimeoutError,
)


DEFAULT_AUTH_DIR = Path("playwright") / ".auth"
DEFAULT_PROFILE_DIR = DEFAULT_AUTH_DIR / "crew-profile"
DEFAULT_STATE_FILE = DEFAULT_AUTH_DIR / "crew-auth-session.storage-state.json"
DEFAULT_LOCAL_ENV_FILE = Path(__file__).resolve().parent / ".env"
DEFAULT_TIMEOUT_SECONDS = 10 * 60
OTP_TIMEOUT_SECONDS = 45
OTP_POLL_INTERVAL_SECONDS = 1
OTP_MAX_ATTEMPTS = 3
OTP_REQUEST_RECOVERY_TIMEOUT_SECONDS = 70
OTP_CLOCK_SKEW_SECONDS = 5
POST_LOGIN_SESSION_TIMEOUT_SECONDS = 30
POST_LOGIN_SESSION_SETTLE_MS = 2_000
POST_LOGIN_SESSION_POLL_INTERVAL_MS = 500
POST_LOGIN_MISSION_PROBE_DELAY_MS = 2_000
OTP_DIAGNOSTIC_DIR = (
    Path("playwright")
    / ".auth-diagnostics"
    / "otp-login"
)
LOGIN_SWITCH_DIAGNOSTIC_DIR = (
    Path("playwright")
    / ".auth-diagnostics"
    / "login-switch"
)

# These selectors were verified against the current CAS DOM. The legacy
# username/password/image-captcha login in crew_calendar_main.py is preserved.
ACCOUNT_LOGIN_TOGGLE_SELECTOR = (
    ".login-badge .badge-icon"
)
PASSWORD_LOGIN_TAB_SELECTOR = "#div1"
DYNAMIC_LOGIN_TAB_SELECTOR = "#div2"
DYNAMIC_LOGIN_FORM_SELECTOR = "#logincontentFm2"
PHONE_OR_EMAIL_SELECTOR = "#phone"
DYNAMIC_PASSWORD_SELECTOR = "#dynamic"
REQUEST_DYNAMIC_PASSWORD_SELECTOR = "#btnGetDynamic"
SUBMIT_DYNAMIC_LOGIN_SELECTOR = "#loginBtn2"
SHUMEI_SLIDER_SELECTOR = "#shu-mei-outer"
QR_LOGIN_HEADING = "手机扫码，安全登录"
IMAP_EMAIL_ENV = "IMAP_EMAIL"
IMAP_AUTH_CODE_ENV = "IMAP_AUTH_CODE"
IMAP_HOST_ENV = "IMAP_HOST"
IMAP_PORT_ENV = "IMAP_PORT"
LOGIN_PHONE_ENV = "CREW_LOGIN_PHONE"
CLOUD_LOGIN_PHONE_ENV = "CREW_PHONE"
LOGIN_STATE_TIMEOUT_SECONDS = 15
LOGIN_STATE_POLL_INTERVAL_MS = 200
LOGIN_STATE_REQUIRED_POLLS = 2
LOGIN_STATE_ACCOUNT_GRACE_SECONDS = 1.5

LOGIN_STAGE_NAMES = frozenset(
    {
        "LOGIN_FLOW_STARTED",
        "LOGIN_STATE_WAIT_STARTED",
        "LOGIN_STATE_CONFIRMED",
        "QR_HEADING_FIRST_SEEN_MS",
        "LOGIN_PAGE_SWITCHED",
        "QR_LOGIN_PAGE_DETECTED",
        "TOGGLE_CANDIDATES_INSPECTED",
        "TOGGLE_CLICK_LOGIN_BADGE",
        "TOGGLE_CLICK_BADGE_ICON",
        "TOGGLE_DOM_CLICK_BADGE_ICON",
        "ACCOUNT_LOGIN_TOGGLE_CLICKED",
        "ACCOUNT_LOGIN_PANEL_VISIBLE",
        "PASSWORD_TAB_VISIBLE",
        "DYNAMIC_TAB_CLICKED",
        "DYNAMIC_TAB_OPENED",
        "PHONE_FILLED",
        "OTP_ATTEMPT_STARTED",
        "IMAP_BASELINE_RECORDED",
        "OTP_REQUEST_CLICKED",
        "SLIDER_PRESENT",
        "SLIDER_ABSENT",
        "OTP_ATTEMPT_TIMEOUT",
        "OTP_RETRY_WAIT_STARTED",
        "OTP_RETRY_READY",
        "OTP_MAIL_RECEIVED",
        "OTP_FIELD_FILLED",
        "LOGIN_BUTTON_CLICKED",
        "SSO_HANDOFF_REACHED",
        "SSO_HANDOFF_TIMEOUT",
        "SSO_SESSION_PROBE",
        "SSO_BUSINESS_COOKIE_READY",
        "MISSION_PAGE_REQUESTED",
        "MISSION_SINGLE_NAVIGATION_RESULT",
        "MISSION_PAGE_AUTHENTICATED",
        "FINAL_PAGE_PROBED",
    }
)
LoginStageReporter = Callable[[str, dict[str, Any]], None]


class AdditionalVerificationRequiredError(OtpError):
    pass


class LoginToggleError(OtpError):
    def __init__(
        self,
        category: str,
        diagnostic: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(category)
        self.category = category
        self.diagnostic = diagnostic or {}


class LoginPageStateError(OtpError):
    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


def _safe_page_location(page: Any) -> tuple[str, str]:
    try:
        parsed = urlsplit(str(getattr(page, "url", "") or ""))
        return parsed.netloc.lower(), parsed.path or "/"
    except Exception:
        return "", ""


def _safe_response_status(response: Any) -> int:
    try:
        status = int(response.status)
    except (AttributeError, TypeError, ValueError):
        return 0
    return status if 0 <= status <= 599 else 0


def _task_area_visible(observation: AuthObservation) -> bool:
    return bool(
        observation.signals.mission_heading
        or observation.signals.task_container
    )


def _authenticated_observation(
    observation: AuthObservation,
) -> AuthObservation:
    return AuthObservation(
        AuthStatus.AUTHENTICATED,
        observation.signals,
    )


def _safe_main_frame_location(page: Any) -> tuple[str, str]:
    try:
        main_frame = page.main_frame
        parsed = urlsplit(str(getattr(main_frame, "url", "") or ""))
        return parsed.netloc.lower(), parsed.path or "/"
    except Exception:
        return "", ""


def _cp_cookie_state(page: Any) -> tuple[dict[str, str], list[str]]:
    """Return comparable CP cookie state while keeping values in memory only."""
    try:
        cookies = page.context.cookies([MISSION_URL])
    except Exception:
        return {}, []

    state: dict[str, str] = {}
    names: set[str] = set()
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        name = str(cookie.get("name", "")).strip()
        domain = str(cookie.get("domain", "")).lstrip(".").lower()
        path = str(cookie.get("path", "/") or "/")
        if not name or not (
            domain == "9cair.com" or domain.endswith(".9cair.com")
        ):
            continue
        key = f"{domain}|{path}|{name}"
        state[key] = str(cookie.get("value", ""))
        names.add(name)
    return state, sorted(names)


def _changed_cp_cookie_names(
    baseline: dict[str, str],
    current: dict[str, str],
) -> list[str]:
    changed: set[str] = set()
    for key, value in current.items():
        if baseline.get(key) == value:
            continue
        try:
            name = key.rsplit("|", 1)[1]
        except (IndexError, AttributeError):
            continue
        if name:
            changed.add(name)
    return sorted(changed)


def _recover_post_login_mission_page(
    page: Any,
    *,
    stage_reporter: LoginStageReporter | None,
    baseline_cp_cookies: dict[str, str] | None = None,
    timeout_seconds: int = POST_LOGIN_SESSION_TIMEOUT_SECONDS,
) -> AuthObservation:
    if timeout_seconds <= 0:
        raise ValueError("SSO业务会话等待时间必须大于0")

    baseline = dict(baseline_cp_cookies or {})
    poll_count = max(
        1,
        int(
            timeout_seconds
            * 1_000
            / POST_LOGIN_SESSION_POLL_INTERVAL_MS
        ),
    )
    last_signature: tuple[Any, ...] | None = None
    observation = probe_page(page)
    domain, _ = _safe_page_location(page)
    main_frame_domain, _ = _safe_main_frame_location(page)
    if domain == "cp.9cair.com" and _task_area_visible(observation):
        return _authenticated_observation(observation)
    if (
        domain == "cas.9cair.com"
        or main_frame_domain == "cas.9cair.com"
    ):
        return AuthObservation(
            AuthStatus.LOGIN_REQUIRED,
            observation.signals,
        )
    page.wait_for_timeout(POST_LOGIN_SESSION_SETTLE_MS)

    for _ in range(poll_count):
        observation = probe_page(page)
        domain, path = _safe_page_location(page)
        main_frame_domain, main_frame_path = _safe_main_frame_location(page)
        cookie_state, cookie_names = _cp_cookie_state(page)
        business_cookie_names = _changed_cp_cookie_names(
            baseline,
            cookie_state,
        )
        task_area_visible = _task_area_visible(observation)
        signature = (
            domain,
            path,
            main_frame_domain,
            main_frame_path,
            tuple(cookie_names),
            tuple(business_cookie_names),
            task_area_visible,
        )
        if signature != last_signature:
            _report_login_stage(
                stage_reporter,
                "SSO_SESSION_PROBE",
                domain=domain,
                path=path,
                main_frame_domain=main_frame_domain,
                main_frame_path=main_frame_path,
                cp_cookie_names=cookie_names,
                business_cookie_names=business_cookie_names,
                task_area_visible=task_area_visible,
            )
            last_signature = signature

        if domain == "cp.9cair.com" and task_area_visible:
            return _authenticated_observation(observation)
        if (
            domain == "cas.9cair.com"
            or main_frame_domain == "cas.9cair.com"
        ):
            return AuthObservation(
                AuthStatus.LOGIN_REQUIRED,
                observation.signals,
            )

        if domain == "cp.9cair.com" and business_cookie_names:
            _report_login_stage(
                stage_reporter,
                "SSO_BUSINESS_COOKIE_READY",
                cookie_names=business_cookie_names,
            )
            _report_login_stage(stage_reporter, "MISSION_PAGE_REQUESTED")
            response_status = 0
            navigation_error = ""
            try:
                response = page.goto(
                    MISSION_URL,
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )
                response_status = _safe_response_status(response)
            except Exception as exc:
                navigation_error = str(exc).lower()

            page.wait_for_timeout(POST_LOGIN_MISSION_PROBE_DELAY_MS)
            observation = probe_page(page)
            domain, path = _safe_page_location(page)
            main_frame_domain, main_frame_path = (
                _safe_main_frame_location(page)
            )
            task_area_visible = _task_area_visible(observation)
            _report_login_stage(
                stage_reporter,
                "MISSION_SINGLE_NAVIGATION_RESULT",
                domain=domain,
                path=path,
                main_frame_domain=main_frame_domain,
                main_frame_path=main_frame_path,
                http_status=response_status,
                task_area_visible=task_area_visible,
            )
            if domain == "cp.9cair.com" and task_area_visible:
                return _authenticated_observation(observation)
            if (
                domain == "cas.9cair.com"
                or main_frame_domain == "cas.9cair.com"
            ):
                return AuthObservation(
                    AuthStatus.LOGIN_REQUIRED,
                    AuthSignals(login_url_hint=True),
                )
            if response_status >= 500 or any(
                marker in navigation_error
                for marker in (
                    "net::err_",
                    "connection reset",
                    "name_not_resolved",
                )
            ):
                return AuthObservation(
                    AuthStatus.NETWORK_OR_SITE_ERROR,
                    AuthSignals(network_or_site_error=True),
                )
            if observation.status == AuthStatus.LOGIN_REQUIRED:
                return AuthObservation(
                    AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
                    observation.signals,
                )
            return observation

        page.wait_for_timeout(POST_LOGIN_SESSION_POLL_INTERVAL_MS)

    if observation.status == AuthStatus.LOGIN_REQUIRED:
        return AuthObservation(
            AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
            observation.signals,
        )
    return observation


def _report_login_stage(
    reporter: LoginStageReporter | None,
    stage: str,
    **details: Any,
) -> None:
    if reporter is not None:
        reporter(stage, details)


def _locator_has_visible_element(locator: Any) -> bool:
    try:
        return any(
            locator.nth(index).is_visible(timeout=500)
            for index in range(min(locator.count(), 5))
        )
    except Exception:
        return False


def collect_safe_login_page_snapshot(page: Any) -> dict[str, Any]:
    try:
        from urllib.parse import urlsplit

        parsed = urlsplit(str(page.url))
        domain = parsed.netloc
        path = parsed.path or "/"
    except Exception:
        domain = ""
        path = ""

    try:
        title = " ".join(str(page.title()).split())[:200]
    except Exception:
        title = ""

    def visible(selector: str) -> bool:
        try:
            return _locator_has_visible_element(page.locator(selector))
        except Exception:
            return False

    try:
        qr_page = _locator_has_visible_element(
            page.get_by_text(QR_LOGIN_HEADING, exact=True)
        )
    except Exception:
        qr_page = False

    slider = False
    for target in list(getattr(page, "frames", ())) or [page]:
        try:
            if _locator_has_visible_element(
                target.locator(SHUMEI_SLIDER_SELECTOR)
            ):
                slider = True
                break
        except Exception:
            continue

    return {
        "domain": domain,
        "path": path,
        "title": title,
        "visible_elements": {
            "qr_login_page": qr_page,
            "password_login_tab": visible(PASSWORD_LOGIN_TAB_SELECTOR),
            "dynamic_login_tab": visible(DYNAMIC_LOGIN_TAB_SELECTOR),
            "phone_field": visible(PHONE_OR_EMAIL_SELECTOR),
            "otp_request_button": visible(
                REQUEST_DYNAMIC_PASSWORD_SELECTOR
            ),
            "otp_field": visible(DYNAMIC_PASSWORD_SELECTOR),
            "slider": slider,
            "mission_area": visible("text=我的任务")
            or visible(
                "[class*='mission' i], [class*='task-list' i], "
                "[data-testid*='task' i]"
            ),
        },
    }


def _decode_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        return decoded if isinstance(decoded, str) else ""
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def load_local_imap_configuration(
    env_file: Path = DEFAULT_LOCAL_ENV_FILE,
) -> bool:
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return False
    except OSError:
        return False

    loaded: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if key in {
            IMAP_HOST_ENV,
            IMAP_PORT_ENV,
            IMAP_EMAIL_ENV,
            IMAP_AUTH_CODE_ENV,
            LOGIN_PHONE_ENV,
        }:
            loaded[key] = _decode_env_value(raw_value)

    for key, value in loaded.items():
        if key in {
            IMAP_HOST_ENV,
            IMAP_PORT_ENV,
            IMAP_EMAIL_ENV,
            IMAP_AUTH_CODE_ENV,
            LOGIN_PHONE_ENV,
        }:
            value = value.strip()
        os.environ[key] = value
    return bool(
        os.environ.get(IMAP_EMAIL_ENV, "").strip()
        and os.environ.get(IMAP_AUTH_CODE_ENV, "")
    )


def save_local_imap_configuration(
    email_address: str,
    auth_code: str,
    env_file: Path = DEFAULT_LOCAL_ENV_FILE,
) -> None:
    email_address = email_address.strip()
    auth_code = auth_code.strip()
    if not email_address or not auth_code:
        raise OtpConfigurationError("邮箱或授权码为空")

    try:
        existing_lines = env_file.read_text(
            encoding="utf-8",
        ).splitlines()
    except FileNotFoundError:
        existing_lines = []
    except OSError as exc:
        raise OtpConfigurationError("本地.env无法读取") from exc

    retained_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in {IMAP_EMAIL_ENV, IMAP_AUTH_CODE_ENV}:
                continue
        retained_lines.append(line)

    retained_lines.extend(
        (
            f"{IMAP_EMAIL_ENV}="
            f"{json.dumps(email_address, ensure_ascii=False)}",
            f"{IMAP_AUTH_CODE_ENV}="
            f"{json.dumps(auth_code, ensure_ascii=False)}",
        )
    )
    content = "\n".join(retained_lines).rstrip("\n") + "\n"

    env_file.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f"{env_file.name}.",
        suffix=".tmp",
        dir=env_file.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            temporary_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary_path, env_file)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def save_local_login_phone(
    phone_number: str,
    env_file: Path = DEFAULT_LOCAL_ENV_FILE,
) -> None:
    phone_number = phone_number.strip()
    if not phone_number:
        raise OtpConfigurationError("登录手机号为空")

    try:
        existing_lines = env_file.read_text(
            encoding="utf-8",
        ).splitlines()
    except FileNotFoundError:
        existing_lines = []
    except OSError as exc:
        raise OtpConfigurationError("本地.env无法读取") from exc

    retained_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key == LOGIN_PHONE_ENV:
                continue
        retained_lines.append(line)
    retained_lines.append(
        f"{LOGIN_PHONE_ENV}="
        f"{json.dumps(phone_number, ensure_ascii=False)}"
    )
    content = "\n".join(retained_lines).rstrip("\n") + "\n"

    env_file.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f"{env_file.name}.",
        suffix=".tmp",
        dir=env_file.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            temporary_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary_path, env_file)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def prompt_for_imap_configuration(
    initial_email: str = "",
) -> tuple[str, str]:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError as exc:
        raise OtpConfigurationError("无法显示本机安全认证窗口") from exc

    result: dict[str, str] = {}
    root = tk.Tk()
    root.title("Crew Calendar 安全认证")
    root.geometry("520x235")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    tk.Label(
        root,
        text="首次使用请保存163邮箱配置；授权码将隐藏显示。",
    ).place(x=20, y=20, width=475, height=30)
    tk.Label(root, text="163邮箱：", anchor="w").place(
        x=20,
        y=70,
        width=105,
        height=28,
    )
    email_entry = tk.Entry(root)
    email_entry.place(x=125, y=70, width=360, height=28)
    email_entry.insert(0, initial_email)

    tk.Label(root, text="客户端授权码：", anchor="w").place(
        x=20,
        y=115,
        width=105,
        height=28,
    )
    auth_code_entry = tk.Entry(root, show="●")
    auth_code_entry.place(x=125, y=115, width=360, height=28)

    def submit() -> None:
        email_address = email_entry.get().strip()
        auth_code = auth_code_entry.get().strip()
        if not email_address or not auth_code:
            messagebox.showinfo(
                "提示",
                "邮箱和授权码均不能为空。",
                parent=root,
            )
            return
        result[IMAP_EMAIL_ENV] = email_address
        result[IMAP_AUTH_CODE_ENV] = auth_code
        email_entry.delete(0, tk.END)
        auth_code_entry.delete(0, tk.END)
        root.destroy()

    tk.Button(
        root,
        text="保存并开始真实登录测试",
        command=submit,
    ).place(x=275, y=165, width=210, height=36)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    email_entry.focus_set()
    root.mainloop()

    email_address = result.get(IMAP_EMAIL_ENV, "")
    auth_code = result.get(IMAP_AUTH_CODE_ENV, "")
    if not email_address or not auth_code:
        raise OtpConfigurationError("本机认证配置未完成")
    return email_address, auth_code


def ensure_local_imap_configuration(
    env_file: Path = DEFAULT_LOCAL_ENV_FILE,
) -> None:
    if load_local_imap_configuration(env_file):
        return

    initial_email = os.environ.get(IMAP_EMAIL_ENV, "").strip()
    email_address, auth_code = prompt_for_imap_configuration(initial_email)
    save_local_imap_configuration(
        email_address,
        auth_code,
        env_file,
    )
    os.environ[IMAP_EMAIL_ENV] = email_address
    os.environ[IMAP_AUTH_CODE_ENV] = auth_code


def prompt_for_login_phone(initial_phone: str = "") -> str:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError as exc:
        raise OtpConfigurationError("无法显示本机手机号配置窗口") from exc

    result: dict[str, str] = {}
    root = tk.Tk()
    root.title("Crew Calendar 登录手机号")
    root.geometry("500x180")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    tk.Label(
        root,
        text="请输入动态密码登录使用的手机号；保存后将自动填写。",
    ).place(x=20, y=20, width=455, height=30)
    tk.Label(root, text="手机号：", anchor="w").place(
        x=20,
        y=70,
        width=90,
        height=28,
    )
    phone_entry = tk.Entry(root)
    phone_entry.place(x=110, y=70, width=365, height=28)
    phone_entry.insert(0, initial_phone)

    def submit() -> None:
        phone_number = phone_entry.get().strip()
        if not phone_number or not phone_number.isdigit():
            messagebox.showinfo(
                "提示",
                "请输入有效的纯数字手机号。",
                parent=root,
            )
            return
        result[LOGIN_PHONE_ENV] = phone_number
        phone_entry.delete(0, tk.END)
        root.destroy()

    tk.Button(
        root,
        text="保存并继续",
        command=submit,
    ).place(x=295, y=115, width=180, height=36)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    phone_entry.focus_set()
    root.mainloop()

    phone_number = result.get(LOGIN_PHONE_ENV, "")
    if not phone_number:
        raise OtpConfigurationError("登录手机号配置未完成")
    return phone_number


def ensure_local_login_phone(
    env_file: Path = DEFAULT_LOCAL_ENV_FILE,
) -> str:
    load_local_imap_configuration(env_file)
    configured = os.environ.get(LOGIN_PHONE_ENV, "").strip()
    if configured:
        return configured

    phone_number = prompt_for_login_phone()
    save_local_login_phone(phone_number, env_file)
    os.environ[LOGIN_PHONE_ENV] = phone_number
    return phone_number


def _safe_imap_error(exc: BaseException) -> tuple[str, str]:
    cause = exc.__cause__
    detail = str(cause if cause is not None else exc)
    for sensitive in (
        os.environ.get(IMAP_EMAIL_ENV, ""),
        os.environ.get(IMAP_AUTH_CODE_ENV, ""),
    ):
        if sensitive:
            detail = detail.replace(sensitive, "<redacted>")
    return type(cause if cause is not None else exc).__name__, detail


def _connect_imap_once() -> None:
    with ImapOtpReader.from_environment():
        return


def validate_local_imap_configuration(
    *,
    allow_credential_update: bool,
) -> bool:
    try:
        ensure_local_imap_configuration()
    except OtpConfigurationError:
        print("IMAP_CONFIG_PRESENT=NO", flush=True)
        return False

    print("IMAP_CONFIG_PRESENT=YES", flush=True)
    imap_host = os.environ.get(IMAP_HOST_ENV, IMAP_HOST).strip()
    imap_port = os.environ.get(IMAP_PORT_ENV, str(IMAP_PORT)).strip()
    print(f"IMAP_TARGET={imap_host}:{imap_port} SSL", flush=True)
    try:
        _connect_imap_once()
    except OtpMailboxError as exc:
        error_type, detail = _safe_imap_error(exc)
        print(f"IMAP_ERROR_TYPE={error_type}", flush=True)
        print(f"IMAP_SERVER_RESPONSE={detail}", flush=True)
        credential_error = (
            "LOGIN" in detail.upper()
            and "PASSWORD" in detail.upper()
        )
        if not allow_credential_update or not credential_error:
            return False

        initial_email = os.environ.get(IMAP_EMAIL_ENV, "").strip()
        try:
            email_address, auth_code = prompt_for_imap_configuration(
                initial_email,
            )
            save_local_imap_configuration(
                email_address,
                auth_code,
            )
            os.environ[IMAP_EMAIL_ENV] = email_address
            os.environ[IMAP_AUTH_CODE_ENV] = auth_code
            _connect_imap_once()
        except OtpError as retry_exc:
            retry_type, retry_detail = _safe_imap_error(retry_exc)
            print(f"IMAP_ERROR_TYPE={retry_type}", flush=True)
            print(f"IMAP_SERVER_RESPONSE={retry_detail}", flush=True)
            return False
    except OtpError as exc:
        error_type, detail = _safe_imap_error(exc)
        print(f"IMAP_ERROR_TYPE={error_type}", flush=True)
        print(f"IMAP_SERVER_RESPONSE={detail}", flush=True)
        return False

    print("IMAP_CONNECT=SUCCESS", flush=True)
    return True


def capture_session_storage(context: Any) -> dict[str, dict[str, str]]:
    allowed = set(ALLOWED_AUTH_ORIGINS)
    captured: dict[str, dict[str, str]] = {}
    for page in list(context.pages):
        for frame in list(page.frames):
            try:
                origin = frame.evaluate("() => window.location.origin")
            except Exception:
                continue
            if origin not in allowed:
                continue
            try:
                entries = frame.evaluate(
                    "() => Object.fromEntries("
                    "Object.entries(window.sessionStorage))"
                )
            except Exception:
                entries = {}
            if not isinstance(entries, dict):
                continue
            target = captured.setdefault(origin, {})
            for key, value in entries.items():
                target[str(key)] = str(value)
    return filter_session_storage(captured)


def capture_storage_state(context: Any) -> dict[str, Any]:
    try:
        supports_indexed_db = (
            "indexed_db"
            in inspect.signature(context.storage_state).parameters
        )
    except (TypeError, ValueError):
        supports_indexed_db = False
    if supports_indexed_db:
        state = context.storage_state(indexed_db=True)
    else:
        state = context.storage_state()
    return filter_storage_state(state)


def observe_context(context: Any) -> tuple[AuthObservation, Any | None]:
    observations: list[tuple[AuthObservation, Any]] = []
    for page in list(context.pages):
        try:
            observations.append((probe_page(page), page))
        except Exception:
            continue
    if not observations:
        signals = AuthSignals(network_or_site_error=True)
        return AuthObservation(AuthStatus.NETWORK_OR_SITE_ERROR, signals), None

    priority = (
        AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED,
        AuthStatus.AUTHENTICATED,
        AuthStatus.LOGIN_REQUIRED,
        AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
        AuthStatus.NETWORK_OR_SITE_ERROR,
    )
    for wanted in priority:
        for observation, page in observations:
            if observation.status == wanted:
                return observation, page
    return observations[0]


def wait_for_manual_authentication(
    context: Any,
    timeout_seconds: int,
) -> tuple[AuthObservation, Any | None]:
    deadline = time.monotonic() + timeout_seconds
    last_status: AuthStatus | None = None
    while time.monotonic() < deadline:
        observation, page = observe_context(context)
        if observation.status != last_status:
            emit_safe_status(observation.status)
            last_status = observation.status
        if observation.status == AuthStatus.AUTHENTICATED:
            return observation, page
        time.sleep(1)
    return (
        AuthObservation(
            AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
            AuthSignals(),
        ),
        None,
    )


def _unique_locator(page: Any, selector: str, description: str) -> Any:
    locator = page.locator(selector)
    count = locator.count()
    if count != 1:
        raise OtpError(f"登录页{description}数量异常")
    return locator


def _element_style(locator: Any) -> dict[str, str]:
    try:
        style = locator.evaluate(
            "(element) => {"
            "const value = window.getComputedStyle(element);"
            "return {"
            "display: value.display,"
            "visibility: value.visibility,"
            "pointer_events: value.pointerEvents"
            "};"
            "}"
        )
    except Exception:
        return {
            "display": "",
            "visibility": "",
            "pointer_events": "",
        }
    return {
        "display": str(style.get("display", "")),
        "visibility": str(style.get("visibility", "")),
        "pointer_events": str(style.get("pointer_events", "")),
    }


def _positive_bounding_box(locator: Any) -> dict[str, float] | None:
    try:
        box = locator.bounding_box()
    except Exception:
        return None
    if not isinstance(box, dict):
        return None
    try:
        normalized = {
            key: float(box[key])
            for key in ("x", "y", "width", "height")
        }
    except (KeyError, TypeError, ValueError):
        return None
    if normalized["width"] <= 0 or normalized["height"] <= 0:
        return None
    return normalized


def _nearest_login_badge(icon: Any) -> Any:
    return icon.locator(
        "xpath=ancestor::*["
        "contains(concat(' ', normalize-space(@class), ' '),"
        " ' login-badge ')"
        "][1]"
    )


def _is_top_right_toggle(
    icon_box: dict[str, float],
    badge_box: dict[str, float],
    heading_box: dict[str, float] | None,
) -> bool:
    icon_center_x = icon_box["x"] + icon_box["width"] / 2
    icon_center_y = icon_box["y"] + icon_box["height"] / 2
    inside_badge = (
        badge_box["x"] <= icon_center_x
        <= badge_box["x"] + badge_box["width"]
        and badge_box["y"] <= icon_center_y
        <= badge_box["y"] + badge_box["height"]
    )
    if not inside_badge or heading_box is None:
        return False
    heading_center_x = heading_box["x"] + heading_box["width"] / 2
    heading_bottom = heading_box["y"] + heading_box["height"] * 2
    return (
        icon_center_x >= heading_center_x
        and icon_center_y <= heading_bottom
    )


def _detect_login_page_state(
    page: Any,
) -> tuple[str | None, Any | None]:
    try:
        qr_heading = page.get_by_text(
            QR_LOGIN_HEADING,
            exact=True,
        )
        if _locator_has_visible_element(qr_heading):
            return "QR", qr_heading
    except Exception:
        pass

    try:
        password_tab = page.locator(PASSWORD_LOGIN_TAB_SELECTOR)
        dynamic_tab = page.locator(DYNAMIC_LOGIN_TAB_SELECTOR)
        if (
            _locator_has_visible_element(password_tab)
            and _locator_has_visible_element(dynamic_tab)
        ):
            return "ACCOUNT", None
    except Exception:
        pass

    try:
        form = page.locator(DYNAMIC_LOGIN_FORM_SELECTOR)
        phone = page.locator(PHONE_OR_EMAIL_SELECTOR)
        dynamic_password = page.locator(DYNAMIC_PASSWORD_SELECTOR)
        if (
            _locator_has_visible_element(form)
            and _locator_has_visible_element(phone)
            and _locator_has_visible_element(dynamic_password)
        ):
            return "DYNAMIC", None
    except Exception:
        pass
    return None, None


def _wait_for_stable_login_page_state(
    page: Any,
    *,
    stage_reporter: LoginStageReporter | None,
    timeout_seconds: float = LOGIN_STATE_TIMEOUT_SECONDS,
    poll_interval_ms: int = LOGIN_STATE_POLL_INTERVAL_MS,
) -> tuple[str, Any | None]:
    try:
        page.wait_for_load_state("load", timeout=5_000)
    except Exception:
        # The caller may already be on a fully loaded page, or a lightweight
        # test double may not implement load-state waiting.
        pass

    started = time.monotonic()
    deadline = started + timeout_seconds
    last_state: str | None = None
    consecutive_polls = 0
    qr_first_seen_reported = False
    account_first_seen_at: float | None = None
    _report_login_stage(stage_reporter, "LOGIN_STATE_WAIT_STARTED")

    while time.monotonic() <= deadline:
        state, qr_heading = _detect_login_page_state(page)
        if state == "QR" and not qr_first_seen_reported:
            elapsed_ms = max(
                0,
                int(round((time.monotonic() - started) * 1000)),
            )
            _report_login_stage(
                stage_reporter,
                "QR_HEADING_FIRST_SEEN_MS",
                elapsed_ms=elapsed_ms,
            )
            qr_first_seen_reported = True

        if state is not None and state == last_state:
            consecutive_polls += 1
        elif state is not None:
            last_state = state
            consecutive_polls = 1
        else:
            last_state = None
            consecutive_polls = 0

        if state == "ACCOUNT":
            if account_first_seen_at is None:
                account_first_seen_at = time.monotonic()
        else:
            account_first_seen_at = None

        account_state_is_settled = (
            state != "ACCOUNT"
            or (
                account_first_seen_at is not None
                and time.monotonic() - account_first_seen_at
                >= LOGIN_STATE_ACCOUNT_GRACE_SECONDS
            )
        )
        if (
            state is not None
            and consecutive_polls >= LOGIN_STATE_REQUIRED_POLLS
            and account_state_is_settled
        ):
            _report_login_stage(
                stage_reporter,
                "LOGIN_STATE_CONFIRMED",
                state=state,
            )
            return state, qr_heading

        try:
            page.wait_for_timeout(poll_interval_ms)
        except Exception:
            time.sleep(poll_interval_ms / 1000)

    raise LoginPageStateError("LOGIN_PAGE_STATE_TIMEOUT")


def _inspect_toggle_candidates(
    page: Any,
    qr_heading: Any,
) -> tuple[Any, Any, dict[str, Any]]:
    badges = page.locator(".login-badge")
    icons = page.locator(".badge-icon")
    heading_box = _positive_bounding_box(qr_heading)
    candidates: list[dict[str, Any]] = []
    eligible: list[tuple[Any, Any]] = []

    for index in range(icons.count()):
        icon = icons.nth(index)
        visible = False
        try:
            visible = icon.is_visible()
        except Exception:
            pass
        icon_box = _positive_bounding_box(icon)
        style = _element_style(icon)
        badge = _nearest_login_badge(icon)
        badge_exists = badge.count() > 0
        badge_visible = False
        badge_box = None
        if badge_exists:
            try:
                badge_visible = badge.is_visible()
            except Exception:
                pass
            badge_box = _positive_bounding_box(badge)
        style_allows_click = (
            style["display"] != "none"
            and style["visibility"] not in {"hidden", "collapse"}
            and style["pointer_events"] != "none"
        )
        top_right = bool(
            visible
            and icon_box
            and badge_visible
            and badge_box
            and style_allows_click
            and _is_top_right_toggle(
                icon_box,
                badge_box,
                heading_box,
            )
        )
        candidates.append(
            {
                "index": index,
                "visible": visible,
                "bounding_box_exists": icon_box is not None,
                "display": style["display"],
                "visibility": style["visibility"],
                "pointer_events": style["pointer_events"],
                "inside_login_badge": badge_exists,
                "top_right_region": top_right,
            }
        )
        if top_right:
            eligible.append((icon, badge))

    diagnostic = {
        "login_badge_count": badges.count(),
        "badge_icon_count": icons.count(),
        "visible_badge_icon_count": sum(
            1 for candidate in candidates if candidate["visible"]
        ),
        "eligible_toggle_count": len(eligible),
        "candidates": candidates,
    }
    if not eligible:
        raise LoginToggleError("TOGGLE_NOT_FOUND", diagnostic)
    if len(eligible) > 1:
        raise LoginToggleError(
            "MULTIPLE_VISIBLE_TOGGLES",
            diagnostic,
        )
    icon, badge = eligible[0]
    return icon, badge, diagnostic


def _account_tabs_visible(password_tab: Any, dynamic_tab: Any) -> bool:
    return (
        _locator_has_visible_element(password_tab)
        and _locator_has_visible_element(dynamic_tab)
    )


def _wait_for_account_tabs(
    page: Any,
    password_tab: Any,
    dynamic_tab: Any,
    timeout_seconds: float = 2,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while True:
        if _account_tabs_visible(password_tab, dynamic_tab):
            return True
        if time.monotonic() >= deadline:
            return False
        try:
            page.wait_for_timeout(100)
        except Exception:
            time.sleep(0.1)


def _ordinary_toggle_click(target: Any) -> None:
    target.scroll_into_view_if_needed(timeout=5_000)
    target.wait_for(state="visible", timeout=5_000)
    target.click(trial=True, timeout=5_000)
    target.click(timeout=5_000)


def _open_account_login_panel(
    page: Any,
    qr_heading: Any,
    *,
    stage_reporter: LoginStageReporter | None,
) -> tuple[Any, Any]:
    try:
        icon, badge, diagnostic = _inspect_toggle_candidates(
            page,
            qr_heading,
        )
    except LoginToggleError as exc:
        _report_login_stage(
            stage_reporter,
            "TOGGLE_CANDIDATES_INSPECTED",
            diagnostic=exc.diagnostic,
        )
        raise exc

    _report_login_stage(
        stage_reporter,
        "TOGGLE_CANDIDATES_INSPECTED",
        diagnostic=diagnostic,
    )
    password_tab = page.locator(PASSWORD_LOGIN_TAB_SELECTOR)
    dynamic_tab = page.locator(DYNAMIC_LOGIN_TAB_SELECTOR)
    click_succeeded = False
    click_intercepted = False

    for target, stage in (
        # The CAS page binds its switch handler to `.login-badge > div`,
        # not to the outer `.login-badge` container.
        (icon, "TOGGLE_CLICK_BADGE_ICON"),
        (badge, "TOGGLE_CLICK_LOGIN_BADGE"),
    ):
        try:
            _ordinary_toggle_click(target)
            click_succeeded = True
            _report_login_stage(stage_reporter, stage)
        except Exception:
            click_intercepted = True
            continue
        if _wait_for_account_tabs(page, password_tab, dynamic_tab):
            _report_login_stage(
                stage_reporter,
                "ACCOUNT_LOGIN_TOGGLE_CLICKED",
            )
            return password_tab, dynamic_tab

    try:
        icon.evaluate("(element) => element.click()")
        click_succeeded = True
        _report_login_stage(
            stage_reporter,
            "TOGGLE_DOM_CLICK_BADGE_ICON",
        )
    except Exception:
        click_intercepted = True
    if _wait_for_account_tabs(page, password_tab, dynamic_tab):
        _report_login_stage(
            stage_reporter,
            "ACCOUNT_LOGIN_TOGGLE_CLICKED",
        )
        return password_tab, dynamic_tab
    if not click_succeeded and click_intercepted:
        raise LoginToggleError("TOGGLE_CLICK_INTERCEPTED")
    raise LoginToggleError("ACCOUNT_PANEL_NOT_OPENED")


def _save_login_switch_diagnostics(page: Any, reason: str) -> None:
    try:
        LOGIN_SWITCH_DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        base = LOGIN_SWITCH_DIAGNOSTIC_DIR / f"login_switch_{timestamp}"
        (base.with_suffix(".html")).write_text(
            page.content(),
            encoding="utf-8",
        )
        (base.with_suffix(".txt")).write_text(
            reason.strip() + "\n",
            encoding="utf-8",
        )
        page.screenshot(
            path=str(base.with_suffix(".png")),
            full_page=True,
        )
        print(
            "登录页切换失败，已在本地认证诊断目录保存DOM和截图。",
            flush=True,
        )
    except Exception:
        print("登录页切换失败，诊断信息保存失败。", flush=True)


def _switch_to_dynamic_password_login(
    page: Any,
    *,
    save_diagnostics: bool = True,
    stage_reporter: LoginStageReporter | None = None,
) -> None:
    try:
        state, qr_heading = _wait_for_stable_login_page_state(
            page,
            stage_reporter=stage_reporter,
        )
        form = page.locator(DYNAMIC_LOGIN_FORM_SELECTOR)
        if state == "QR":
            _report_login_stage(
                stage_reporter,
                "QR_LOGIN_PAGE_DETECTED",
            )
            password_tab, dynamic_tab = _open_account_login_panel(
                page,
                qr_heading,
                stage_reporter=stage_reporter,
            )
            password_tab.wait_for(state="visible", timeout=10_000)
            _report_login_stage(
                stage_reporter,
                "PASSWORD_TAB_VISIBLE",
            )
            dynamic_tab.wait_for(state="visible", timeout=10_000)
            _report_login_stage(
                stage_reporter,
                "LOGIN_PAGE_SWITCHED",
            )
            _report_login_stage(
                stage_reporter,
                "ACCOUNT_LOGIN_PANEL_VISIBLE",
            )
            dynamic_tab.click()
            _report_login_stage(
                stage_reporter,
                "DYNAMIC_TAB_CLICKED",
            )
            form = _unique_locator(
                page,
                DYNAMIC_LOGIN_FORM_SELECTOR,
                "动态密码登录表单",
            )
            form.wait_for(state="visible", timeout=10_000)
            _report_login_stage(
                stage_reporter,
                "DYNAMIC_TAB_OPENED",
            )
        elif state == "DYNAMIC":
            dynamic_tab = None
            _report_login_stage(
                stage_reporter,
                "LOGIN_PAGE_SWITCHED",
            )
            _report_login_stage(
                stage_reporter,
                "ACCOUNT_LOGIN_PANEL_VISIBLE",
            )
            _report_login_stage(
                stage_reporter,
                "DYNAMIC_TAB_OPENED",
            )
        elif state == "ACCOUNT":
            password_tab = page.locator(PASSWORD_LOGIN_TAB_SELECTOR)
            dynamic_tab = page.locator(DYNAMIC_LOGIN_TAB_SELECTOR)
            _report_login_stage(
                stage_reporter,
                "LOGIN_PAGE_SWITCHED",
            )
            _report_login_stage(
                stage_reporter,
                "ACCOUNT_LOGIN_PANEL_VISIBLE",
            )
            dynamic_tab.click()
            _report_login_stage(
                stage_reporter,
                "DYNAMIC_TAB_CLICKED",
            )
            form = _unique_locator(
                page,
                DYNAMIC_LOGIN_FORM_SELECTOR,
                "动态密码登录表单",
            )
            form.wait_for(state="visible", timeout=10_000)
            _report_login_stage(
                stage_reporter,
                "DYNAMIC_TAB_OPENED",
            )
        else:
            raise LoginPageStateError("LOGIN_PAGE_STATE_TIMEOUT")

        _unique_locator(
            page,
            PHONE_OR_EMAIL_SELECTOR,
            "手机号输入框",
        ).wait_for(state="visible", timeout=10_000)
        _unique_locator(
            page,
            REQUEST_DYNAMIC_PASSWORD_SELECTOR,
            "获取动态密码按钮",
        ).wait_for(state="visible", timeout=10_000)
        _unique_locator(
            page,
            DYNAMIC_PASSWORD_SELECTOR,
            "动态密码输入框",
        ).wait_for(state="visible", timeout=10_000)
    except Exception as exc:
        if save_diagnostics:
            _save_login_switch_diagnostics(page, type(exc).__name__)
        if isinstance(exc, OtpError):
            raise
        raise OtpError("未能切换到动态密码登录页") from exc


def _wait_for_phone_or_email(
    page: Any,
    timeout_seconds: int,
    *,
    phone_number: str | None = None,
    stage_reporter: LoginStageReporter | None = None,
) -> None:
    del timeout_seconds
    phone = _unique_locator(
        page,
        PHONE_OR_EMAIL_SELECTOR,
        "手机号或邮箱输入框",
    )
    phone.wait_for(state="visible", timeout=10_000)
    configured_phone = (
        (phone_number or "").strip()
        or os.environ.get(CLOUD_LOGIN_PHONE_ENV, "").strip()
        or os.environ.get(LOGIN_PHONE_ENV, "").strip()
    )
    if not configured_phone:
        configured_phone = ensure_local_login_phone()
    if phone.input_value().strip() != configured_phone:
        phone.fill(configured_phone)
    _report_login_stage(stage_reporter, "PHONE_FILLED")


def _find_visible_slider(
    page: Any,
    *,
    detection_timeout_seconds: float,
) -> Any | None:
    deadline = time.monotonic() + max(0, detection_timeout_seconds)
    while True:
        frames = list(getattr(page, "frames", ()))
        targets = frames or [page]
        for target in targets:
            try:
                slider = target.locator(SHUMEI_SLIDER_SELECTOR)
                if slider.count() == 1 and slider.is_visible():
                    return slider
            except Exception:
                continue
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.2)


def _wait_for_slider_if_present(
    page: Any,
    timeout_seconds: int,
    *,
    detection_timeout_seconds: float = 3,
    allow_manual_completion: bool = True,
    stage_reporter: LoginStageReporter | None = None,
) -> None:
    slider = _find_visible_slider(
        page,
        detection_timeout_seconds=detection_timeout_seconds,
    )
    if slider is None:
        _report_login_stage(stage_reporter, "SLIDER_ABSENT")
        return
    _report_login_stage(stage_reporter, "SLIDER_PRESENT")
    if not allow_manual_completion:
        raise AdditionalVerificationRequiredError(
            "登录需要人工完成滑块验证"
        )
    print(
        "需要人工完成一次滑块；完成后程序将自动继续。",
        flush=True,
    )
    try:
        slider.wait_for(
            state="hidden",
            timeout=max(1, timeout_seconds) * 1_000,
        )
    except Exception as exc:
        raise OtpError("滑块未在等待时间内完成") from exc


def _save_otp_timeout_screenshot(page: Any) -> None:
    try:
        OTP_DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
        filename = (
            "otp_timeout_"
            f"{time.strftime('%Y%m%d-%H%M%S')}.png"
        )
        page.screenshot(
            path=str(OTP_DIAGNOSTIC_DIR / filename),
            full_page=True,
        )
        print(
            "验证码等待超时，已在本地认证诊断目录保存页面截图。",
            flush=True,
        )
    except Exception:
        print("验证码等待超时，调试截图保存失败。", flush=True)


def _wait_for_otp_request_button_enabled(
    page: Any,
    *,
    timeout_seconds: int,
) -> None:
    page.wait_for_function(
        "() => {"
        "const button=document.querySelector('#btnGetDynamic');"
        "return Boolean(button && !button.disabled);"
        "}",
        timeout=max(1, timeout_seconds) * 1_000,
    )


def _confirm_dynamic_login_attempt_ready(
    page: Any,
    *,
    manual_timeout_seconds: int,
    phone_number: str | None,
    stage_reporter: LoginStageReporter | None,
) -> Any:
    _unique_locator(
        page,
        DYNAMIC_LOGIN_FORM_SELECTOR,
        "动态密码登录表单",
    ).wait_for(state="visible", timeout=10_000)
    _wait_for_phone_or_email(
        page,
        manual_timeout_seconds,
        phone_number=phone_number,
        stage_reporter=stage_reporter,
    )
    request_button = _unique_locator(
        page,
        REQUEST_DYNAMIC_PASSWORD_SELECTOR,
        "获取动态密码按钮",
    )
    request_button.wait_for(state="visible", timeout=10_000)
    _unique_locator(
        page,
        DYNAMIC_PASSWORD_SELECTOR,
        "动态密码输入框",
    ).wait_for(state="visible", timeout=10_000)
    return request_button


def complete_dynamic_password_login(
    page: Any,
    otp_reader: ImapOtpReader,
    *,
    manual_timeout_seconds: int,
    otp_timeout_seconds: int = OTP_TIMEOUT_SECONDS,
    phone_number: str | None = None,
    allow_manual_slider: bool = True,
    save_diagnostics: bool = True,
    stage_reporter: LoginStageReporter | None = None,
    expected_otp_length: int | None = None,
    max_otp_attempts: int = OTP_MAX_ATTEMPTS,
    otp_poll_interval_seconds: float = OTP_POLL_INTERVAL_SECONDS,
    request_recovery_timeout_seconds: int = (
        OTP_REQUEST_RECOVERY_TIMEOUT_SECONDS
    ),
    before_otp_request: Callable[[int], None] | None = None,
) -> AuthObservation:
    if max_otp_attempts < 1:
        raise ValueError("动态密码申请次数必须至少为1")
    _report_login_stage(stage_reporter, "LOGIN_FLOW_STARTED")
    _switch_to_dynamic_password_login(
        page,
        save_diagnostics=save_diagnostics,
        stage_reporter=stage_reporter,
    )
    otp_reader.connect()
    processed_uids: set[int] = set()
    used_otps: set[str] = set()
    otp: str | None = None

    for attempt in range(1, max_otp_attempts + 1):
        _report_login_stage(
            stage_reporter,
            "OTP_ATTEMPT_STARTED",
            attempt=attempt,
        )
        request_button = _confirm_dynamic_login_attempt_ready(
            page,
            manual_timeout_seconds=manual_timeout_seconds,
            phone_number=phone_number,
            stage_reporter=stage_reporter,
        )
        if attempt == 1:
            _wait_for_otp_request_button_enabled(
                page,
                timeout_seconds=10,
            )

        otp_reader.connect()
        baseline_uid = otp_reader.current_max_uid()
        requested_at = datetime.now(timezone.utc)
        _report_login_stage(
            stage_reporter,
            "IMAP_BASELINE_RECORDED",
            attempt=attempt,
        )
        if before_otp_request is not None:
            before_otp_request(attempt)
        request_button.click()
        _report_login_stage(
            stage_reporter,
            "OTP_REQUEST_CLICKED",
            attempt=attempt,
        )
        _wait_for_slider_if_present(
            page,
            manual_timeout_seconds,
            allow_manual_completion=allow_manual_slider,
            stage_reporter=stage_reporter,
        )

        try:
            otp = otp_reader.wait_for_new_otp(
                baseline_uid,
                timeout_seconds=otp_timeout_seconds,
                poll_interval_seconds=otp_poll_interval_seconds,
                not_before=requested_at,
                clock_skew_seconds=OTP_CLOCK_SKEW_SECONDS,
                processed_uids=processed_uids,
                used_otps=used_otps,
            )
        except OtpTimeoutError:
            _report_login_stage(
                stage_reporter,
                "OTP_ATTEMPT_TIMEOUT",
                attempt=attempt,
            )
            if attempt >= max_otp_attempts:
                if save_diagnostics:
                    _save_otp_timeout_screenshot(page)
                raise
            _report_login_stage(
                stage_reporter,
                "OTP_RETRY_WAIT_STARTED",
                attempt=attempt + 1,
            )
            _wait_for_otp_request_button_enabled(
                page,
                timeout_seconds=request_recovery_timeout_seconds,
            )
            _report_login_stage(
                stage_reporter,
                "OTP_RETRY_READY",
                attempt=attempt + 1,
            )
            continue
        break

    if otp is None:
        raise OtpTimeoutError("三次申请均未收到新的验证码邮件")
    if expected_otp_length is not None and len(otp) != expected_otp_length:
        raise OtpParseError("动态密码长度不符合预期")
    used_otps.add(otp)
    _report_login_stage(
        stage_reporter,
        "OTP_MAIL_RECEIVED",
        otp_length=len(otp),
    )

    dynamic_password = _unique_locator(
        page,
        DYNAMIC_PASSWORD_SELECTOR,
        "动态密码输入框",
    )
    dynamic_password.fill(otp)
    _report_login_stage(stage_reporter, "OTP_FIELD_FILLED")

    login_button = _unique_locator(
        page,
        SUBMIT_DYNAMIC_LOGIN_SELECTOR,
        "登录按钮",
    )
    baseline_cp_cookies, _ = _cp_cookie_state(page)
    login_button.click()
    _report_login_stage(stage_reporter, "LOGIN_BUTTON_CLICKED")
    try:
        page.wait_for_url(
            "https://cp.9cair.com/**",
            timeout=30_000,
            wait_until="domcontentloaded",
        )
        _report_login_stage(stage_reporter, "SSO_HANDOFF_REACHED")
    except Exception:
        _report_login_stage(stage_reporter, "SSO_HANDOFF_TIMEOUT")
    observation = _recover_post_login_mission_page(
        page,
        stage_reporter=stage_reporter,
        baseline_cp_cookies=baseline_cp_cookies,
    )
    _report_login_stage(stage_reporter, "FINAL_PAGE_PROBED")
    if observation.status == AuthStatus.AUTHENTICATED:
        _report_login_stage(
            stage_reporter,
            "MISSION_PAGE_AUTHENTICATED",
        )
    return observation


def _imap_otp_environment_present() -> bool:
    return bool(
        os.environ.get("IMAP_EMAIL")
        or os.environ.get("IMAP_AUTH_CODE")
    )


def try_imap_dynamic_password_login(
    page: Any,
    *,
    manual_timeout_seconds: int,
) -> AuthObservation | None:
    if not _imap_otp_environment_present():
        return None
    try:
        with ImapOtpReader.from_environment() as otp_reader:
            observation = complete_dynamic_password_login(
                page,
                otp_reader,
                manual_timeout_seconds=manual_timeout_seconds,
            )
    except OtpConfigurationError:
        print(
            "IMAP OTP配置不完整，继续使用原有人工认证方式。",
            flush=True,
        )
        return None
    except OtpError as exc:
        print(
            f"IMAP OTP自动登录未完成：{exc}。"
            "继续使用原有人工认证方式。",
            flush=True,
        )
        return None
    except Exception:
        print(
            "动态密码登录页面流程未完成，"
            "继续使用原有人工认证方式。",
            flush=True,
        )
        return None
    emit_safe_status(observation.status)
    return observation


def write_candidate_bundle(bundle: AuthBundle, state_file: Path) -> Path:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{state_file.stem}.",
        suffix=".candidate.storage-state.json",
        dir=state_file.parent,
    )
    candidate = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                auth_bundle_to_dict(bundle),
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            candidate.chmod(0o600)
        except OSError:
            pass
        return candidate
    except Exception:
        candidate.unlink(missing_ok=True)
        raise


def finalize_candidate_bundle(
    candidate: Path,
    state_file: Path,
    first_status: AuthStatus,
    second_status: AuthStatus,
) -> bool:
    if (
        first_status != AuthStatus.AUTHENTICATED
        or second_status != AuthStatus.AUTHENTICATED
    ):
        candidate.unlink(missing_ok=True)
        return False
    os.replace(candidate, state_file)
    return True


def _status_from_subprocess(returncode: int) -> AuthStatus:
    for status, code in STATUS_EXIT_CODES.items():
        if code == returncode:
            return status
    return AuthStatus.PAGE_CHANGED_OR_UNKNOWN


def validate_in_fresh_python_process(
    candidate: Path,
    *,
    channel: str,
) -> AuthStatus:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--validate-existing",
        "--state-file",
        str(candidate),
    ]
    if channel:
        command.extend(["--channel", channel])
    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return AuthStatus.NETWORK_OR_SITE_ERROR
    return _status_from_subprocess(process.returncode)


def validate_existing_file(args: argparse.Namespace) -> int:
    state_file = Path(args.state_file).resolve()
    try:
        bundle = load_auth_bundle_file(state_file)
    except AuthBundleError:
        status = AuthStatus.LOGIN_REQUIRED
        emit_safe_status(status, success_only=True)
        return STATUS_EXIT_CODES[status]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        status = AuthStatus.NETWORK_OR_SITE_ERROR
        emit_safe_status(status, success_only=True)
        return STATUS_EXIT_CODES[status]

    try:
        with sync_playwright() as playwright:
            observation = verify_auth_bundle(
                playwright,
                bundle,
                channel=args.channel,
            )
    except Exception:
        observation = AuthObservation(
            AuthStatus.NETWORK_OR_SITE_ERROR,
            AuthSignals(network_or_site_error=True),
        )
    emit_safe_status(observation.status, success_only=True)
    return STATUS_EXIT_CODES[observation.status]


def verify_loaded_auth_bundle(
    playwright: Any,
    bundle: AuthBundle,
    *,
    channel: str,
) -> AuthObservation:
    try:
        return verify_auth_bundle(
            playwright,
            bundle,
            channel=channel,
        )
    except Exception:
        return AuthObservation(
            AuthStatus.NETWORK_OR_SITE_ERROR,
            AuthSignals(network_or_site_error=True),
        )


def should_start_dynamic_password_login(status: AuthStatus) -> bool:
    return status == AuthStatus.LOGIN_REQUIRED


def run_manual_authentication(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        status = AuthStatus.NETWORK_OR_SITE_ERROR
        emit_safe_status(status)
        return STATUS_EXIT_CODES[status]

    profile_dir = Path(args.profile_dir).resolve()
    state_file = Path(args.state_file).resolve()
    candidate: Path | None = None
    bundle: AuthBundle | None = None
    try:
        saved_bundle = load_auth_bundle_file(state_file)
    except AuthBundleError:
        saved_bundle = None
    launch_options = {"channel": args.channel} if args.channel else {}

    with sync_playwright() as playwright:
        profile_dir.mkdir(parents=True, exist_ok=True)
        persistent_context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 1000},
            **launch_options,
        )
        try:
            if saved_bundle is not None:
                restore_auth_bundle_to_existing_context(
                    persistent_context,
                    saved_bundle,
                )
            page = (
                persistent_context.pages[0]
                if persistent_context.pages
                else persistent_context.new_page()
            )
            initial = navigate_and_probe(page, MISSION_URL)
            emit_safe_status(initial.status)
            observation = initial
            authenticated_page = page
            if initial.status != AuthStatus.AUTHENTICATED:
                if saved_bundle is not None:
                    saved_observation = verify_loaded_auth_bundle(
                        playwright,
                        saved_bundle,
                        channel=args.channel,
                    )
                    if (
                        saved_observation.status
                        == AuthStatus.AUTHENTICATED
                    ):
                        emit_safe_status(
                            AuthStatus.AUTHENTICATED,
                            success_only=True,
                        )
                        return STATUS_EXIT_CODES[
                            AuthStatus.AUTHENTICATED
                        ]
                if not should_start_dynamic_password_login(initial.status):
                    return STATUS_EXIT_CODES[initial.status]
                if not validate_local_imap_configuration(
                    allow_credential_update=True,
                ):
                    return STATUS_EXIT_CODES[AuthStatus.LOGIN_REQUIRED]
                automatic_observation = try_imap_dynamic_password_login(
                    page,
                    manual_timeout_seconds=args.timeout_seconds,
                )
                if (
                    automatic_observation is not None
                    and automatic_observation.status
                    == AuthStatus.AUTHENTICATED
                ):
                    observation = automatic_observation
                else:
                    observation, authenticated_page = (
                        wait_for_manual_authentication(
                            persistent_context,
                            args.timeout_seconds,
                        )
                    )
            if (
                observation.status != AuthStatus.AUTHENTICATED
                or authenticated_page is None
            ):
                return STATUS_EXIT_CODES[observation.status]
            bundle = AuthBundle(
                capture_storage_state(persistent_context),
                capture_session_storage(persistent_context),
            )
            candidate = write_candidate_bundle(bundle, state_file)
        finally:
            persistent_context.close()

        if candidate is None or bundle is None:
            return STATUS_EXIT_CODES[AuthStatus.PAGE_CHANGED_OR_UNKNOWN]

        try:
            first_observation = verify_auth_bundle(
                playwright,
                bundle,
                channel=args.channel,
            )
        except Exception:
            first_observation = AuthObservation(
                AuthStatus.NETWORK_OR_SITE_ERROR,
                AuthSignals(network_or_site_error=True),
            )

    first_status = first_observation.status
    if first_status != AuthStatus.AUTHENTICATED:
        candidate.unlink(missing_ok=True)
        emit_safe_status(first_status)
        return STATUS_EXIT_CODES[first_status]

    second_status = validate_in_fresh_python_process(
        candidate,
        channel=args.channel,
    )
    if not finalize_candidate_bundle(
        candidate,
        state_file,
        first_status,
        second_status,
    ):
        emit_safe_status(second_status)
        return STATUS_EXIT_CODES[second_status]

    emit_safe_status(AuthStatus.AUTHENTICATED, success_only=True)
    return 0


def run(args: argparse.Namespace) -> int:
    if args.validate_imap:
        return 0 if validate_local_imap_configuration(
            allow_credential_update=True,
        ) else 1
    if args.validate_existing:
        return validate_existing_file(args)
    return run_manual_authentication(args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过一次人工认证安全生成完整浏览器认证包"
    )
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE))
    parser.add_argument(
        "--channel",
        default="msedge" if sys.platform == "win32" else "",
        help="Windows默认使用已安装的Edge；留空时使用Playwright Chromium。",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--validate-imap",
        action="store_true",
        help="仅验证本机163邮箱IMAP配置；凭据错误时安全提示更新一次。",
    )
    parser.add_argument(
        "--validate-existing",
        action="store_true",
        help="仅在普通无头Context中验证指定认证包，绝不启动人工认证。",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
