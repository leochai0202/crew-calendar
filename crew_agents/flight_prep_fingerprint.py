from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from crew_agents.ics_utils import BEIJING, CalendarEvent


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalized_people(values: object) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    return sorted(
        {
            person
            for item in values
            if (person := _normalized_text(item))
        }
    )


def _normalized_datetime(value: datetime | str) -> str:
    if isinstance(value, datetime):
        moment = value
    else:
        moment = datetime.fromisoformat(str(value))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=BEIJING)
    return moment.astimezone(BEIJING).replace(microsecond=0).isoformat()


def task_records_from_events(
    events: Iterable[CalendarEvent],
    target: date,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for event in events:
        if event.start.astimezone(BEIJING).date() != target:
            continue
        if not event.is_flight or event.is_positioning:
            continue
        departure, arrival = event.route
        if not event.flight_number or not departure or not arrival:
            continue
        records.append(
            {
                "flight_number": _normalized_text(event.flight_number).upper(),
                "departure": _normalized_text(departure),
                "arrival": _normalized_text(arrival),
                "start": _normalized_datetime(event.start),
                "end": _normalized_datetime(event.end),
                "task_type": "flight",
                "people": _normalized_people(event.people),
            }
        )
    return sorted(
        records,
        key=lambda item: (
            item["start"],
            item["end"],
            item["flight_number"],
            item["departure"],
            item["arrival"],
        ),
    )


def task_records_from_metadata(
    matched_flights: object,
    target: date,
) -> list[dict[str, Any]]:
    if not isinstance(matched_flights, list):
        return []
    records: list[dict[str, Any]] = []
    for item in matched_flights:
        if not isinstance(item, Mapping):
            continue
        try:
            start = _normalized_datetime(item.get("start", ""))
            end = _normalized_datetime(item.get("end", ""))
            if datetime.fromisoformat(start).date() != target:
                continue
        except (TypeError, ValueError):
            continue
        flight_number = _normalized_text(item.get("flight_number", "")).upper()
        departure = _normalized_text(item.get("departure", ""))
        arrival = _normalized_text(item.get("arrival", ""))
        if not flight_number or not departure or not arrival:
            continue
        records.append(
            {
                "flight_number": flight_number,
                "departure": departure,
                "arrival": arrival,
                "start": start,
                "end": end,
                "task_type": _normalized_text(item.get("task_type", "flight"))
                or "flight",
                "people": _normalized_people(item.get("people", [])),
            }
        )
    return sorted(
        records,
        key=lambda item: (
            item["start"],
            item["end"],
            item["flight_number"],
            item["departure"],
            item["arrival"],
        ),
    )


def task_fingerprint(target: date, records: list[dict[str, Any]]) -> str:
    payload = {
        "target_date": target.isoformat(),
        "tasks": records,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def task_fingerprint_from_events(
    events: Iterable[CalendarEvent],
    target: date,
) -> tuple[str, list[dict[str, Any]]]:
    records = task_records_from_events(events, target)
    return task_fingerprint(target, records), records


def task_fingerprint_from_metadata(
    matched_flights: object,
    target: date,
) -> str:
    return task_fingerprint(
        target,
        task_records_from_metadata(matched_flights, target),
    )
