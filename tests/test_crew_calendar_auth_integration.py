import os
import inspect
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import crew_auth_session as auth
import crew_calendar_main as calendar


class FakePage:
    def __init__(self) -> None:
        self.default_timeout = None
        self.navigation_timeout = None

    def set_default_timeout(self, timeout: int) -> None:
        self.default_timeout = timeout

    def set_default_navigation_timeout(self, timeout: int) -> None:
        self.navigation_timeout = timeout


class MissionBodyLocator:
    def __init__(self, page) -> None:
        self.page = page

    def inner_text(self, timeout: int) -> str:
        return self.page.body_text


class MissionNavigationCandidate:
    def __init__(
        self,
        page,
        *,
        visible: bool,
        y: int,
        opens_list: bool = False,
    ) -> None:
        self.page = page
        self.visible = visible
        self.y = y
        self.opens_list = opens_list
        self.clicked = 0
        self.scrolled = 0

    def is_visible(self) -> bool:
        return self.visible

    def bounding_box(self):
        if not self.visible:
            return None
        return {"x": 0, "y": self.y, "width": 100, "height": 30}

    def scroll_into_view_if_needed(self) -> None:
        self.scrolled += 1

    def click(self, timeout: int) -> None:
        self.clicked += 1
        if self.opens_list:
            self.page.url = calendar.MISSION_URL
            self.page.body_text = "我的任务\n07月31日 周五"


class MissionNavigationCandidates:
    def __init__(self, candidates) -> None:
        self.candidates = candidates

    def count(self) -> int:
        return len(self.candidates)

    def nth(self, index: int):
        return self.candidates[index]


class MissionPage:
    def __init__(self) -> None:
        self.url = "https://cp.9cair.com/index.html"
        self.body_text = "首页\n我的任务"
        self.waits: list[int] = []
        self.candidates: list[MissionNavigationCandidate] = []

    def locator(self, selector: str):
        assert selector == "body"
        return MissionBodyLocator(self)

    def get_by_text(self, text: str, *, exact: bool):
        assert text == "我的任务"
        assert exact is True
        return MissionNavigationCandidates(self.candidates)

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()
        self.pages = [self.page]
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False
        self.context: FakeContext | None = None
        self.context_options: dict = {}

    def new_context(self, **options) -> FakeContext:
        self.context_options.update(options)
        if self.context is None:
            self.context = FakeContext()
        return self.context

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_options: list[dict] = []
        self.persistent_launch_options: list[dict] = []

    def launch(self, **options) -> FakeBrowser:
        self.launch_options.append(options)
        return self.browser

    def launch_persistent_context(self, **options) -> FakeContext:
        self.persistent_launch_options.append(options)
        if self.browser.context is None:
            self.browser.context = FakeContext()
        return self.browser.context


class FakePlaywrightManager:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def install_fake_browser(monkeypatch):
    browser = FakeBrowser()
    manager = FakePlaywrightManager(browser)
    context = FakeContext()
    context_options: dict = {}
    browser.context = context
    browser.context_options = context_options

    monkeypatch.setattr(calendar, "sync_playwright", lambda: manager)
    monkeypatch.setattr(
        calendar,
        "resolve_persistent_profile_dir",
        lambda: None,
    )

    def fake_create_context(passed_browser, bundle, **options):
        assert passed_browser is browser
        context_options.update(options)
        return context

    monkeypatch.setattr(
        calendar,
        "create_context_from_auth_bundle",
        fake_create_context,
    )
    return manager, browser, context, context_options


def install_valid_bundle(monkeypatch) -> None:
    monkeypatch.setenv("CREW_STORAGE_STATE_B64", "encoded-test-bundle")
    monkeypatch.setattr(
        calendar,
        "decode_auth_bundle",
        lambda encoded: SimpleNamespace(
            storage_state={},
            session_storage={},
        ),
    )


def test_open_mission_page_clicks_top_navigation_and_waits_for_day_list() -> None:
    page = MissionPage()
    hidden = MissionNavigationCandidate(page, visible=False, y=0)
    content = MissionNavigationCandidate(page, visible=True, y=300)
    top_navigation = MissionNavigationCandidate(
        page,
        visible=True,
        y=20,
        opens_list=True,
    )
    page.candidates = [hidden, content, top_navigation]

    calendar.open_mission_page(page)

    assert top_navigation.clicked == 1
    assert top_navigation.scrolled == 1
    assert content.clicked == 0
    assert "07月31日 周五" in page.body_text


def test_homepage_date_does_not_bypass_mission_navigation() -> None:
    page = MissionPage()
    page.body_text = "首页\n我的任务\n07月30日 周四"
    top_navigation = MissionNavigationCandidate(
        page,
        visible=True,
        y=20,
        opens_list=True,
    )
    page.candidates = [top_navigation]

    calendar.open_mission_page(page)

    assert top_navigation.clicked == 1
    assert page.url == calendar.MISSION_URL
    assert "07月31日 周五" in page.body_text


