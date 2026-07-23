import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import authenticate_crew_session as local_auth
import crew_auth_session as auth


def sample_storage_state() -> dict:
    return {
        "cookies": [
            {
                "name": "session",
                "value": "redacted-cookie-value",
                "domain": ".9cair.com",
            },
            {
                "name": "cas-session",
                "value": "redacted-cas-value",
                "domain": "cas.9cair.com",
            },
            {
                "name": "unrelated",
                "value": "redacted-unrelated-value",
                "domain": ".bing.com",
            },
        ],
        "origins": [
            {
                "origin": "https://cp.9cair.com",
                "localStorage": [
                    {"name": "site-state", "value": "redacted-local-value"}
                ],
            },
            {
                "origin": "https://cas.9cair.com",
                "localStorage": [],
            },
            {
                "origin": "https://www.bing.com",
                "localStorage": [
                    {"name": "unrelated", "value": "redacted-value"}
                ],
            },
        ],
    }


def sample_bundle(*, with_session_storage: bool = True) -> auth.AuthBundle:
    session_storage = {}
    if with_session_storage:
        session_storage = {
            "https://cp.9cair.com": {
                "client_token": "redacted-session-value",
                "loginUser": "redacted-user-value",
            }
        }
    return auth.AuthBundle(
        auth.filter_storage_state(sample_storage_state()),
        auth.filter_session_storage(session_storage),
    )


class FakeContext:
    def __init__(self, storage_state: dict):
        self.storage_state = storage_state
        self.init_scripts: list[str] = []
        self.closed = False

    def add_init_script(self, *, script: str) -> None:
        self.init_scripts.append(script)

    def new_page(self):
        return SimpleNamespace(context=self)

    def close(self) -> None:
        self.closed = True


class FakeTextLocator:
    def __init__(self, text: str, selector: str):
        self.text = text
        self.selector = selector

    def inner_text(self, timeout: int) -> str:
        return self.text if self.selector == "body" else ""

    def count(self) -> int:
        return 0


class FakeTextPage:
    def __init__(self, text: str):
        self.text = text
        self.url = auth.MISSION_URL

    def locator(self, selector: str) -> FakeTextLocator:
        return FakeTextLocator(self.text, selector)


class FakeBrowser:
    def __init__(self):
        self.contexts: list[FakeContext] = []
        self.closed = False

    def new_context(self, *, storage_state: dict) -> FakeContext:
        context = FakeContext(storage_state)
        self.contexts.append(context)
        return context

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self):
        self.launches: list[dict] = []
        self.browsers: list[FakeBrowser] = []

    def launch(self, **kwargs) -> FakeBrowser:
        self.launches.append(kwargs)
        browser = FakeBrowser()
        self.browsers.append(browser)
        return browser


def fake_playwright() -> SimpleNamespace:
    return SimpleNamespace(chromium=FakeChromium())


def test_storage_state_alone_is_login_required_and_full_bundle_authenticates(
    monkeypatch,
) -> None:
    playwright = fake_playwright()

    def fake_probe(page) -> auth.AuthObservation:
        status = (
            auth.AuthStatus.AUTHENTICATED
            if page.context.init_scripts
            else auth.AuthStatus.LOGIN_REQUIRED
        )
        return auth.AuthObservation(status, auth.AuthSignals())

    monkeypatch.setattr(auth, "navigate_and_probe", fake_probe)

    state_only = auth.verify_auth_bundle(
        playwright,
        sample_bundle(with_session_storage=False),
    )
    complete = auth.verify_auth_bundle(
        playwright,
        sample_bundle(with_session_storage=True),
    )

    assert state_only.status == auth.AuthStatus.LOGIN_REQUIRED
    assert complete.status == auth.AuthStatus.AUTHENTICATED
    assert all(
        launch == {"headless": True}
        for launch in playwright.chromium.launches
    )


