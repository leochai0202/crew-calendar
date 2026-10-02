from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from crew_agents.flight_prep_fingerprint import task_fingerprint_from_events
from crew_agents.ics_utils import CalendarEvent, parse_ics
from scripts.check_flight_prep_schedule import (
    dispatch_flight_preparation,
    evaluate_preparation,
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


def test_removed_flights_invalidate_previous_success(tmp_path: Path) -> None:
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    _write_ics(repo / "flight.ics", [])

    result = evaluate_preparation(repo, TARGET)

    assert result.status == "INVALIDATED_NO_TASK"
    assert result.should_dispatch is False
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
    assert repeated.state_changed is False


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