def test_jiayuguan_routes_use_longest_known_airport_names() -> None:
    calendar.rebuild_airport_indexes()

    assert calendar.AIRPORT_CN_TO_ICAO["嘉峪关"] == "ZLJQ"
    assert calendar.AIRPORT_CN_TO_ICAO["酒泉"] == "ZLJQ"
    assert calendar.AIRPORT_CN_TO_ICAO["嘉峪关酒泉机场"] == "ZLJQ"
    assert calendar.AIRPORT_ICAO_TO_CN["ZLJQ"] == "嘉峪关酒泉"
    assert calendar.split_concat_airport_route("沈阳桃仙嘉峪关酒泉") == (
        "沈阳桃仙",
        "嘉峪关酒泉",
    )
    assert calendar.split_concat_airport_route("嘉峪关酒泉沈阳桃仙") == (
        "嘉峪关酒泉",
        "沈阳桃仙",
    )
    assert calendar.split_concat_airport_route("酒泉沈阳桃仙") == (
        "嘉峪关酒泉",
        "沈阳桃仙",
    )
    assert calendar.split_concat_airport_route("嘉峪关酒泉机场沈阳桃仙") == (
        "嘉峪关酒泉",
        "沈阳桃仙",
    )
    assert calendar.split_concat_airport_route("嘉峪关酒泉沈阳桃仙") != (
        "嘉峪关",
        "酒泉沈阳桃仙",
    )


def test_segment_card_icao_pair_overrides_conflicting_chinese_route() -> None:
    calendar.rebuild_airport_indexes()
    day_block = "\n".join(
        [
            calendar.SEGMENT_CARD_MARKER,
            "9C6500",
            "上海浦东沈阳桃仙 20:50-00:30(+1)",
            "ZLJQ",
            "ZYTX",
        ]
    )

    details = calendar.extract_segment_details_from_day_block(day_block, ["9C6500"])

    assert len(details) == 1
    assert details[0]["dep"] == "ZLJQ"
    assert details[0]["arr"] == "ZYTX"
    assert details[0]["dep_cn"] == "嘉峪关酒泉"
    assert details[0]["arr_cn"] == "沈阳桃仙"


def test_jiayuguan_round_trip_cards_keep_icao_endpoint_order() -> None:
    calendar.rebuild_airport_indexes()
    day_block = "\n".join(
        [
            "08月08日 周六",
            calendar.SEGMENT_CARD_MARKER,
            "9C6499",
            "沈阳桃仙嘉峪关酒泉 15:50-20:05",
            "ZYTX",
            "ZLJQ",
            calendar.SEGMENT_CARD_MARKER,
            "9C6500",
            "嘉峪关酒泉沈阳桃仙 20:50-00:30(+1)",
            "ZLJQ",
            "ZYTX",
        ]
    )

    items = calendar.parse_multi_segment_flight_items(
        "08月08日 周六",
        day_block,
        2026,
    )

    assert [item["flight_no"] for item in items] == ["9C6499", "9C6500"]
    assert [
        (item["dep"], item["arr"], item["dep_cn"], item["arr_cn"])
        for item in items
    ] == [
        ("ZYTX", "ZLJQ", "沈阳桃仙", "嘉峪关酒泉"),
        ("ZLJQ", "ZYTX", "嘉峪关酒泉", "沈阳桃仙"),
    ]


def test_unknown_route_without_known_endpoint_stays_unresolved() -> None:
    calendar.rebuild_airport_indexes()
    assert calendar.split_concat_airport_route("未知甲未知乙") == ("", "")


@pytest.mark.parametrize(
    ("route_text", "expected"),
    [
        ("上海浦东沈阳桃仙", ("上海浦东", "沈阳桃仙")),
        ("乌兰巴托成吉思汗上海浦东", ("乌兰巴托成吉思汗", "上海浦东")),
        ("札幌新千岁上海浦东", ("札幌新千岁", "上海浦东")),
    ],
)
def test_long_airport_names_remain_intact(route_text: str, expected: tuple[str, str]) -> None:
    calendar.rebuild_airport_indexes()
    assert calendar.split_concat_airport_route(route_text) == expected


def test_open_mission_page_does_not_treat_navigation_text_as_task_list() -> None:
    page = MissionPage()
    navigation = MissionNavigationCandidate(page, visible=True, y=20)
    page.candidates = [navigation]

    with pytest.raises(RuntimeError, match="未能进入任务列表页"):
        calendar.open_mission_page(page)

    assert navigation.clicked == 3


