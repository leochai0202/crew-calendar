import pytest

import crew_calendar_main as calendar


class FakeLocator:
    def __init__(self, page, selector: str) -> None:
        self.page = page
        self.selector = selector
        self.first = self

    def inner_text(self, timeout: int) -> str:
        assert self.selector == "body"
        return self.page.body_text

    def click(self, timeout: int) -> None:
        assert self.selector == "text=我的任务"
        self.page.mission_clicks += 1
        if self.page.body_after_mission_click is not None:
            self.page.body_text = self.page.body_after_mission_click


class FakePage:
    def __init__(
        self,
        *,
        url: str,
        body_text: str,
        goto_error: Exception | None = None,
        body_after_goto: str | None = None,
        body_after_mission_click: str | None = None,
    ) -> None:
        self.url = url
        self.body_text = body_text
        self.goto_error = goto_error
        self.body_after_goto = body_after_goto
        self.body_after_mission_click = body_after_mission_click
        self.goto_calls: list[str] = []
        self.load_state_calls = 0
        self.wait_calls = 0
        self.mission_clicks = 0

    def wait_for_load_state(self, state: str, timeout: int) -> None:
        assert state == "domcontentloaded"
        self.load_state_calls += 1

    def wait_for_timeout(self, timeout: int) -> None:
        self.wait_calls += 1

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append(url)
        self.url = url
        if self.body_after_goto is not None:
            self.body_text = self.body_after_goto
        if self.goto_error is not None:
            raise self.goto_error

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)


def test_open_mission_page_reuses_loaded_mission_content() -> None:
    page = FakePage(
        url=calendar.MISSION_URL,
        body_text="我的任务\n07月30日 周四\nMU1234",
    )

    calendar.open_mission_page(page)

    assert page.goto_calls == []
    assert page.mission_clicks == 0


def test_open_mission_page_reuses_existing_mission_area() -> None:
    page = FakePage(
        url="https://cp.9cair.com/",
        body_text="我的任务",
        body_after_mission_click="我的任务\n07月30日 周四\nMU1234",
    )

    calendar.open_mission_page(page)

    assert page.goto_calls == []
    assert page.mission_clicks == 1


def test_open_mission_page_navigates_only_once_when_needed() -> None:
    page = FakePage(
        url="https://cp.9cair.com/home",
        body_text="首页",
        body_after_goto="我的任务\n07月30日 周四\nMU1234",
    )

    calendar.open_mission_page(page)

    assert page.goto_calls == [calendar.MISSION_URL]
    assert page.mission_clicks == 0


def test_interrupted_navigation_waits_and_rechecks_without_retry() -> None:
    page = FakePage(
        url="https://cp.9cair.com/",
        body_text="登录跳转中",
        goto_error=RuntimeError(
            "Navigation is interrupted by another navigation"
        ),
        body_after_goto="我的任务\n07月30日 周四\nMU1234",
    )

    calendar.open_mission_page(page)

    assert page.goto_calls == [calendar.MISSION_URL]


def test_unrelated_navigation_error_is_not_retried() -> None:
    page = FakePage(
        url="https://cp.9cair.com/home",
        body_text="首页",
        goto_error=RuntimeError("net::ERR_CONNECTION_RESET"),
    )

    with pytest.raises(RuntimeError, match="ERR_CONNECTION_RESET"):
        calendar.open_mission_page(page)

    assert page.goto_calls == [calendar.MISSION_URL]
