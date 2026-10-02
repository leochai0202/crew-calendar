from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crew_agents.flight_prep_fingerprint import (
    task_fingerprint_from_events,
    task_fingerprint_from_metadata,
)
from crew_agents.ics_utils import parse_ics


BEIJING = ZoneInfo("Asia/Shanghai")
WORKFLOW_FILE = "flight-prep-free-v5-20260616.yml"


@dataclass(frozen=True)
class CheckResult:
    status: str
    target_date: str
    should_dispatch: bool
    reason: str
    task_fingerprint: str
    task_count: int
    state_source: str = ""


def target_date_for_days_ahead(
    days_ahead: int,
    *,
    now: datetime | None = None,
) -> date:
    if days_ahead not in (1, 2):
        raise ValueError("days_ahead must be 1 or 2")
    current = now or datetime.now(BEIJING)
    if current.tzinfo is None:
        current = current.replace(tzinfo=BEIJING)
    return current.astimezone(BEIJING).date() + timedelta(days=days_ahead)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _preparation_state(repo: Path, target: date) -> tuple[dict, str]:
    output_dir = repo / "flight_preparation"
    dated = output_dir / f"{target.isoformat()}_meta.json"
    dated_state = _load_json(dated)
    if dated_state:
        return dated_state, dated.name
    latest = _load_json(output_dir / "latest_meta.json")
    if latest.get("target_date") == target.isoformat():
        return latest, "latest_meta.json"
    return {}, ""


def evaluate_preparation(
    repo: Path,
    target: date,
) -> CheckResult:
    fingerprint, records = task_fingerprint_from_events(
        parse_ics(repo / "flight.ics"),
        target,
    )
    if not records:
        return CheckResult(
            status="NO_TASK",
            target_date=target.isoformat(),
            should_dispatch=False,
            reason="target_date_has_no_complete_flight_task",
            task_fingerprint=fingerprint,
            task_count=0,
        )

    state, source = _preparation_state(repo, target)
    if not state:
        return CheckResult(
            status="DISPATCH",
            target_date=target.isoformat(),
            should_dispatch=True,
            reason="preparation_state_missing",
            task_fingerprint=fingerprint,
            task_count=len(records),
        )
    if state.get("status") != "SUCCESS":
        return CheckResult(
            status="DISPATCH",
            target_date=target.isoformat(),
            should_dispatch=True,
            reason="previous_status_not_success",
            task_fingerprint=fingerprint,
            task_count=len(records),
            state_source=source,
        )

    stored_fingerprint = str(state.get("task_fingerprint", "")).strip()
    if not stored_fingerprint:
        stored_fingerprint = task_fingerprint_from_metadata(
            state.get("matched_flights"),
            target,
        )
    if stored_fingerprint != fingerprint:
        return CheckResult(
            status="DISPATCH",
            target_date=target.isoformat(),
            should_dispatch=True,
            reason="task_fingerprint_changed",
            task_fingerprint=fingerprint,
            task_count=len(records),
            state_source=source,
        )

    output = repo / "flight_preparation" / f"{target.isoformat()}_航前准备.txt"
    if not output.exists():
        return CheckResult(
            status="DISPATCH",
            target_date=target.isoformat(),
            should_dispatch=True,
            reason="preparation_output_missing",
            task_fingerprint=fingerprint,
            task_count=len(records),
            state_source=source,
        )
    return CheckResult(
        status="NO_ACTION",
        target_date=target.isoformat(),
        should_dispatch=False,
        reason="successful_preparation_matches_current_tasks",
        task_fingerprint=fingerprint,
        task_count=len(records),
        state_source=source,
    )


def dispatch_flight_preparation(
    repository: str,
    token: str,
    target: date,
    days_ahead: int,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("GITHUB_REPOSITORY is invalid")
    if not token.strip():
        raise ValueError("GITHUB_TOKEN is required")
    payload = json.dumps(
        {
            "ref": "main",
            "inputs": {
                "target_date": target.isoformat(),
                "days_ahead": str(days_ahead),
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        (
            f"https://api.github.com/repos/{repository}/actions/workflows/"
            f"{WORKFLOW_FILE}/dispatches"
        ),
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "crew-calendar-flight-prep-scheduler",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request, timeout=45) as response:
            status = int(getattr(response, "status", 0))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"workflow dispatch returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as exc:
        raise RuntimeError(
            f"workflow dispatch transport failed: {type(exc).__name__}"
        ) from None
    if status != 204:
        raise RuntimeError(f"workflow dispatch returned HTTP {status}")


def _write_github_output(path: str, result: CheckResult) -> None:
    if not path:
        return
    values = {
        "status": result.status,
        "target_date": result.target_date,
        "should_dispatch": str(result.should_dispatch).lower(),
        "reason": result.reason,
        "task_fingerprint": result.task_fingerprint,
    }
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--days-ahead", type=int, choices=(1, 2), required=True)
    parser.add_argument("--target-date", default="")
    parser.add_argument("--github-output", default="")
    parser.add_argument("--dispatch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    target = (
        date.fromisoformat(args.target_date)
        if args.target_date
        else target_date_for_days_ahead(args.days_ahead)
    )
    result = evaluate_preparation(repo, target)
    print(f"FLIGHT_PREP_CHECK={result.status}")
    print(f"FLIGHT_PREP_TARGET_DATE={result.target_date}")
    print(f"FLIGHT_PREP_CHECK_REASON={result.reason}")
    print(f"FLIGHT_PREP_TASK_COUNT={result.task_count}")
    _write_github_output(args.github_output, result)

    if args.dispatch and result.should_dispatch:
        dispatch_flight_preparation(
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_TOKEN", ""),
            target,
            args.days_ahead,
        )
        print("FLIGHT_PREP_DISPATCH=REQUESTED")
    else:
        print(f"FLIGHT_PREP_DISPATCH={result.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