def forbid_legacy_and_processing(monkeypatch, calls: list[str]) -> None:
    def forbidden(name: str):
        def fail(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not be called")

        return fail

    for name in (
        "login",
        "solve_captcha",
        "solve_captcha_with_ddddocr",
        "solve_captcha_with_tesseract",
        "snapshot_existing_calendars",
        "rebuild_airport_indexes",
        "open_mission_page",
        "detect_page_year",
        "collect_day_blocks",
        "create_multi_calendars_from_blocks",
    ):
        monkeypatch.setattr(calendar, name, forbidden(name))


def test_authenticated_status_enters_existing_processing_flow(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    manager, browser, context, context_options = install_fake_browser(
        monkeypatch
    )
    calls: list[str] = []

    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page: (_ for _ in ()).throw(
            AssertionError("valid session must not use QQ IMAP")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy login must not be called")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "solve_captcha",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("OCR must not be called")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "snapshot_existing_calendars",
        lambda: calls.append("snapshot"),
    )
    monkeypatch.setattr(
        calendar,
        "rebuild_airport_indexes",
        lambda: calls.append("rebuild"),
    )
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda page: calls.append("open"),
    )
    monkeypatch.setattr(
        calendar,
        "detect_page_year",
        lambda page: calls.append("year") or 2026,
    )
    monkeypatch.setattr(
        calendar,
        "collect_day_blocks",
        lambda page: calls.append("collect") or ["day-block"],
    )
    monkeypatch.setattr(
        calendar,
        "create_multi_calendars_from_blocks",
        lambda blocks, year: calls.append("create"),
    )

    assert calendar.run() == 0

    assert capsys.readouterr().out == "AUTH_STATUS=AUTHENTICATED\n"
    assert calls == [
        "snapshot",
        "rebuild",
        "open",
        "year",
        "collect",
        "create",
    ]
    assert manager.chromium.launch_options == [{"headless": True}]
    assert context_options == {"viewport": {"width": 1400, "height": 1000}}
    assert context.closed is True
    assert browser.closed is True


def test_persistent_profile_reuses_session_without_imap_and_saves_backup(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    manager, browser, context, _ = install_fake_browser(monkeypatch)
    profile_dir = tmp_path / "runner-data" / "browser-profile"
    backup_path = tmp_path / "runner-data" / "auth-backup" / "session.json"
    calls: list[str] = []
    monkeypatch.setenv(calendar.BROWSER_CHANNEL_ENV, "msedge")

    monkeypatch.setattr(
        calendar,
        "resolve_persistent_profile_dir",
        lambda: profile_dir,
    )
    monkeypatch.setattr(
        calendar,
        "resolve_auth_backup_path",
        lambda _profile: backup_path,
    )
    monkeypatch.setattr(
        calendar,
        "restore_auth_bundle_to_existing_context",
        lambda *_args: calls.append("restore-backup"),
    )
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda _page: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda _page: (_ for _ in ()).throw(
            AssertionError("valid persistent session must not use QQ IMAP")
        ),
    )
    monkeypatch.setattr(calendar, "snapshot_existing_calendars", lambda: None)
    monkeypatch.setattr(calendar, "rebuild_airport_indexes", lambda: None)
    monkeypatch.setattr(calendar, "open_mission_page", lambda _page: None)
    monkeypatch.setattr(
        calendar,
        "_write_filtered_auth_backup",
        lambda passed_context, path: calls.append(
            f"backup:{passed_context is context}:{path == backup_path}"
        ),
    )
    monkeypatch.setattr(calendar, "detect_page_year", lambda _page: 2026)
    monkeypatch.setattr(
        calendar,
        "collect_day_blocks",
        lambda _page: ["day-block"],
    )
    monkeypatch.setattr(
        calendar,
        "create_multi_calendars_from_blocks",
        lambda _blocks, _year: None,
    )

    assert calendar.run() == 0

    assert capsys.readouterr().out == "AUTH_STATUS=AUTHENTICATED\n"
    assert manager.chromium.launch_options == []
    assert manager.chromium.persistent_launch_options == [
        {
            "user_data_dir": str(profile_dir),
            "headless": True,
            "viewport": {"width": 1400, "height": 1000},
            "channel": "msedge",
        }
    ]
    assert calls == ["backup:True:True"]
    assert context.closed is True
    assert browser.closed is False


def test_missing_profile_session_storage_recovers_local_bundle_first(
    monkeypatch,
) -> None:
    context = object()
    page = object()
    local_backup = auth.AuthBundle({}, {"https://cp.9cair.com": {"k": "v"}})
    secret_bundle = auth.AuthBundle({}, {"https://cp.9cair.com": {"s": "v"}})
    events: list[str] = []

    def verify(_playwright, bundle, *, channel):
        events.append(
            "verify-local" if bundle is local_backup else "verify-secret"
        )
        return auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        )

    monkeypatch.setattr(calendar, "verify_auth_bundle", verify)
    monkeypatch.setattr(
        calendar,
        "restore_auth_bundle_to_existing_context",
        lambda passed_context, bundle: events.append(
            f"restore:{passed_context is context}:{bundle is local_backup}"
        ),
    )
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda passed_page: events.append(f"probe:{passed_page is page}")
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )

    observation = calendar._recover_persistent_authentication(
        object(),
        context,
        page,
        initial_observation=auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
        local_backup=local_backup,
        secret_bundle=secret_bundle,
        channel="msedge",
    )

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert events == ["verify-local", "restore:True:True", "probe:True"]


