from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crew_agents.common import atomic_write_json
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
    state_changed: bool = False
    state_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleTiming:
    scheduled_cron: str
    slot_utc: datetime
    slot_beijing: datetime
    actual_start_utc: datetime
    actual_start_beijing: datetime
    delay_minutes: int
    target_date: date


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


def scheduled_target_timing(
    days_ahead: int,
    scheduled_cron: str,
    *,
    actual_start_utc: datetime | None = None,
) -> ScheduleTiming:
    if days_ahead not in (1, 2):
        raise ValueError("days_ahead must be 1 or 2")
    match = re.fullmatch(
        r"\s*(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*\s*",
        scheduled_cron,
    )
    if not match:
        raise ValueError("scheduled_cron must be a daily five-field cron")
    minute, hour = (int(value) for value in match.groups())
    if not 0 <= minute <= 59 or not 0 <= hour <= 23:
        raise ValueError("scheduled_cron hour or minute is out of range")

    actual = actual_start_utc or datetime.now(timezone.utc)
    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=timezone.utc)
    actual = actual.astimezone(timezone.utc)
    slot = actual.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if slot > actual:
        slot -= timedelta(days=1)
    slot_beijing = slot.astimezone(BEIJING)
    return ScheduleTiming(
        scheduled_cron=scheduled_cron.strip(),
        slot_utc=slot,
        slot_beijing=slot_beijing,
        actual_start_utc=actual,
        actual_start_beijing=actual.astimezone(BEIJING),
        delay_minutes=int((actual - slot).total_seconds() // 60),
        target_date=slot_beijing.date() + timedelta(days=days_ahead),
    )


def parse_utc_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _invalidated_metadata(
    existing: dict,
    target: date,
    current_fingerprint: str,
) -> dict:
    invalidated = dict(existing)
    previous_matched_flights = invalidated.get("matched_flights")
    previous_fingerprint = str(invalidated.get("task_fingerprint", "")).strip()
    invalidated.update(
        {
            "status": "INVALIDATED_NO_TASK",
            "target_date": target.isoformat(),
            "task_fingerprint": current_fingerprint,
            "matched_flights": [],
            "invalidated_at_beijing": datetime.now(BEIJING).isoformat(),
            "invalidation_reason": "target_date_has_no_complete_flight_task",
        }
    )
    if previous_fingerprint:
        invalidated["previous_task_fingerprint"] = previous_fingerprint
    if isinstance(previous_matched_flights, list) and previous_matched_flights:
        invalidated["previous_matched_flights"] = previous_matched_flights
    return invalidated


def _invalidate_no_task_preparation(
    repo: Path,
    target: date,
    state: dict,
    current_fingerprint: str,
) -> tuple[str, ...]:
    output_dir = repo / "flight_preparation"
    dated_path = output_dir / f"{target.isoformat()}_meta.json"
    dated_existing = _load_json(dated_path) or state
    atomic_write_json(
        dated_path,
        _invalidated_metadata(dated_existing, target, current_fingerprint),
    )
    changed = [dated_path.relative_to(repo).as_posix()]

    latest_path = output_dir / "latest_meta.json"
    latest = _load_json(latest_path)
    if latest.get("target_date") == target.isoformat():
        atomic_write_json(
            latest_path,
            _invalidated_metadata(latest, target, current_fingerprint),
        )
        changed.append(latest_path.relative_to(repo).as_posix())
    return tuple(changed)


def evaluate_preparation(
    repo: Path,
    target: date,
    *,
    existing_only: bool = False,
) -> CheckResult:
    fingerprint, records = task_fingerprint_from_events(
        parse_ics(repo / "flight.ics"),
        target,
    )
    if not records:
        state, source = _preparation_state(repo, target)
        output = repo / "flight_preparation" / f"{target.isoformat()}_航前准备.txt"
        already_invalid = state.get("status") in {
            "NO_TASK",
            "INVALIDATED_NO_TASK",
        }
        if not already_invalid and (
            state.get("status") == "SUCCESS" or output.exists()
        ):
            state_files = _invalidate_no_task_preparation(
                repo,
                target,
                state,
                fingerprint,
            )
            return CheckResult(
                status="INVALIDATED_NO_TASK",
                target_date=target.isoformat(),
                should_dispatch=True,
                reason="previous_preparation_invalidated_after_task_removal",
                task_fingerprint=fingerprint,
                task_count=0,
                state_source=source,
                state_changed=True,
                state_files=state_files,
            )
        return CheckResult(
            status="NO_TASK",
            target_date=target.isoformat(),
            should_dispatch=False,
            reason="target_date_has_no_complete_flight_task",
            task_fingerprint=fingerprint,
            task_count=0,
        )

    state, source = _preparation_state(repo, target)
    output = repo / "flight_preparation" / f"{target.isoformat()}_航前准备.txt"
    if existing_only and not state and not output.exists():
        return CheckResult(
            status="NO_ACTION",
            target_date=target.isoformat(),
            should_dispatch=False,
            reason="existing_preparation_missing",
            task_fingerprint=fingerprint,
            task_count=len(records),
        )
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
        "state_changed": str(result.state_changed).lower(),
        "state_files": ";".join(result.state_files),
    }
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--days-ahead", type=int, choices=(1, 2), required=True)
    parser.add_argument("--target-date", default="")
    parser.add_argument("--scheduled-cron", default="")
    parser.add_argument("--actual-start-utc", default="")
    parser.add_argument("--existing-only", action="store_true")
    parser.add_argument("--github-output", default="")
    parser.add_argument("--dispatch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    actual_start = (
        parse_utc_datetime(args.actual_start_utc)
        if args.actual_start_utc
        else datetime.now(timezone.utc)
    )
    timing: ScheduleTiming | None = None
    if args.target_date:
        target = date.fromisoformat(args.target_date)
    elif args.scheduled_cron:
        timing = scheduled_target_timing(
            args.days_ahead,
            args.scheduled_cron,
            actual_start_utc=actual_start,
        )
        target = timing.target_date
    else:
        target = target_date_for_days_ahead(
            args.days_ahead,
            now=actual_start,
        )
    print(f"SCHEDULE_CRON={args.scheduled_cron or 'MANUAL'}")
    print(f"ACTUAL_START_UTC={actual_start.isoformat()}")
    print(f"ACTUAL_START_BEIJING={actual_start.astimezone(BEIJING).isoformat()}")
    if timing is not None:
        print(f"SCHEDULE_SLOT_UTC={timing.slot_utc.isoformat()}")
        print(f"SCHEDULE_SLOT_BEIJING={timing.slot_beijing.isoformat()}")
        print(f"SCHEDULE_DELAY_MINUTES={timing.delay_minutes}")
    else:
        print("SCHEDULE_SLOT_UTC=MANUAL")
        print("SCHEDULE_SLOT_BEIJING=MANUAL")
        print("SCHEDULE_DELAY_MINUTES=MANUAL")
    print(f"TARGET_DATE={target.isoformat()}")
    result = evaluate_preparation(
        repo,
        target,
        existing_only=args.existing_only,
    )
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
