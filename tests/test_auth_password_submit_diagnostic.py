import json

import crew_calendar_main as calendar


class Element:
    def __init__(
        self,
        *,
        value: str = "",
        text: str = "",
        attributes: dict[str, str] | None = None,
        tag: str = "input",
        form_id: str = "",
        form_action: str = "",
        form_method: str = "",
        selectors: set[str] | None = None,
    ) -> None:
        self.value = value
        self.text = text
        self.attributes = attributes or {}
        self.tag = tag
        self.form_id = form_id
        self.form_action = form_action
        self.form_method = form_method
        self.selectors = selectors or set()

    def input_value(self, timeout: int = 0) -> str:
        return self.value

    def get_attribute(self, name: str, timeout: int = 0):
        return self.attributes.get(name)

    def is_visible(self, timeout: int = 0) -> bool:
        return True

    def is_enabled(self, timeout: int = 0) -> bool:
        return True

    def inner_text(self, timeout: int = 0) -> str:
        return self.text

    def evaluate(self, script: str, argument=None):
        if "matches(selector)" in script:
            return argument in self.selectors
        if "tagName" in script:
            return self.tag
        if "element.value" in script:
            return self.value
        if "form.id" in script:
            return self.form_id
        if "form.getAttribute('action')" in script:
            return self.form_action
        if "form.getAttribute('method')" in script:
            return self.form_method
        return ""


class Locator:
    def __init__(self, elements: list[Element]) -> None:
        self.elements = elements

    def count(self) -> int:
        return len(self.elements)

    def nth(self, index: int) -> Element:
        return self.elements[index]


class ErrorPage:
    def __init__(self, error: Element | None) -> None:
        self.error = error

    def locator(self, selector: str) -> Locator:
        if selector == calendar.PASSWORD_LOGIN_ERROR_SELECTOR and self.error:
            return Locator([self.error])
        return Locator([])


class Request:
    def __init__(self, method: str, url: str, resource_type: str) -> None:
        self.method = method
        self.url = url
        self.resource_type = resource_type
        self.post_data = "username=private-user&password=private-password"
        self.headers = {
            "cookie": "private-cookie",
            "authorization": "private-token",
        }


class Response:
    def __init__(self, request: Request, status: int) -> None:
        self.request = request
        self.status = status
        self.headers = {"set-cookie": "private-cookie"}


class NetworkPage:
    def __init__(self) -> None:
        self.handlers: dict[str, list] = {"request": [], "response": []}

    def on(self, event: str, handler) -> None:
        self.handlers[event].append(handler)

    def off(self, event: str, handler) -> None:
        self.handlers[event].remove(handler)

    def emit(self, event: str, value) -> None:
        for handler in list(self.handlers[event]):
            handler(value)


class WaitPage:
    def __init__(self) -> None:
        self.waits: list[int] = []
        self.elapsed = 0
        self.url = "https://cas.9cair.com/login/start?credential=private"

    def wait_for_timeout(self, delay: int) -> None:
        self.waits.append(delay)
        self.elapsed += delay
        if self.elapsed >= 5_000:
            self.url = "https://cas.9cair.com/login?credential=private"
        elif self.elapsed >= 2_000:
            self.url = "https://cas.9cair.com/login/verify?credential=private"


def test_records_actual_password_submit_selector_and_safe_dom(capsys) -> None:
    element = Element(
        tag="button",
        attributes={"id": "loginBtn1", "type": "submit", "name": "login"},
        form_id="logincontentFm1",
        form_action="https://cas.9cair.com/login?service=private",
        form_method="post",
        selectors={"#loginBtn1"},
    )

    details = calendar._password_submit_safe_details(element)
    calendar._emit_password_submit_details(details)

    assert details == {
        "selector": "#loginBtn1",
        "tag": "button",
        "id": "loginBtn1",
        "type": "submit",
        "name": "login",
        "form_id": "logincontentFm1",
        "form_action": "https://cas.9cair.com/login",
        "form_method": "POST",
        "visible": True,
        "enabled": True,
    }
    output = capsys.readouterr().out
    assert "PASSWORD_SUBMIT_SELECTOR=#loginBtn1" in output
    assert "PASSWORD_FORM_ACTION=https://cas.9cair.com/login" in output
    assert "service=private" not in output


def test_credential_diagnostic_records_lengths_never_values(capsys) -> None:
    diagnostic: dict = {}

    filled = calendar._record_password_credential_fill_state(
        diagnostic,
        Element(value="private-user"),
        Element(value="private-password"),
    )

    assert filled is True
    assert diagnostic["password_credentials"] == {
        "username_filled": True,
        "username_length": 12,
        "password_filled": True,
        "password_length": 16,
    }
    output = capsys.readouterr().out
    assert "PASSWORD_USERNAME_LENGTH=12" in output
    assert "PASSWORD_PASSWORD_LENGTH=16" in output
    assert "private-user" not in output
    assert "private-password" not in output
    assert "private-user" not in json.dumps(diagnostic)
    assert "private-password" not in json.dumps(diagnostic)