def test_bundle_round_trip_filters_unrelated_origins() -> None:
    encoded = auth.encode_auth_bundle(sample_bundle())
    decoded = auth.decode_auth_bundle(encoded)

    assert [item["domain"] for item in decoded.storage_state["cookies"]] == [
        ".9cair.com",
        "cas.9cair.com",
    ]
    assert [
        item["origin"] for item in decoded.storage_state["origins"]
    ] == [
        "https://cp.9cair.com",
        "https://cas.9cair.com",
    ]
    assert set(decoded.session_storage) == {"https://cp.9cair.com"}


def test_session_storage_restore_rejects_wildcards_and_other_origins() -> None:
    with pytest.raises(auth.AuthBundleError):
        auth.normalize_auth_origins(["https://*.9cair.com"])
    with pytest.raises(auth.AuthBundleError):
        auth.normalize_auth_origins(["https://example.com"])

    filtered = auth.filter_session_storage(
        {
            "https://cp.9cair.com": {"allowed-key": "allowed-value"},
            "https://example.com": {"other-key": "other-value"},
        }
    )
    assert set(filtered) == {"https://cp.9cair.com"}


def test_missing_corrupt_and_invalid_bundle_are_login_required(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    missing_args = SimpleNamespace(
        state_file=str(tmp_path / "missing.json"),
        channel="",
    )
    assert local_auth.validate_existing_file(missing_args) == 3
    assert capsys.readouterr().out.startswith("LOGIN_REQUIRED")

    corrupt = tmp_path / "corrupt.storage-state.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    corrupt_args = SimpleNamespace(state_file=str(corrupt), channel="")
    assert local_auth.validate_existing_file(corrupt_args) == 3

    monkeypatch.delenv("CREW_STORAGE_STATE_B64", raising=False)
    assert auth.check_secret_environment("CREW_STORAGE_STATE_B64") == 3


def test_expired_state_redirect_is_login_required() -> None:
    status = auth.classify_auth_signals(
        auth.AuthSignals(login_text=True, login_url_hint=True)
    )
    assert status == auth.AuthStatus.LOGIN_REQUIRED


@pytest.mark.parametrize("marker", ["登录已过期", "会话已过期"])
def test_session_expired_page_is_login_required(marker: str) -> None:
    observation = auth.probe_page(FakeTextPage(marker))
    assert observation.status == auth.AuthStatus.LOGIN_REQUIRED


@pytest.mark.parametrize("marker", ["无权限", "访问被拒绝"])
def test_access_denied_page_is_unknown_even_with_task_content(
    marker: str,
) -> None:
    page_text = f"我的任务\n07月23日 周四\n{marker}"
    observation = auth.probe_page(FakeTextPage(page_text))
    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN


def test_additional_verification_has_priority() -> None:
    status = auth.classify_auth_signals(
        auth.AuthSignals(
            login_form=True,
            login_text=True,
            additional_verification=True,
        )
    )
    assert status == auth.AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED


def test_unknown_page_is_not_treated_as_authenticated() -> None:
    assert (
        auth.classify_auth_signals(auth.AuthSignals())
        == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    )


def test_network_error_is_separate_from_login_error() -> None:
    status = auth.classify_auth_signals(
        auth.AuthSignals(network_or_site_error=True, login_text=True)
    )
    assert status == auth.AuthStatus.NETWORK_OR_SITE_ERROR


def test_additional_verification_page_wins_over_authenticated_page(
    monkeypatch,
) -> None:
    authenticated_page = SimpleNamespace(
        status=auth.AuthStatus.AUTHENTICATED
    )
    verification_page = SimpleNamespace(
        status=auth.AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED
    )
    context = SimpleNamespace(
        pages=[authenticated_page, verification_page]
    )
    monkeypatch.setattr(
        local_auth,
        "probe_page",
        lambda page: auth.AuthObservation(page.status, auth.AuthSignals()),
    )

    observation, selected_page = local_auth.observe_context(context)

    assert observation.status == auth.AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED
    assert selected_page is verification_page


def test_authenticated_page_wins_over_plain_login_page(monkeypatch) -> None:
    login_page = SimpleNamespace(status=auth.AuthStatus.LOGIN_REQUIRED)
    authenticated_page = SimpleNamespace(
        status=auth.AuthStatus.AUTHENTICATED
    )
    context = SimpleNamespace(pages=[login_page, authenticated_page])
    monkeypatch.setattr(
        local_auth,
        "probe_page",
        lambda page: auth.AuthObservation(page.status, auth.AuthSignals()),
    )

    observation, selected_page = local_auth.observe_context(context)

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert selected_page is authenticated_page


def test_safe_log_never_contains_authentication_material(capsys) -> None:
    auth.emit_safe_status(auth.AuthStatus.LOGIN_REQUIRED)
    output = capsys.readouterr().out

    for forbidden in (
        "redacted-cookie-value",
        "redacted-session-value",
        "redacted-user-value",
        "client_token",
        "loginUser",
        '"cookies"',
        '"storage_state"',
    ):
        assert forbidden not in output


def test_failed_validation_does_not_overwrite_old_bundle(
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "crew-auth-session.storage-state.json"
    state_file.write_text('{"old":"still-valid"}', encoding="utf-8")
    candidate = local_auth.write_candidate_bundle(
        sample_bundle(),
        state_file,
    )

    replaced = local_auth.finalize_candidate_bundle(
        candidate,
        state_file,
        auth.AuthStatus.AUTHENTICATED,
        auth.AuthStatus.LOGIN_REQUIRED,
    )

    assert replaced is False
    assert json.loads(state_file.read_text(encoding="utf-8")) == {
        "old": "still-valid"
    }
    assert not candidate.exists()


def test_headless_validation_never_falls_back_to_manual_authentication(
    monkeypatch,
) -> None:
    args = SimpleNamespace(validate_existing=True)
    monkeypatch.setattr(local_auth, "validate_existing_file", lambda _: 3)

    def fail_if_called(_):
        raise AssertionError("不允许回退到人工认证")

    monkeypatch.setattr(
        local_auth,
        "run_manual_authentication",
        fail_if_called,
    )
    assert local_auth.run(args) == 3


def test_fresh_process_command_only_uses_headless_validation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(local_auth.subprocess, "run", fake_run)
    status = local_auth.validate_in_fresh_python_process(
        tmp_path / "candidate.storage-state.json",
        channel="msedge",
    )

    assert status == auth.AuthStatus.AUTHENTICATED
    assert "--validate-existing" in captured["command"]
    assert "--channel" in captured["command"]
    assert captured["kwargs"]["stderr"] == local_auth.subprocess.DEVNULL


def test_workflow_is_manual_read_only_and_has_no_artifacts() -> None:
    workflow = (
        Path(__file__).parents[1]
        / ".github"
        / "workflows"
        / "auth-session-check.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "pull_request:" not in workflow
    assert "\n  push:" not in workflow
    assert "contents: read" in workflow
    assert "CREW_STORAGE_STATE_B64" in workflow
    for forbidden in (
        "upload-artifact",
        "debug_output",
        "flight.ics",
        "crew_calendar_main.py",
    ):
        assert forbidden not in workflow


def test_formal_authentication_files_do_not_use_poc_naming() -> None:
    root = Path(__file__).parents[1]
    for path in (
        root / "crew_auth_session.py",
        root / "authenticate_crew_session.py",
        Path(__file__),
    ):
        assert "poc" not in path.name.lower()


def test_gitignore_excludes_local_authentication_material() -> None:
    content = (Path(__file__).parents[1] / ".gitignore").read_text(
        encoding="utf-8"
    )
    for pattern in (
        "playwright/.auth/",
        "playwright/.auth-diagnostics/",
        "*.storage-state.json",
        "crew-auth-session*.json",
        ".env",
    ):
        assert pattern in content


def test_manual_wait_function_is_not_referenced_by_headless_verifier() -> None:
    source = inspect.getsource(local_auth.validate_existing_file)
    assert "wait_for_manual_authentication" not in source
    assert "launch_persistent_context" not in source