def test_invalid_local_backup_falls_back_to_verified_secret(monkeypatch) -> None:
    local_backup = auth.AuthBundle({}, {})
    secret_bundle = auth.AuthBundle({}, {"https://cp.9cair.com": {"k": "v"}})
    events: list[str] = []

    def verify(_playwright, bundle, *, channel):
        events.append("local" if bundle is local_backup else "secret")
        status = (
            auth.AuthStatus.LOGIN_REQUIRED
            if bundle is local_backup
            else auth.AuthStatus.AUTHENTICATED
        )
        return auth.AuthObservation(status, auth.AuthSignals())

    monkeypatch.setattr(calendar, "verify_auth_bundle", verify)
    monkeypatch.setattr(
        calendar,
        "restore_auth_bundle_to_existing_context",
        lambda _context, bundle: events.append(
            "restore-secret" if bundle is secret_bundle else "restore-local"
        ),
    )
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda _page: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )

    observation = calendar._recover_persistent_authentication(
        object(),
        object(),
        object(),
        initial_observation=auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
        local_backup=local_backup,
        secret_bundle=secret_bundle,
        channel="msedge",
    )

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert events == ["local", "secret", "restore-secret"]


def test_valid_profile_is_not_overwritten_by_backup_or_secret(monkeypatch) -> None:
    valid = auth.AuthObservation(
        auth.AuthStatus.AUTHENTICATED,
        auth.AuthSignals(mission_heading=True, task_container=True),
    )
    monkeypatch.setattr(
        calendar,
        "verify_auth_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("valid profile must not verify fallback bundles")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "restore_auth_bundle_to_existing_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("valid profile cookies must remain untouched")
        ),
    )

    observation = calendar._recover_persistent_authentication(
        object(),
        object(),
        object(),
        initial_observation=valid,
        local_backup=auth.AuthBundle({}, {}),
        secret_bundle=auth.AuthBundle({}, {}),
        channel="msedge",
    )

    assert observation is valid


def test_filtered_auth_backup_is_atomic_and_excludes_other_origins(
    monkeypatch,
    tmp_path: Path,
) -> None:
    backup_path = tmp_path / "auth-backup" / "session.json"
    monkeypatch.setattr(
        calendar,
        "capture_storage_state",
        lambda _context: {
            "cookies": [
                {
                    "name": "CP_SESSION",
                    "value": "test-session-value",
                    "domain": ".9cair.com",
                    "path": "/",
                },
                {
                    "name": "OTHER",
                    "value": "other-value",
                    "domain": ".example.com",
                    "path": "/",
                },
            ],
            "origins": [
                {
                    "origin": "https://cp.9cair.com",
                    "localStorage": [{"name": "cp", "value": "saved"}],
                },
                {
                    "origin": "https://example.com",
                    "localStorage": [{"name": "other", "value": "drop"}],
                },
            ],
        },
    )
    monkeypatch.setattr(
        calendar,
        "capture_session_storage",
        lambda _context: {
            "https://cp.9cair.com": {"cp-key": "cp-value"},
            "https://example.com": {"other-key": "drop"},
        },
    )

    calendar._write_filtered_auth_backup(object(), backup_path)

    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    assert [item["name"] for item in payload["storage_state"]["cookies"]] == [
        "CP_SESSION"
    ]
    assert [
        item["origin"] for item in payload["storage_state"]["origins"]
    ] == ["https://cp.9cair.com"]
    assert set(payload["session_storage"]) == {"https://cp.9cair.com"}
    assert not backup_path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [
        (auth.AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED, 4),
        (auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN, 5),
        (auth.AuthStatus.NETWORK_OR_SITE_ERROR, 6),
    ],
)
def test_non_authenticated_status_never_processes_or_writes_ics(
    status: auth.AuthStatus,
    exit_code: int,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    _, browser, context, _ = install_fake_browser(monkeypatch)
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: auth.AuthObservation(status, auth.AuthSignals()),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page: (_ for _ in ()).throw(
            AssertionError("non-login auth status must not use QQ IMAP")
        ),
    )

    assert calendar.run() == exit_code

    output = capsys.readouterr().out
    assert output.endswith(f"AUTH_STATUS={status.value}\n")
    if status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN:
        assert "LOGIN_ERROR_CATEGORY=LOGIN_RESULT_UNKNOWN" in output
        assert "LOGIN_PAGE_PATH=" in output
        assert "LOGIN_VISIBLE_MISSION_AREA=false" in output
    else:
        assert output == f"AUTH_STATUS={status.value}\n"
    assert calls == []
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context.closed is True
    assert browser.closed is True


@pytest.mark.parametrize("secret", ["", "not-valid-base64"])
def test_missing_or_corrupt_secret_falls_back_without_writing(
    secret: str,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    if secret:
        monkeypatch.setenv("CREW_STORAGE_STATE_B64", secret)
    else:
        monkeypatch.delenv("CREW_STORAGE_STATE_B64", raising=False)
    _, browser, context, context_options = install_fake_browser(monkeypatch)
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
    )

    assert calendar.run() == 3

    assert capsys.readouterr().out == "AUTH_STATUS=LOGIN_REQUIRED\n"
    assert calls == []
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context_options == {"viewport": {"width": 1400, "height": 1000}}
    assert context.closed is True
    assert browser.closed is True


