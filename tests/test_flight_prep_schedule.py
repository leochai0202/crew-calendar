from __future__ import annotations

import json
from argparse import Namespace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.flight_prep_fingerprint import task_fingerprint_from_events
from crew_agents.ics_utils import CalendarEvent, parse_ics
from scripts import check_flight_prep_schedule as checker
from scripts.check_flight_prep_schedule import (
    dispatch_flight_preparation,
    evaluate_preparation,
    scheduled_target_timing,
    target_date_for_days_ahead,
)


BEIJING = ZoneInfo("Asia/Shanghai")
TARGET = date(2026, 10, 3)


def _event(
    *,
    flight_number: str = "9C1234",
    departure: str = "上海浦东",
    arrival: str = "深圳宝安",
    start: datetime | None = None,
    people: tuple[str, ...] = ("段洋硕 (B)", "CAPTAIN TEST"),
    uid: str = "event-1",
    registration: str = "B-1234",
    checkin: str = "07:30",
) -> CalendarEvent:
    start = start or datetime(2026, 10, 3, 9, 0, tzinfo=BEIJING)
    people_text = "\n".join(f"• {person}" for person in people)
    return CalendarEvent(
        uid=uid,
        summary=f"✈️ {flight_number} {departure}→{arrival}",
        start=start,
        end=start + timedelta(hours=2),
        description=(
            f"类型：航班\n航班：{flight_number}\n"
            f"航线：{departure} → {arrival}\n"
            f"签到：{checkin}\n注册号：{registration}\n"
            f"人员名单：\n{people_text}"
        ),
        location=departure,
        properties={"X-UNRELATED": "metadata"},
        source_file="flight.ics",
    )


def _write_ics(path: Path, events: list[CalendarEvent]) -> None:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for event in events:
        description = event.description.replace("\\", "\\\\").replace("\n", "\\n")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event.uid}",
                f"DTSTART;TZID=Asia/Shanghai:{event.start:%Y%m%dT%H%M%S}",
                f"DTEND;TZID=Asia/Shanghai:{event.end:%Y%m%dT%H%M%S}",
                f"SUMMARY:{event.summary}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{event.location}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _repo_with_event(tmp_path: Path, event: CalendarEvent | None = None) -> Path:
    repo = tmp_path / "repo"
    (repo / "flight_preparation").mkdir(parents=True)
    _write_ics(repo / "flight.ics", [event or _event()])
    return repo


def _write_success_state(repo: Path) -> str:
    events = parse_ics(repo / "flight.ics")
    fingerprint, _ = task_fingerprint_from_events(events, TARGET)
    state = {
        "status": "SUCCESS",
        "target_date": TARGET.isoformat(),
        "task_fingerprint": fingerprint,
        "matched_flights": [event.to_dict() for event in events],
        "generated_at_beijing": "2026-10-01T22:00:00+08:00",
    }
    (repo / "flight_preparation" / f"{TARGET.isoformat()}_meta.json").write_text(
        json.dumps(state, ensure_ascii=False),
        encoding="utf-8",
    )
    (repo / "flight_preparation" / "latest_meta.json").write_text(
        json.dumps(state, ensure_ascii=False),
        encoding="utf-8",
    )
    (repo / "flight_preparation" / f"{TARGET.isoformat()}_航前准备.txt").write_text(
        "source-grounded preparation\n",
        encoding="utf-8",
    )
    return fingerprint


def test_d2_and_d1_target_dates_use_beijing_calendar_days() -> None:
    now = datetime(2026, 10, 1, 22, 0, tzinfo=BEIJING)
    assert target_date_for_days_ahead(2, now=now) == date(2026, 10, 3)
    assert target_date_for_days_ahead(1, now=now) == date(2026, 10, 2)


def test_delayed_calendar_slot_uses_planned_beijing_date_across_midnight() -> None:
    actual = datetime(2026, 10, 2, 18, 15, tzinfo=timezone.utc)

    d1 = scheduled_target_timing(1, "27 13 * * *", actual_start_utc=actual)
    d2 = scheduled_target_timing(2, "27 13 * * *", actual_start_utc=actual)

    assert d1.slot_beijing == datetime(2026, 10, 2, 21, 27, tzinfo=BEIJING)
    assert d1.actual_start_beijing == datetime(2026, 10, 3, 2, 15, tzinfo=BEIJING)
    assert d1.target_date == date(2026, 10, 3)
    assert d2.target_date == date(2026, 10, 4)
    assert d1.delay_minutes == 288


