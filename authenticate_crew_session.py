from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

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
    OtpTimeoutError,
)


DEFAULT_AUTH_DIR = Path("playwright") / ".auth"
DEFAULT_PROFILE_DIR = DEFAULT_AUTH_DIR / "crew-profile"
DEFAULT_STATE_FILE = DEFAULT_AUTH_DIR / "crew-auth-session.storage-state.json"
DEFAULT_LOCAL_ENV_FILE = Path(__file__).resolve().parent / ".env"
DEFAULT_TIMEOUT_SECONDS = 10 * 60
OTP_TIMEOUT_SECONDS = 120
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
    '.login-badge .badge-icon:not([style*="display: none"])'
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


class AdditionalVerificationRequiredError(OtpError):
    pass


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
) -> None:
    try:
        form = page.locator(DYNAMIC_LOGIN_FORM_SELECTOR)
        if form.count() == 1 and form.is_visible():
            dynamic_tab = None
        else:
            password_tab = page.locator(PASSWORD_LOGIN_TAB_SELECTOR)
            dynamic_tab = page.locator(DYNAMIC_LOGIN_TAB_SELECTOR)
            account_tabs_visible = (
                password_tab.count() == 1
                and dynamic_tab.count() == 1
                and password_tab.is_visible()
                and dynamic_tab.is_visible()
            )
            if not account_tabs_visible:
                qr_heading = page.get_by_text(
                    QR_LOGIN_HEADING,
                    exact=True,
                )
                if (
                    qr_heading.count() != 1
                    or not qr_heading.is_visible()
                ):
                    raise OtpError("未识别到扫码登录页或账号登录页")
                toggle = _unique_locator(
                    page,
                    ACCOUNT_LOGIN_TOGGLE_SELECTOR,
                    "二维码面板电脑登录切换控件",
                )
                toggle.wait_for(state="visible", timeout=10_000)
                toggle.click()
                password_tab = _unique_locator(
                    page,
                    PASSWORD_LOGIN_TAB_SELECTOR,
                    "密码登录页签",
                )
                dynamic_tab = _unique_locator(
                    page,
                    DYNAMIC_LOGIN_TAB_SELECTOR,
                    "动态密码登录页签",
                )
                password_tab.wait_for(state="visible", timeout=10_000)
                dynamic_tab.wait_for(state="visible", timeout=10_000)

            dynamic_tab.click()
            form = _unique_locator(
                page,
                DYNAMIC_LOGIN_FORM_SELECTOR,
                "动态密码登录表单",
            )
            form.wait_for(state="visible", timeout=10_000)

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
) -> None:
    slider = _find_visible_slider(
        page,
        detection_timeout_seconds=detection_timeout_seconds,
    )
    if slider is None:
        return
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


def complete_dynamic_password_login(
    page: Any,
    otp_reader: ImapOtpReader,
    *,
    manual_timeout_seconds: int,
    otp_timeout_seconds: int = OTP_TIMEOUT_SECONDS,
    phone_number: str | None = None,
    allow_manual_slider: bool = True,
    save_diagnostics: bool = True,
) -> AuthObservation:
    _switch_to_dynamic_password_login(
        page,
        save_diagnostics=save_diagnostics,
    )
    _wait_for_phone_or_email(
        page,
        manual_timeout_seconds,
        phone_number=phone_number,
    )

    request_button = _unique_locator(
        page,
        REQUEST_DYNAMIC_PASSWORD_SELECTOR,
        "获取动态密码按钮",
    )
    request_button.wait_for(state="visible", timeout=10_000)
    page.wait_for_function(
        "() => {"
        "const button=document.querySelector('#btnGetDynamic');"
        "return Boolean(button && !button.disabled);"
        "}",
        timeout=10_000,
    )

    baseline_uid = otp_reader.current_max_uid()
    request_button.click()
    _wait_for_slider_if_present(
        page,
        manual_timeout_seconds,
        allow_manual_completion=allow_manual_slider,
    )

    try:
        otp = otp_reader.wait_for_new_otp(
            baseline_uid,
            timeout_seconds=otp_timeout_seconds,
        )
    except OtpTimeoutError:
        if save_diagnostics:
            _save_otp_timeout_screenshot(page)
        raise

    dynamic_password = _unique_locator(
        page,
        DYNAMIC_PASSWORD_SELECTOR,
        "动态密码输入框",
    )
    dynamic_password.fill(otp)

    login_button = _unique_locator(
        page,
        SUBMIT_DYNAMIC_LOGIN_SELECTOR,
        "登录按钮",
    )
    login_button.click()
    try:
        page.wait_for_url(
            "https://cp.9cair.com/**",
            timeout=30_000,
            wait_until="domcontentloaded",
        )
    except Exception:
        pass
    return navigate_and_probe(page, MISSION_URL)


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
