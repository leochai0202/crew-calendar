from __future__ import annotations

import argparse
import base64
import binascii
import gzip
import io
import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit


MISSION_URL = "https://cp.9cair.com/html/task/mission.html"
AUTH_BUNDLE_FORMAT = "crew-auth-bundle-v1"
ALLOWED_AUTH_ORIGINS = (
    "https://cp.9cair.com",
    "https://cas.9cair.com",
)
MAX_SECRET_B64_BYTES = 48 * 1024
MAX_AUTH_BUNDLE_BYTES = 512 * 1024

DATE_HEADER_RE = re.compile(r"\d{2}月\d{2}日\s*周.")
LOGIN_TEXT_MARKERS = (
    "统一认证中心",
    "账号密码登录",
    "密码登录",
    "扫码登录",
    "二维码登录",
    "请登录",
)
ADDITIONAL_VERIFICATION_MARKERS = (
    "手机验证",
    "手机号验证",
    "短信验证码",
    "邮箱验证",
    "邮件验证",
    "二次验证",
    "安全验证",
    "验证身份",
)
SESSION_EXPIRED_MARKERS = (
    "登录已过期",
    "会话已过期",
)
ACCESS_DENIED_MARKERS = (
    "无权限",
    "权限不足",
    "访问被拒绝",
)


class AuthStatus(str, Enum):
    AUTHENTICATED = "AUTHENTICATED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    ADDITIONAL_VERIFICATION_REQUIRED = "ADDITIONAL_VERIFICATION_REQUIRED"
    PAGE_CHANGED_OR_UNKNOWN = "PAGE_CHANGED_OR_UNKNOWN"
    NETWORK_OR_SITE_ERROR = "NETWORK_OR_SITE_ERROR"


SAFE_STATUS_MESSAGES = {
    AuthStatus.AUTHENTICATED: "认证有效。",
    AuthStatus.LOGIN_REQUIRED: "认证包缺失、损坏或已失效，需要在本机重新认证。",
    AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED: "网站要求人工完成手机、邮箱或二次验证。",
    AuthStatus.PAGE_CHANGED_OR_UNKNOWN: "页面已加载，但无法安全确认认证状态。",
    AuthStatus.NETWORK_OR_SITE_ERROR: "网络连接或站点服务异常，请稍后重试。",
}

STATUS_EXIT_CODES = {
    AuthStatus.AUTHENTICATED: 0,
    AuthStatus.LOGIN_REQUIRED: 3,
    AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED: 4,
    AuthStatus.PAGE_CHANGED_OR_UNKNOWN: 5,
    AuthStatus.NETWORK_OR_SITE_ERROR: 6,
}


class AuthBundleError(ValueError):
    pass


@dataclass(frozen=True)
class AuthBundle:
    storage_state: dict[str, Any]
    session_storage: dict[str, dict[str, str]]


@dataclass(frozen=True)
class AuthSignals:
    mission_heading: bool = False
    task_container: bool = False
    user_indicator: bool = False
    login_form: bool = False
    login_text: bool = False
    qr_indicator: bool = False
    additional_verification: bool = False
    session_expired: bool = False
    access_denied: bool = False
    login_url_hint: bool = False
    network_or_site_error: bool = False


@dataclass(frozen=True)
class AuthObservation:
    status: AuthStatus
    signals: AuthSignals