def test_delayed_0637_d2_slot_keeps_its_planned_beijing_date() -> None:
    actual = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)

    timing = scheduled_target_timing(2, "37 22 * * *", actual_start_utc=actual)

    assert timing.slot_utc == datetime(2026, 10, 2, 22, 37, tzinfo=timezone.utc)
    assert timing.slot_beijing == datetime(2026, 10, 3, 6, 37, tzinfo=BEIJING)
    assert timing.target_date == date(2026, 10, 5)


def test_existing_success_with_same_fingerprint_is_no_action(tmp_path: Path) -> None:
    repo = _repo_with_event(tmp_path)
    fingerprint = _write_success_state(repo)

    result = evaluate_preparation(repo, TARGET)

    assert result.status == "NO_ACTION"
    assert result.should_dispatch is False
    assert result.task_fingerprint == fingerprint


def test_missing_preparation_dispatches(tmp_path: Path) -> None:
    result = evaluate_preparation(_repo_with_event(tmp_path), TARGET)

    assert result.status == "DISPATCH"
    assert result.should_dispatch is True
    assert result.reason == "preparation_state_missing"


def test_calendar_existing_only_does_not_create_first_preparation(tmp_path: Path) -> None:
    result = evaluate_preparation(
        _repo_with_event(tmp_path),
        TARGET,
        existing_only=True,
    )

    assert result.status == "NO_ACTION"
    assert result.should_dispatch is False
    assert result.reason == "existing_preparation_missing"


def test_calendar_existing_only_dispatches_changed_existing_preparation(
    tmp_path: Path,
) -> None:
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    _write_ics(repo / "flight.ics", [_event(flight_number="9C5678")])

    result = evaluate_preparation(repo, TARGET, existing_only=True)

    assert result.status == "DISPATCH"
    assert result.reason == "task_fingerprint_changed"


def test_failed_preparation_dispatches(tmp_path: Path) -> None:
    repo = _repo_with_event(tmp_path)
    (repo / "flight_preparation" / f"{TARGET.isoformat()}_meta.json").write_text(
        json.dumps({"status": "FAILED_SAFE", "target_date": TARGET.isoformat()}),
        encoding="utf-8",
    )

    result = evaluate_preparation(repo, TARGET)

    assert result.should_dispatch is True
    assert result.reason == "previous_status_not_success"


def test_task_change_dispatches(tmp_path: Path) -> None:
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    _write_ics(repo / "flight.ics", [_event(flight_number="9C5678")])

    result = evaluate_preparation(repo, TARGET)

    assert result.should_dispatch is True
    assert result.reason == "task_fingerprint_changed"


def test_irrelevant_metadata_does_not_change_fingerprint() -> None:
    original = _event(uid="old", registration="B-1111", checkin="07:30")
    refreshed = _event(uid="new", registration="B-9999", checkin="08:00")
    refreshed.properties["X-REFRESHED"] = "different"
    refreshed.source_file = "refreshed.ics"

    original_fingerprint, _ = task_fingerprint_from_events([original], TARGET)
    refreshed_fingerprint, _ = task_fingerprint_from_events([refreshed], TARGET)

    assert original_fingerprint == refreshed_fingerprint


@pytest.mark.parametrize(
    "changed",
    [
        {"flight_number": "9C5678"},
        {"departure": "上海虹桥"},
        {"arrival": "曼谷素旺那普"},
        {"start": datetime(2026, 10, 3, 10, 0, tzinfo=BEIJING)},
        {"people": ("段洋硕 (B)", "OTHER FOREIGN CREW")},
    ],
)
def test_operational_task_fields_change_fingerprint(changed: dict) -> None:
    baseline, _ = task_fingerprint_from_events([_event()], TARGET)
    updated, _ = task_fingerprint_from_events([_event(**changed)], TARGET)

    assert updated != baseline


def test_no_valid_task_does_not_dispatch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "flight_preparation").mkdir(parents=True)
    _write_ics(repo / "flight.ics", [])

    result = evaluate_preparation(repo, TARGET)

    assert result.status == "NO_TASK"
    assert result.should_dispatch is False
    assert result.state_changed is False


def test_later_d2_check_dispatches_when_task_appears_after_no_task(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "flight_preparation").mkdir(parents=True)
    _write_ics(repo / "flight.ics", [])
    assert evaluate_preparation(repo, TARGET).status == "NO_TASK"

    _write_ics(repo / "flight.ics", [_event()])
    later = evaluate_preparation(repo, TARGET)

    assert later.status == "DISPATCH"
    assert later.reason == "preparation_state_missing"