def test_confirmed_login_required_uses_cloud_fallback_then_processes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    install_fake_browser(monkeypatch)
    calls: list[str] = []
    observations = iter(
        [
            auth.AuthObservation(
                auth.AuthStatus.LOGIN_REQUIRED,
                auth.AuthSignals(login_url_hint=True),
            )
        ]
    )
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: next(observations),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda page, **_kwargs: calls.append("fallback")
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "snapshot_existing_calendars",
        lambda: calls.append("snapshot"),
    )
    monkeypatch.setattr(
        calendar,
        "rebuild_airport_indexes",
        lambda: calls.append("rebuild"),
    )
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda page: calls.append("open"),
    )
    monkeypatch.setattr(calendar, "detect_page_year", lambda page: 2026)
    monkeypatch.setattr(
        calendar,
        "collect_day_blocks",
        lambda page: ["day-block"],
    )
    monkeypatch.setattr(
        calendar,
        "create_multi_calendars_from_blocks",
        lambda blocks, year: calls.append("create"),
    )

    assert calendar.run() == 0
    assert calls == [
        "fallback",
        "snapshot",
        "rebuild",
        "open",
        "create",
    ]


def test_successful_cloud_login_refreshes_backup_before_processing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    install_valid_bundle(monkeypatch)
    _, _, context, _ = install_fake_browser(monkeypatch)
    profile_dir = tmp_path / "runner-data" / "browser-profile"
    backup_path = tmp_path / "runner-data" / "auth-backup" / "session.json"
    events: list[str] = []
    monkeypatch.setattr(
        calendar,
        "resolve_persistent_profile_dir",
        lambda: profile_dir,
    )
    monkeypatch.setattr(
        calendar,
        "resolve_auth_backup_path",
        lambda _profile: backup_path,
    )
    monkeypatch.setattr(
        calendar,
        "resolve_auth_control_path",
        lambda _profile: tmp_path / "runner-data" / "auth-control.json",
    )
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda _page: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "_recover_persistent_authentication",
        lambda *_args, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda _page, **_kwargs: events.append("fallback")
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "_write_filtered_auth_backup",
        lambda passed_context, path: events.append(
            f"backup:{passed_context is context}:{path == backup_path}"
        ),
    )
    monkeypatch.setattr(
        calendar,
        "snapshot_existing_calendars",
        lambda: events.append("snapshot"),
    )
    monkeypatch.setattr(
        calendar,
        "rebuild_airport_indexes",
        lambda: events.append("rebuild"),
    )
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda _page: events.append("open"),
    )
    monkeypatch.setattr(calendar, "detect_page_year", lambda _page: 2026)
    monkeypatch.setattr(
        calendar,
        "collect_day_blocks",
        lambda _page: [{"cards": ["card"]}],
    )
    monkeypatch.setattr(
        calendar,
        "create_multi_calendars_from_blocks",
        lambda _blocks, _year: events.append("create"),
    )

    assert calendar.run() == 0
    assert events == [
        "fallback",
        "backup:True:True",
        "snapshot",
        "rebuild",
        "open",
        "backup:True:True",
        "create",
    ]


def test_cloud_fallback_uses_fixed_qq_imap_and_secret_phone(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    captured: dict = {}

    class Reader:
        def __init__(self, email, auth_code, *, host, port) -> None:
            captured["reader"] = (email, auth_code, host, port)

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda page, reader, **options: captured.update(options)
        or auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        ),
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    assert captured["reader"] == (
        "crew@example.invalid",
        "test-auth-code",
        "imap.qq.com",
        993,
    )
    assert captured["phone_number"] == "13000000000"
    assert captured["allow_manual_slider"] is False
    assert captured["save_diagnostics"] is False
    assert captured["expected_otp_length"] == 6
    assert callable(captured["before_otp_request"])


def test_three_workflows_allow_one_otp_event_in_24_hours(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    control_path = tmp_path / "auth-control.json"
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    events: list[str] = []

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            events.append("reader")

        def close(self) -> None:
            events.append("close")

    def fail_after_request(_page, _reader, **options):
        options["before_otp_request"](1)
        events.append("otp-request")
        return auth.AuthObservation(
            auth.AuthStatus.NETWORK_OR_SITE_ERROR,
            auth.AuthSignals(network_or_site_error=True),
        )

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        fail_after_request,
    )
    start = datetime(2026, 8, 21, 9, 30, tzinfo=timezone.utc)

    first = calendar.attempt_cloud_dynamic_password_login(
        object(), auth_control_path=control_path, now=start
    )
    second = calendar.attempt_cloud_dynamic_password_login(
        object(),
        auth_control_path=control_path,
        now=start + timedelta(hours=1),
    )
    third = calendar.attempt_cloud_dynamic_password_login(
        object(),
        auth_control_path=control_path,
        now=start + timedelta(hours=2),
    )

    assert first.status == auth.AuthStatus.NETWORK_OR_SITE_ERROR
    assert second.status == auth.AuthStatus.AUTH_DEFERRED_OTP_COOLDOWN
    assert third.status == auth.AuthStatus.AUTH_DEFERRED_OTP_COOLDOWN
    assert events == ["reader", "otp-request", "close"]
    assert capsys.readouterr().out.count("OTP_COOLDOWN_ACTIVE") >= 2
    payload = json.loads(control_path.read_text(encoding="utf-8"))
    assert payload == {
        "format": calendar.AUTH_CONTROL_FORMAT,
        "last_failure_reason": "NETWORK_OR_SITE_ERROR",
        "last_otp_request_at": "2026-08-21T09:30:00Z",
        "last_otp_result": "FAILED",
    }
    serialized = json.dumps(payload)
    assert "13000000000" not in serialized
    assert "test-auth-code" not in serialized


