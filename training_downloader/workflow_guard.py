"""Read-only GitHub activity check; no login Secrets or production state access."""
from __future__ import annotations

import json
import os
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://api.github.com/repos/leochai0202/crew-calendar"
EXPECTED_WORKFLOWS = {
    "schedule.yml": "fefc765b7845f1ce011662b6deb84206d2149452",
    "sync-airport-manual.yml": "69e45ec40f06e2479ed6ec3912ccf879f73af9bc",
}
ACTIVE_STATES = ("in_progress", "queued", "pending", "waiting", "requested")


class GuardError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def github_get(path: str) -> dict:
    # Fixed API host; never follow a redirect carrying the short-lived API token.
    token = os.environ.get("TRAINING_API_TOKEN", "")
    if not token:
        raise GuardError("CONCURRENCY_CHECK_UNAVAILABLE")
    request = Request(API + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "training-login-guard",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            return json.load(response)
    except Exception:
        raise GuardError("CONCURRENCY_CHECK_UNAVAILABLE") from None


def check_activity(get=github_get, environ=None) -> str:
    env = os.environ if environ is None else environ
    if (env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REPOSITORY") != "leochai0202/crew-calendar"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or not str(env.get("GITHUB_RUN_ID", "")).isdigit()):
        raise GuardError("MANUAL_FIRST_ATTEMPT_REQUIRED")
    current_id = int(env["GITHUB_RUN_ID"])
    # If production no longer uses the reviewed mutex, do not rely on old YAML.
    for name, sha in EXPECTED_WORKFLOWS.items():
        item = get(f"/contents/.github/workflows/{name}?ref=main")
        if item.get("sha") != sha:
            raise GuardError("PRODUCTION_WORKFLOW_CHANGED_REVIEW_REQUIRED")
    for state in ACTIVE_STATES:
        result = get(f"/actions/runs?status={state}&per_page=100")
        runs = result.get("workflow_runs")
        count = result.get("total_count")
        if not isinstance(runs, list) or not isinstance(count, int) or count != len(runs):
            raise GuardError("CONCURRENCY_RESULT_INCOMPLETE")
        # Conservative: any other active workflow blocks, including queued jobs.
        # The shared server-side mutex closes the race with future calendar runs.
        if any(run.get("id") != current_id for run in runs):
            raise GuardError("OTHER_WORKFLOW_ACTIVE")
    return "NO_OTHER_ACTIVE_WORKFLOWS"


def main() -> int:
    try:
        check_activity()
    except Exception:
        print("TRAINING_CONCURRENCY=BLOCKED_OR_UNVERIFIABLE")
        return 2
    print("TRAINING_CONCURRENCY=SAFE_TO_ATTEMPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