def test_removed_flights_invalidate_previous_success(tmp_path: Path) -> None:
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    _write_ics(repo / "flight.ics", [])

    result = evaluate_preparation(repo, TARGET)

    assert result.status == "INVALIDATED_NO_TASK"
    assert result.should_dispatch is True
    assert result.state_changed is True
    assert set(result.state_files) == {
        "flight_preparation/2026-10-03_meta.json",
        "flight_preparation/latest_meta.json",
    }
    for name in ("2026-10-03_meta.json", "latest_meta.json"):
        metadata = json.loads(
            (repo / "flight_preparation" / name).read_text(encoding="utf-8")
        )
        assert metadata["status"] == "INVALIDATED_NO_TASK"
        assert metadata["matched_flights"] == []
        assert metadata["previous_matched_flights"]
    assert (
        repo / "flight_preparation" / "2026-10-03_航前准备.txt"
    ).exists()

    repeated = evaluate_preparation(repo, TARGET)
    assert repeated.status == "NO_TASK"
    assert repeated.should_dispatch is False
    assert repeated.state_changed is False


def test_removed_flights_dispatch_visible_no_task_run_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    _write_ics(repo / "flight.ics", [])
    dispatches: list[date] = []

    monkeypatch.setattr(
        checker,
        "parse_args",
        lambda: Namespace(
            repo=str(repo),
            days_ahead=1,
            target_date=TARGET.isoformat(),
            scheduled_cron="",
            actual_start_utc="",
            existing_only=False,
            github_output="",
            dispatch=True,
        ),
    )
    monkeypatch.setattr(
        checker,
        "dispatch_flight_preparation",
        lambda _repository, _token, target, _days_ahead: dispatches.append(target),
    )

    assert checker.main() == 0
    assert checker.main() == 0
    assert dispatches == [TARGET]


def test_no_task_workflow_keeps_existing_text_without_success_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "agent-repo"
    output_dir = repo / "flight_preparation"
    output_dir.mkdir(parents=True)
    _write_ics(repo / "flight.ics", [])
    existing_output = output_dir / f"{TARGET.isoformat()}_航前准备.txt"
    existing_output.write_text("previous valid preparation\n", encoding="utf-8")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(
        agent,
        "parse_args",
        lambda: Namespace(
            repo=str(repo),
            target_date=TARGET.isoformat(),
            days_ahead=1,
            flight_number="",
            departure="",
            arrival="",
            generate_english="auto",
        ),
    )

    assert agent.main() == 0

    metadata = json.loads(
        (output_dir / f"{TARGET.isoformat()}_meta.json").read_text(encoding="utf-8")
    )
    assert metadata["status"] == "NO_TASK"
    assert existing_output.read_text(encoding="utf-8") == "previous valid preparation\n"
    assert not (output_dir / ".success").exists()


def test_flight_restoration_after_invalidation_dispatches(tmp_path: Path) -> None:
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    _write_ics(repo / "flight.ics", [])
    assert evaluate_preparation(repo, TARGET).status == "INVALIDATED_NO_TASK"

    _write_ics(repo / "flight.ics", [_event()])
    restored = evaluate_preparation(repo, TARGET)

    assert restored.status == "DISPATCH"
    assert restored.should_dispatch is True
    assert restored.reason == "previous_status_not_success"


def test_legacy_latest_meta_fingerprint_is_compatible(tmp_path: Path) -> None:
    repo = _repo_with_event(tmp_path)
    events = parse_ics(repo / "flight.ics")
    (repo / "flight_preparation" / "latest_meta.json").write_text(
        json.dumps(
            {
                "status": "SUCCESS",
                "target_date": TARGET.isoformat(),
                "matched_flights": [event.to_dict() for event in events],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (repo / "flight_preparation" / f"{TARGET.isoformat()}_航前准备.txt").write_text(
        "existing\n",
        encoding="utf-8",
    )

    result = evaluate_preparation(repo, TARGET)

    assert result.status == "NO_ACTION"
    assert result.state_source == "latest_meta.json"


def test_dispatch_payload_explicitly_contains_target_date() -> None:
    captured: dict[str, object] = {}

    class Response:
        status = 204

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def opener(request: object, *, timeout: int) -> Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    dispatch_flight_preparation(
        "owner/repository",
        "test-token",
        TARGET,
        2,
        opener=opener,
    )

    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload == {
        "ref": "main",
        "inputs": {"target_date": "2026-10-03", "days_ahead": "2"},
    }
    assert captured["timeout"] == 45