def test_expired_cooldown_allows_one_new_otp_event(
    monkeypatch,
    tmp_path: Path,
) -> None:
    control_path = tmp_path / "auth-control.json"
    start = datetime(2026, 8, 21, 9, 30, tzinfo=timezone.utc)
    calendar._write_auth_control_state(
        control_path,
        requested_at=start,
        result="FAILED",
        failure_reason="NETWORK_OR_SITE_ERROR",
    )
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    events: list[str] = []

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            events.append("reader")

        def close(self) -> None:
            events.append("close")

    def request_once(_page, _reader, **options):
        options["before_otp_request"](1)
        events.append("otp-request")
        return auth.AuthObservation(
            auth.AuthStatus.NETWORK_OR_SITE_ERROR,
            auth.AuthSignals(network_or_site_error=True),
        )

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        request_once,
    )

    observation = calendar.attempt_cloud_dynamic_password_login(
        object(),
        auth_control_path=control_path,
        now=start + timedelta(hours=24),
    )

    assert observation.status == auth.AuthStatus.NETWORK_OR_SITE_ERROR
    assert events == ["reader", "otp-request", "close"]
    payload = json.loads(control_path.read_text(encoding="utf-8"))
    assert payload["last_otp_request_at"] == "2026-08-22T09:30:00Z"


def test_successful_otp_records_safe_result(monkeypatch, tmp_path: Path) -> None:
    control_path = tmp_path / "auth-control.json"
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    def succeed_after_request(_page, _reader, **options):
        options["before_otp_request"](1)
        return auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(mission_heading=True, task_container=True),
        )

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        succeed_after_request,
    )

    observation = calendar.attempt_cloud_dynamic_password_login(
        object(),
        auth_control_path=control_path,
        now=datetime(2026, 8, 21, 9, 30, tzinfo=timezone.utc),
    )

    assert observation.status == auth.AuthStatus.AUTHENTICATED
    payload = json.loads(control_path.read_text(encoding="utf-8"))
    assert payload["last_otp_result"] == "AUTHENTICATED"
    assert payload["last_failure_reason"] == ""
    assert calendar._otp_cooldown_active(
        control_path,
        now=datetime(2026, 8, 21, 10, 30, tzinfo=timezone.utc),
    ) is False


def test_cloud_fallback_missing_secret_does_not_connect_imap(
    monkeypatch,
) -> None:
    monkeypatch.delenv("CREW_PHONE", raising=False)
    monkeypatch.delenv("IMAP_EMAIL", raising=False)
    monkeypatch.delenv("IMAP_AUTH_CODE", raising=False)
    monkeypatch.setattr(
        calendar,
        "ImapOtpReader",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("missing cloud config must not connect IMAP")
        ),
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.LOGIN_REQUIRED