def normalize_auth_origins(origins: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in origins:
        if "*" in value:
            raise AuthBundleError("认证域名不能包含通配符")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AuthBundleError("认证域名必须是完整的http/https origin")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in ALLOWED_AUTH_ORIGINS:
            raise AuthBundleError("认证域名不在允许列表中")
        if origin not in normalized:
            normalized.append(origin)
    return tuple(normalized)


def _cookie_applies_to_allowed_host(
    cookie: dict[str, Any], allowed_hosts: set[str]
) -> bool:
    domain = str(cookie.get("domain", "")).lstrip(".").lower()
    return bool(domain) and any(
        host == domain or host.endswith(f".{domain}") for host in allowed_hosts
    )


def filter_storage_state(
    storage_state: dict[str, Any],
    allowed_origins: Iterable[str] = ALLOWED_AUTH_ORIGINS,
) -> dict[str, Any]:
    if not isinstance(storage_state, dict):
        raise AuthBundleError("storage state格式无效")
    origins = normalize_auth_origins(allowed_origins)
    allowed = set(origins)
    allowed_hosts = {
        parsed.hostname
        for origin in origins
        if (parsed := urlsplit(origin)).hostname
    }
    cookies = storage_state.get("cookies", [])
    origin_data = storage_state.get("origins", [])
    if not isinstance(cookies, list) or not isinstance(origin_data, list):
        raise AuthBundleError("storage state格式无效")

    filtered = dict(storage_state)
    filtered["cookies"] = [
        dict(cookie)
        for cookie in cookies
        if isinstance(cookie, dict)
        and _cookie_applies_to_allowed_host(cookie, allowed_hosts)
    ]
    filtered["origins"] = [
        dict(item)
        for item in origin_data
        if isinstance(item, dict) and str(item.get("origin", "")) in allowed
    ]
    return filtered


def filter_session_storage(
    session_storage: dict[str, Any],
    allowed_origins: Iterable[str] = ALLOWED_AUTH_ORIGINS,
) -> dict[str, dict[str, str]]:
    if not isinstance(session_storage, dict):
        raise AuthBundleError("session storage格式无效")
    allowed = set(normalize_auth_origins(allowed_origins))
    filtered: dict[str, dict[str, str]] = {}
    for origin, entries in session_storage.items():
        if origin not in allowed or not isinstance(entries, dict):
            continue
        filtered[origin] = {
            str(key): str(value)
            for key, value in sorted(entries.items())
        }
    return dict(sorted(filtered.items()))


def make_auth_bundle(payload: dict[str, Any]) -> AuthBundle:
    if not isinstance(payload, dict):
        raise AuthBundleError("认证包格式无效")
    if payload.get("format") != AUTH_BUNDLE_FORMAT:
        raise AuthBundleError("认证包版本不受支持")
    storage_state = filter_storage_state(payload.get("storage_state", {}))
    session_storage = filter_session_storage(payload.get("session_storage", {}))
    return AuthBundle(storage_state, session_storage)


def auth_bundle_to_dict(bundle: AuthBundle) -> dict[str, Any]:
    return {
        "format": AUTH_BUNDLE_FORMAT,
        "storage_state": filter_storage_state(bundle.storage_state),
        "session_storage": filter_session_storage(bundle.session_storage),
    }


def load_auth_bundle_file(path: Path) -> AuthBundle:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthBundleError("认证包无法读取") from exc
    return make_auth_bundle(payload)


def encode_auth_bundle(bundle: AuthBundle) -> bytes:
    raw = json.dumps(
        auth_bundle_to_dict(bundle),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(raw) > MAX_AUTH_BUNDLE_BYTES:
        raise AuthBundleError("认证包超过安全大小限制")
    encoded = base64.b64encode(gzip.compress(raw, compresslevel=9))
    if len(encoded) >= MAX_SECRET_B64_BYTES:
        raise AuthBundleError("认证包超过GitHub Secret大小限制")
    return encoded


def decode_auth_bundle(encoded: str | bytes) -> AuthBundle:
    try:
        encoded_bytes = encoded.encode("ascii") if isinstance(encoded, str) else encoded
    except UnicodeEncodeError as exc:
        raise AuthBundleError("认证包Base64格式无效") from exc
    if not encoded_bytes or len(encoded_bytes) >= MAX_SECRET_B64_BYTES:
        raise AuthBundleError("认证包缺失或超过大小限制")
    try:
        compressed = base64.b64decode(encoded_bytes, validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(MAX_AUTH_BUNDLE_BYTES + 1)
    except (binascii.Error, EOFError, OSError) as exc:
        raise AuthBundleError("认证包Base64或gzip格式无效") from exc
    if len(raw) > MAX_AUTH_BUNDLE_BYTES:
        raise AuthBundleError("认证包解压后超过安全大小限制")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuthBundleError("认证包JSON格式无效") from exc
    return make_auth_bundle(payload)


def add_session_storage_init_script(
    context: Any,
    session_storage: dict[str, dict[str, str]],
) -> None:
    scoped = filter_session_storage(session_storage)
    if not any(scoped.values()):
        return
    serialized = json.dumps(scoped, ensure_ascii=False, separators=(",", ":"))
    context.add_init_script(
        script=(
            "(() => {"
            f"const states={serialized};"
            "const origin=window.location.origin;"
            "if(!Object.prototype.hasOwnProperty.call(states,origin))return;"
            "for(const [key,value] of Object.entries(states[origin]))"
            "window.sessionStorage.setItem(key,value);"
            "})();"
        )
    )


def classify_auth_signals(signals: AuthSignals) -> AuthStatus:
    if signals.network_or_site_error:
        return AuthStatus.NETWORK_OR_SITE_ERROR
    if signals.additional_verification:
        return AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED
    if signals.session_expired:
        return AuthStatus.LOGIN_REQUIRED
    if signals.access_denied:
        return AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    if (
        signals.mission_heading
        and (signals.task_container or signals.user_indicator)
        and not (signals.login_form or signals.login_text or signals.qr_indicator)
    ):
        return AuthStatus.AUTHENTICATED
    if (
        signals.login_form
        or signals.login_text
        or signals.qr_indicator
        or signals.login_url_hint
    ):
        return AuthStatus.LOGIN_REQUIRED
    return AuthStatus.PAGE_CHANGED_OR_UNKNOWN


def _locator_visible(page: Any, selector: str) -> bool:
    try:
        locator = page.locator(selector)
        return any(
            locator.nth(index).is_visible(timeout=500)
            for index in range(min(locator.count(), 5))
        )
    except Exception:
        return False


def _page_body_text(page: Any) -> str:
    try:
        return page.locator("body").inner_text(timeout=5_000)
    except Exception:
        return ""


def probe_page(page: Any) -> AuthObservation:
    body_text = _page_body_text(page)
    compact_text = re.sub(r"\s+", "", body_text)
    try:
        parsed = urlsplit(str(page.url))
        path_probe = f"{parsed.netloc}{parsed.path}".lower()
    except Exception:
        path_probe = ""

    signals = AuthSignals(
        mission_heading=(
            "我的任务" in compact_text
            or _locator_visible(page, "text=我的任务")
        ),
        task_container=(
            bool(DATE_HEADER_RE.search(body_text))
            or _locator_visible(
                page,
                "[class*='mission' i], [class*='task-list' i], "
                "[data-testid*='task' i]",
            )
        ),
        user_indicator=(
            "退出登录" in compact_text
            or _locator_visible(page, "[class*='avatar' i]")
            or _locator_visible(page, "[class*='user-info' i]")
        ),
        login_form=(
            _locator_visible(page, "input[type='password']")
            or _locator_visible(page, "form input[name*='password' i]")
            or _locator_visible(
                page, "form input[autocomplete='current-password']"
            )
        ),
        login_text=any(marker in compact_text for marker in LOGIN_TEXT_MARKERS),
        qr_indicator=(
            _locator_visible(page, "[class*='qr' i]")
            or _locator_visible(page, "img[alt*='二维码']")
            or _locator_visible(page, "img[src*='qr' i]")
        ),
        additional_verification=any(
            marker in compact_text
            for marker in ADDITIONAL_VERIFICATION_MARKERS
        ),
        session_expired=any(
            marker in compact_text for marker in SESSION_EXPIRED_MARKERS
        ),
        access_denied=any(
            marker in compact_text for marker in ACCESS_DENIED_MARKERS
        ),
        login_url_hint=any(
            marker in path_probe for marker in ("/login", "/auth", "/sso")
        ),
    )
    return AuthObservation(classify_auth_signals(signals), signals)


def navigate_and_probe(
    page: Any, url: str = MISSION_URL
) -> AuthObservation:
    try:
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=90_000,
        )
        try:
            response_status = int(response.status)
        except Exception:
            response_status = 0
        if response_status >= 500:
            signals = AuthSignals(network_or_site_error=True)
            return AuthObservation(AuthStatus.NETWORK_OR_SITE_ERROR, signals)
        if response_status in {401, 403}:
            signals = AuthSignals(login_url_hint=True)
            return AuthObservation(AuthStatus.LOGIN_REQUIRED, signals)
        page.wait_for_timeout(2_000)
        return probe_page(page)
    except Exception:
        signals = AuthSignals(network_or_site_error=True)
        return AuthObservation(AuthStatus.NETWORK_OR_SITE_ERROR, signals)


def verify_auth_bundle(
    playwright: Any,
    bundle: AuthBundle,
    *,
    channel: str = "",
) -> AuthObservation:
    launch_options = {"channel": channel} if channel else {}
    browser = playwright.chromium.launch(headless=True, **launch_options)
    context = browser.new_context(storage_state=bundle.storage_state)
    try:
        add_session_storage_init_script(context, bundle.session_storage)
        page = context.new_page()
        return navigate_and_probe(page)
    finally:
        context.close()
        browser.close()


def safe_status_line(status: AuthStatus, *, success_only: bool = False) -> str:
    if status == AuthStatus.AUTHENTICATED and success_only:
        return AuthStatus.AUTHENTICATED.value
    return f"{status.value}: {SAFE_STATUS_MESSAGES[status]}"


def emit_safe_status(
    status: AuthStatus,
    *,
    success_only: bool = False,
) -> None:
    print(safe_status_line(status, success_only=success_only), flush=True)


def check_secret_environment(variable_name: str) -> int:
    encoded = os.environ.get(variable_name, "")
    try:
        bundle = decode_auth_bundle(encoded)
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
            observation = verify_auth_bundle(playwright, bundle)
    except Exception:
        observation = AuthObservation(
            AuthStatus.NETWORK_OR_SITE_ERROR,
            AuthSignals(network_or_site_error=True),
        )
    emit_safe_status(observation.status, success_only=True)
    return STATUS_EXIT_CODES[observation.status]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="在无头浏览器中安全检查完整认证包"
    )
    parser.add_argument(
        "--check-secret-env",
        metavar="VARIABLE",
        help="从指定环境变量读取Base64+gzip认证包并只输出认证状态。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_secret_env:
        return check_secret_environment(args.check_secret_env)
    raise SystemExit("必须指定--check-secret-env")


if __name__ == "__main__":
    raise SystemExit(main())
