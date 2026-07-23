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
    verify_auth_bundle,
)


DEFAULT_AUTH_DIR = Path("playwright") / ".auth"
DEFAULT_PROFILE_DIR = DEFAULT_AUTH_DIR / "crew-profile"
DEFAULT_STATE_FILE = DEFAULT_AUTH_DIR / "crew-auth-session.storage-state.json"
DEFAULT_TIMEOUT_SECONDS = 10 * 60


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
            page = (
                persistent_context.pages[0]
                if persistent_context.pages
                else persistent_context.new_page()
            )
            initial = navigate_and_probe(page, MISSION_URL)
            emit_safe_status(initial.status)
            observation, authenticated_page = wait_for_manual_authentication(
                persistent_context,
                args.timeout_seconds,
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
        "--validate-existing",
        action="store_true",
        help="仅在普通无头Context中验证指定认证包，绝不启动人工认证。",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