def test_network_diagnostic_excludes_body_headers_cookies_and_query(capsys) -> None:
    page = NetworkPage()
    request = Request(
        "POST",
        "https://cas.9cair.com/login?username=private-user",
        "document",
    )
    response = Response(request, 302)

    state = calendar._start_password_login_network_capture(page)
    page.emit("request", request)
    page.emit("response", response)
    summary = calendar._stop_password_login_network_capture(page, state)
    diagnostic: dict = {}
    calendar._emit_password_login_network_summary(summary, diagnostic)

    assert summary["submit"] is True
    assert summary["request_method"] == "POST"
    assert summary["request_host"] == "cas.9cair.com"
    assert summary["request_path"] == "/login"
    assert summary["response_status"] == 302
    serialized = json.dumps(diagnostic)
    output = capsys.readouterr().out
    for secret in (
        "private-user",
        "private-password",
        "private-cookie",
        "private-token",
        "username=",
        "authorization",
        "set-cookie",
    ):
        assert secret not in serialized
        assert secret not in output


def test_post_click_diagnostic_records_all_timing_states(
    monkeypatch,
    capsys,
) -> None:
    page = WaitPage()
    snapshots = iter(
        [
            {
                "visible_elements": {
                    "username_field": True,
                    "password_field": True,
                }
            },
            {"visible_elements": {"image_captcha_field": True}},
            {"visible_elements": {"qr_login_page": True}},
        ]
    )
    monkeypatch.setattr(
        calendar,
        "collect_safe_login_page_snapshot",
        lambda _page: next(snapshots),
    )
    monkeypatch.setattr(
        calendar,
        "_safe_visible_password_login_error",
        lambda *_args, **_kwargs: "NONE",
    )
    diagnostic: dict = {}

    result, error = calendar._collect_password_post_click_diagnostics(
        page,
        secrets=("private-user", "private-password"),
        diagnostic=diagnostic,
    )

    assert page.waits == [500, 1_500, 3_000]
    assert [item["label"] for item in result] == ["500MS", "2S", "5S"]
    assert result[0]["username_visible"] is True
    assert result[1]["captcha_visible"] is True
    assert result[2]["qr_visible"] is True
    assert error == "NONE"
    output = capsys.readouterr().out
    assert "PASSWORD_POST_CLICK_500MS_URL=" in output
    assert "PASSWORD_POST_CLICK_2S_URL=" in output
    assert "PASSWORD_POST_CLICK_5S_URL=" in output
    assert "credential=private" not in output


def test_visible_error_is_redacted_normalized_and_limited() -> None:
    error = Element(
        text=(
            "用户名 private-user 密码 private-password 错误 "
            + "额外说明" * 40
        )
    )

    result = calendar._safe_visible_password_login_error(
        ErrorPage(error),
        secrets=("private-user", "private-password"),
    )

    assert len(result) <= 100
    assert "private-user" not in result
    assert "private-password" not in result
    assert "[REDACTED]" in result


def test_failure_reason_no_network_submit() -> None:
    reason = calendar._password_login_failure_reason(
        {"submit": False},
        [{"qr_visible": True}],
        "NONE",
    )

    assert reason == "NO_NETWORK_SUBMIT"


def test_failure_reason_credential_rejected() -> None:
    reason = calendar._password_login_failure_reason(
        {"submit": True},
        [{"username_visible": True}],
        "用户名或密码错误",
    )

    assert reason == "CREDENTIAL_REJECTED"


def test_failure_reason_additional_verification() -> None:
    reason = calendar._password_login_failure_reason(
        {"submit": True},
        [{"captcha_visible": True}],
        "NONE",
    )

    assert reason == "ADDITIONAL_VERIFICATION"


def test_failure_reason_returned_to_qr() -> None:
    reason = calendar._password_login_failure_reason(
        {"submit": True},
        [{"qr_visible": False}, {"qr_visible": True}],
        "NONE",
    )

    assert reason == "RETURNED_TO_QR"


def test_password_diagnostic_does_not_change_otp_or_imap_counts(capsys) -> None:
    diagnostic = {
        "otp_requests": 0,
        "imap_reads": 0,
        "password_login_failure_reason": "RETURNED_TO_QR",
    }

    calendar._emit_auth_io_counts(diagnostic)

    output = capsys.readouterr().out
    assert "OTP_REQUESTS=0" in output
    assert "IMAP_READS=0" in output

