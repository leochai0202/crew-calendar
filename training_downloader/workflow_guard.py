"""Read-only GitHub activity check; no login Secrets or production state access."""
from __future__ import annotations

import json
import os
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://api.github.com/repos/leochai0202/crew-calendar"
EXPECTED_WORKFLOWS = {
    "schedule.yml": "fefc765b7845f1ce011662b6deb84206d2149452",
    "sync-airport-manual.yml": "69e45ec40f06e2479ed6ec3912ccf879f73af9bc",
}
ACTIVE_STATES = ("in_progress", "queued", "pending", "waiting", "requested")
FAILURE_CODES = frozenset({
    "CONCURRENCY_TOKEN_MISSING", "CONCURRENCY_API_TIMEOUT", "CONCURRENCY_API_TLS_ERROR",
    "CONCURRENCY_API_NETWORK_ERROR", "CONCURRENCY_API_INVALID_JSON",
    "CONCURRENCY_API_HTTP_401", "CONCURRENCY_API_HTTP_403", "CONCURRENCY_API_HTTP_429",
    "CONCURRENCY_API_HTTP_5XX", "CONCURRENCY_API_HTTP_OTHER",
    "MANUAL_FIRST_ATTEMPT_REQUIRED", "PRODUCTION_WORKFLOW_CHANGED_REVIEW_REQUIRED",
    "CONCURRENCY_RESULT_INCOMPLETE", "OTHER_WORKFLOW_ACTIVE",
    "CONCURRENCY_UNEXPECTED_ERROR", "CONCURRENCY_GUARD_IMPORT_FAILED",
})
CHECK_CODES = frozenset({"ENVIRONMENT", "PRODUCTION_WORKFLOW_CONFIG", "GUARD_IMPORT", "UNKNOWN",
                         *("ACTIVE_RUNS_" + state.upper() for state in ACTIVE_STATES)})


class GuardError(RuntimeError):
    def __init__(self, reason: str, check: str = "UNKNOWN"):
        self.reason = reason if reason in FAILURE_CODES else "CONCURRENCY_UNEXPECTED_ERROR"
        self.check = check if check in CHECK_CODES else "UNKNOWN"
        super().__init__(self.reason)


def safe_failure(exc: Exception) -> dict:
    """Only fixed allowlisted fields, never exception text/URLs/headers."""
    if isinstance(exc, GuardError):
        return {"concurrency_failure_reason": exc.reason, "concurrency_check": exc.check}
    return {"concurrency_failure_reason": "CONCURRENCY_UNEXPECTED_ERROR",
            "concurrency_check": "UNKNOWN"}


def transport_failure(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return ({401: "CONCURRENCY_API_HTTP_401", 403: "CONCURRENCY_API_HTTP_403",
                 429: "CONCURRENCY_API_HTTP_429"}.get(exc.code)
                or ("CONCURRENCY_API_HTTP_5XX" if 500 <= exc.code <= 599
                    else "CONCURRENCY_API_HTTP_OTHER"))
    cause = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(cause, (TimeoutError, socket.timeout)):
        return "CONCURRENCY_API_TIMEOUT"
    if isinstance(cause, ssl.SSLError):
        return "CONCURRENCY_API_TLS_ERROR"
    if isinstance(exc, (json.JSONDecodeError, UnicodeError)):
        return "CONCURRENCY_API_INVALID_JSON"
    if isinstance(exc, (URLError, OSError)):
        return "CONCURRENCY_API_NETWORK_ERROR"
    return "CONCURRENCY_UNEXPECTED_ERROR"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def github_get(path: str) -> dict:
    # Fixed API host; never follow a redirect carrying the short-lived API token.
    token = os.environ.get("TRAINING_API_TOKEN", "")
    if not token:
        raise GuardError("CONCURRENCY_TOKEN_MISSING")
    request = Request(API + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "training-login-guard",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            return json.load(response)
    except Exception as exc:
        raise GuardError(transport_failure(exc)) from None


def checked_get(get, path: str, check: str) -> dict:
    try:
        result = get(path)
        if not isinstance(result, dict):
            raise GuardError("CONCURRENCY_RESULT_INCOMPLETE")
        return result
    except Exception as exc:
        reason = exc.reason if isinstance(exc, GuardError) else transport_failure(exc)
        raise GuardError(reason, check) from None


def check_activity(get=github_get, environ=None) -> str:
    env = os.environ if environ is None else environ
    if (env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REPOSITORY") != "leochai0202/crew-calendar"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or not str(env.get("GITHUB_RUN_ID", "")).isdigit()):
        raise GuardError("MANUAL_FIRST_ATTEMPT_REQUIRED", "ENVIRONMENT")
    current_id = int(env["GITHUB_RUN_ID"])
    # If production no longer uses the reviewed mutex, do not rely on old YAML.
    for name, sha in EXPECTED_WORKFLOWS.items():
        item = checked_get(get, f"/contents/.github/workflows/{name}?ref=main", "PRODUCTION_WORKFLOW_CONFIG")
        if item.get("sha") != sha:
            raise GuardError("PRODUCTION_WORKFLOW_CHANGED_REVIEW_REQUIRED", "PRODUCTION_WORKFLOW_CONFIG")
    for state in ACTIVE_STATES:
        check = "ACTIVE_RUNS_" + state.upper()
        result = checked_get(get, f"/actions/runs?status={state}&per_page=100", check)
        runs = result.get("workflow_runs")
        count = result.get("total_count")
        if (not isinstance(runs, list) or type(count) is not int or count != len(runs)
                or any(not isinstance(run, dict) or type(run.get("id")) is not int for run in runs)):
            raise GuardError("CONCURRENCY_RESULT_INCOMPLETE", check)
        # Conservative: any other active workflow blocks, including queued jobs.
        # The shared server-side mutex closes the race with future calendar runs.
        if any(run.get("id") != current_id for run in runs):
            raise GuardError("OTHER_WORKFLOW_ACTIVE", check)
    return "NO_OTHER_ACTIVE_WORKFLOWS"


def main() -> int:
    try:
        check_activity()
    except Exception as exc:
        print("TRAINING_CONCURRENCY=BLOCKED_OR_UNVERIFIABLE")
        failure = safe_failure(exc)
        print("TRAINING_CONCURRENCY_REASON=" + failure["concurrency_failure_reason"])
        print("TRAINING_CONCURRENCY_CHECK=" + failure["concurrency_check"])
        return 2
    print("TRAINING_CONCURRENCY=SAFE_TO_ATTEMPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