def test_cooldown_deferred_run_preserves_last_good_calendars(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing_flight = tmp_path / "flight.ics"
    existing_schedule = tmp_path / "crew_schedule.ics"
    existing_flight.write_text("last-good-flight", encoding="utf-8")
    existing_schedule.write_text("last-good-schedule", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    _, browser, context, _ = install_fake_browser(monkeypatch)
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda _page: auth.AuthObservation(
            auth.AuthStatus.LOGIN_REQUIRED,
            auth.AuthSignals(login_url_hint=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "attempt_cloud_dynamic_password_login",
        lambda _page, **_kwargs: auth.AuthObservation(
            auth.AuthStatus.AUTH_DEFERRED_OTP_COOLDOWN,
            auth.AuthSignals(login_url_hint=True),
        ),
    )
    monkeypatch.setattr(
        calendar,
        "ImapOtpReader",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cooldown must not read IMAP")
        ),
    )

    assert calendar.run() == 7
    assert capsys.readouterr().out == (
        "AUTH_STATUS=AUTH_DEFERRED_OTP_COOLDOWN\n"
        "CALENDAR_UPDATE=SKIPPED_PRESERVE_LAST_GOOD\n"
    )
    assert calls == []
    assert existing_flight.read_text(encoding="utf-8") == "last-good-flight"
    assert (
        existing_schedule.read_text(encoding="utf-8")
        == "last-good-schedule"
    )
    assert context.closed is True
    assert browser.closed is True


def test_cloud_slider_requires_additional_verification(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.AdditionalVerificationRequiredError(
                "manual slider required"
            )
        ),
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert (
        observation.status
        == auth.AuthStatus.ADDITIONAL_VERIFICATION_REQUIRED
    )


def test_cloud_toggle_failure_keeps_exact_category_and_closes_reader(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    events: list[str] = []

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def connect(self) -> None:
            events.append("connect")

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.LoginToggleError("ACCOUNT_PANEL_NOT_OPENED")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "登录春秋统一认证",
            "visible_elements": {},
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert events == ["close"]
    assert "LOGIN_ERROR_CATEGORY=ACCOUNT_PANEL_NOT_OPENED" in (
        capsys.readouterr().out
    )


def test_cloud_login_state_timeout_keeps_exact_category(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.LoginPageStateError("LOGIN_PAGE_STATE_TIMEOUT")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "登录春秋统一认证",
            "visible_elements": {},
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert "LOGIN_ERROR_CATEGORY=LOGIN_PAGE_STATE_TIMEOUT" in (
        capsys.readouterr().out
    )


def test_cloud_unknown_writes_only_safe_staged_diagnostic(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    diagnostic_path = tmp_path / "crew-auth-diagnostic.json"
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    monkeypatch.setenv(
        calendar.AUTH_DIAGNOSTIC_PATH_ENV,
        str(diagnostic_path),
    )

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    def fake_login(_page, _reader, **options):
        reporter = options["stage_reporter"]
        reporter(
            "TOGGLE_CANDIDATES_INSPECTED",
            {
                "diagnostic": {
                    "login_badge_count": 2,
                    "badge_icon_count": 2,
                    "visible_badge_icon_count": 1,
                    "eligible_toggle_count": 1,
                    "candidates": [
                        {
                            "index": 0,
                            "visible": False,
                            "bounding_box_exists": False,
                            "display": "none",
                            "visibility": "hidden",
                            "pointer_events": "none",
                            "inside_login_badge": True,
                            "top_right_region": False,
                        }
                    ],
                }
            },
        )
        for stage in (
            "LOGIN_FLOW_STARTED",
            "LOGIN_PAGE_SWITCHED",
            "DYNAMIC_TAB_OPENED",
            "PHONE_FILLED",
            "IMAP_BASELINE_RECORDED",
            "OTP_REQUEST_CLICKED",
            "SLIDER_ABSENT",
        ):
            reporter(stage, {})
        reporter("OTP_MAIL_RECEIVED", {"otp_length": 6})
        for stage in (
            "OTP_FIELD_FILLED",
            "LOGIN_BUTTON_CLICKED",
            "SSO_HANDOFF_REACHED",
        ):
            reporter(stage, {})
        reporter(
            "SSO_SESSION_PROBE",
            {
                "domain": "cp.9cair.com",
                "path": "/",
                "main_frame_domain": "cp.9cair.com",
                "main_frame_path": "/",
                "cp_cookie_names": ["CP_SESSION"],
                "business_cookie_names": ["CP_SESSION"],
                "task_area_visible": False,
            },
        )
        reporter(
            "SSO_BUSINESS_COOKIE_READY",
            {"cookie_names": ["CP_SESSION"]},
        )
        reporter("MISSION_PAGE_REQUESTED", {})
        reporter(
            "MISSION_SINGLE_NAVIGATION_RESULT",
            {
                "domain": "cp.9cair.com",
                "path": "/",
                "main_frame_domain": "cp.9cair.com",
                "main_frame_path": "/",
                "http_status": 200,
                "task_area_visible": False,
            },
        )
        reporter("FINAL_PAGE_PROBED", {})
        return auth.AuthObservation(
            auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN,
            auth.AuthSignals(),
        )

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        fake_login,
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "统一认证中心",
            "visible_elements": {
                "qr_login_page": False,
                "password_login_tab": True,
                "dynamic_login_tab": True,
                "phone_field": True,
                "otp_request_button": True,
                "otp_field": True,
                "slider": False,
                "mission_area": False,
            },
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    output = capsys.readouterr().out
    assert (
        'LOGIN_TOGGLE_DIAGNOSTIC={"badge_icon_count":2'
        in output
    )
    assert "LOGIN_STAGE=OTP_MAIL_RECEIVED OTP_LENGTH=6" in output
    assert (
        'SSO_SESSION_PROBE={"business_cookie_names":["CP_SESSION"],'
        '"cp_cookie_names":["CP_SESSION"],"domain":"cp.9cair.com",'
        '"http_status":0,"main_frame_domain":"cp.9cair.com",'
        '"main_frame_path":"/","path":"/","stage":"SSO_SESSION_PROBE",'
        '"task_area_visible":false}'
        in output
    )
    assert (
        'MISSION_SINGLE_NAVIGATION_RESULT={"domain":"cp.9cair.com",'
        '"http_status":200,"main_frame_domain":"cp.9cair.com",'
        '"main_frame_path":"/","path":"/",'
        '"stage":"MISSION_SINGLE_NAVIGATION_RESULT",'
        '"task_area_visible":false}'
        in output
    )
    assert (
        "LOGIN_ERROR_CATEGORY=POST_LOGIN_HANDOFF_INCOMPLETE"
        in output
    )
    assert "LOGIN_PAGE_DOMAIN=cas.9cair.com" in output
    assert "LOGIN_PAGE_PATH=/login" in output
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert payload["last_stage"] == "FINAL_PAGE_PROBED"
    assert payload["error_category"] == "POST_LOGIN_HANDOFF_INCOMPLETE"
    assert payload["auth_status"] == "PAGE_CHANGED_OR_UNKNOWN"
    serialized = json.dumps(payload, ensure_ascii=False)
    for sensitive in (
        "13000000000",
        "crew@example.invalid",
        "test-auth-code",
        "token",
        "cookie-value",
        "otp_value",
    ):
        assert sensitive not in serialized.lower()


def test_cloud_otp_error_reports_stage_specific_category(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    diagnostic_path = tmp_path / "crew-auth-diagnostic.json"
    monkeypatch.setenv("CREW_PHONE", "13000000000")
    monkeypatch.setenv("IMAP_EMAIL", "crew@example.invalid")
    monkeypatch.setenv("IMAP_AUTH_CODE", "test-auth-code")
    monkeypatch.setenv(
        calendar.AUTH_DIAGNOSTIC_PATH_ENV,
        str(diagnostic_path),
    )

    class Reader:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(calendar, "ImapOtpReader", Reader)
    monkeypatch.setattr(
        calendar,
        "complete_dynamic_password_login",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            calendar.OtpError("safe test failure")
        ),
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: {
            "domain": "cas.9cair.com",
            "path": "/login",
            "title": "",
            "visible_elements": {},
        },
    )

    observation = calendar.attempt_cloud_dynamic_password_login(object())

    assert observation.status == auth.AuthStatus.PAGE_CHANGED_OR_UNKNOWN
    assert "LOGIN_ERROR_CATEGORY=LOGIN_SWITCH_FAILED" in (
        capsys.readouterr().out
    )
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert payload["error_category"] == "LOGIN_SWITCH_FAILED"


def test_processing_exception_returns_one_and_closes_resources(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    _, browser, context, _ = install_fake_browser(monkeypatch)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(),
        ),
    )
    monkeypatch.setattr(calendar, "snapshot_existing_calendars", lambda: None)
    monkeypatch.setattr(calendar, "rebuild_airport_indexes", lambda: None)
    monkeypatch.setenv("IMAP_AUTH_CODE", "secret-auth-code")
    monkeypatch.setattr(
        calendar,
        "open_mission_page",
        lambda page: (_ for _ in ()).throw(
            RuntimeError("page changed secret-auth-code")
        ),
    )

    assert calendar.run() == 1
    assert "RuntimeError" in caplog.text
    assert "page changed <redacted>" in caplog.text
    assert "secret-auth-code" not in caplog.text
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context.closed is True
    assert browser.closed is True


def test_recognized_days_with_zero_cards_stop_before_ics_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    _, browser, context, _ = install_fake_browser(monkeypatch)
    monkeypatch.setattr(
        calendar,
        "navigate_and_probe",
        lambda page: auth.AuthObservation(
            auth.AuthStatus.AUTHENTICATED,
            auth.AuthSignals(),
        ),
    )
    monkeypatch.setattr(calendar, "snapshot_existing_calendars", lambda: None)
    monkeypatch.setattr(calendar, "rebuild_airport_indexes", lambda: None)
    monkeypatch.setattr(calendar, "open_mission_page", lambda page: None)
    monkeypatch.setattr(calendar, "detect_page_year", lambda page: 2026)
    monkeypatch.setattr(
        calendar,
        "get_day_headers",
        lambda page: ["07月31日 周五"],
    )
    monkeypatch.setattr(calendar, "collect_day_blocks", lambda page: [])
    monkeypatch.setattr(
        calendar,
        "create_multi_calendars_from_blocks",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("zero cards must not write ICS")
        ),
    )

    assert calendar.run() == 1
    assert existing.read_text(encoding="utf-8") == "existing-calendar"
    assert context.closed is True
    assert browser.closed is True


def test_context_creation_exception_returns_one_and_closes_browser(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "flight.ics"
    existing.write_text("existing-calendar", encoding="utf-8")
    install_valid_bundle(monkeypatch)
    manager, browser, _, _ = install_fake_browser(monkeypatch)
    calls: list[str] = []
    forbid_legacy_and_processing(monkeypatch, calls)
    monkeypatch.setattr(
        calendar,
        "create_context_from_auth_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("context creation failed")
        ),
    )

    assert calendar.run() == 1
    assert capsys.readouterr().out == ""
    assert calls == []
    assert manager.chromium.launch_options == [{"headless": True}]
    assert browser.closed is True
    assert existing.read_text(encoding="utf-8") == "existing-calendar"


def test_import_does_not_touch_repository_debug_output(
    tmp_path: Path,
) -> None:
    debug_dir = tmp_path / "debug_output"
    debug_dir.mkdir()
    sentinel = debug_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    env = os.environ.copy()
    env.pop("CREW_LEGACY_DIAGNOSTICS", None)
    root = Path(__file__).parents[1]
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(root), env.get("PYTHONPATH", "")])
    )

    result = subprocess.run(
        [sys.executable, "-c", "import crew_calendar_main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "playwright" / ".auth-diagnostics").exists()


def test_formal_run_has_no_legacy_login_or_ocr_call_path() -> None:
    source = inspect.getsource(calendar.run)

    assert "attempt_cloud_dynamic_password_login(" in source
    for forbidden in (
        "solve_captcha",
        "extract_captcha_bytes",
        "pytesseract",
        "ddddocr",
        "screenshot(",
        "page_text(",
    ):
        assert forbidden not in source
