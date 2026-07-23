from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")


class FlightSelectionError(ValueError):
    """Raised when one exact flight event cannot be selected safely."""


class AmbiguousFlightSelectionError(FlightSelectionError):
    """Raised when more than one event satisfies the requested flight identity."""


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    start: datetime
    end: datetime
    description: str
    location: str
    properties: dict[str, str]
    source_file: str = ""

    @property
    def is_flight(self) -> bool:
        return "✈" in self.summary or "类型：航班" in self.description or bool(self.flight_number)

    @property
    def is_positioning(self) -> bool:
        text = f"{self.summary}\n{self.description}"
        return "置位" in text

    @property
    def flight_number(self) -> str:
        m = re.search(r"\b9C\d{3,4}[A-Z]?\b", f"{self.summary}\n{self.description}")
        return m.group(0) if m else ""

    @property
    def route(self) -> tuple[str, str]:
        text = f"{self.summary}\n{self.description}"
        patterns = [
            r"航线[:：]\s*([^\n｜|]+?)\s*[→-]\s*([^\n｜|]+)",
            r"(?:✈️?\s*)?(?:9C\d{3,4}[A-Z]?\s+)?([^\n→]+?)\s*→\s*([^\n(]+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                dep = clean_airport_name(m.group(1))
                arr = clean_airport_name(m.group(2))
                if dep and arr:
                    return dep, arr
        return "", ""

    @property
    def aircraft_type(self) -> str:
        m = re.search(r"机型[:：]\s*([^\n｜|]+)", self.description)
        return m.group(1).strip() if m else ""

    @property
    def registration(self) -> str:
        m = re.search(r"注册号[:：]\s*([A-Z0-9-]+)", self.description)
        return m.group(1).strip() if m else ""

    @property
    def checkin(self) -> str:
        m = re.search(r"签到[:：]\s*([^\n]+)", self.description)
        return m.group(1).strip() if m else ""

    @property
    def people(self) -> list[str]:
        lines = self.description.splitlines()
        out: list[str] = []
        in_people = False
        for line in lines:
            s = line.strip()
            if s == "人员名单：":
                in_people = True
                continue
            if not in_people:
                continue
            if not s:
                if out:
                    break
                continue
            if s.startswith("版本：") or (s.endswith("：") and not s.startswith("•")):
                break
            if s.startswith("•"):
                s = s[1:].strip()
            if s:
                out.append(s)
        return out

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = self.start.isoformat()
        data["end"] = self.end.isoformat()
        data["flight_number"] = self.flight_number
        data["departure"], data["arrival"] = self.route
        data["aircraft_type"] = self.aircraft_type
        data["registration"] = self.registration
        data["checkin"] = self.checkin
        data["people"] = self.people
        data["cross_day"] = self.end.date() > self.start.date()
        return data


def clean_airport_name(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\(\+1\)|（\+1）", "", value)
    value = re.sub(r"^[✈️\s]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -｜|")


def unfold_ics(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    physical = text.split("\n")
    logical: list[str] = []
    for line in physical:
        if line.startswith((" ", "\t")) and logical:
            logical[-1] += line[1:]
        else:
            logical.append(line)
    return logical


def unescape_ics_text(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in ("n", "N"):
                out.append("\n")
                i += 2
                continue
            if nxt in ("\\", ";", ","):
                out.append(nxt)
                i += 2
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _parse_datetime(prop_name: str, value: str) -> datetime:
    tz = BEIJING
    tz_match = re.search(r"TZID=([^;:]+)", prop_name)
    if tz_match:
        try:
            tz = ZoneInfo(tz_match.group(1))
        except Exception:
            tz = BEIJING

    value = value.strip()
    if re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=tz)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(BEIJING)
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=tz).astimezone(BEIJING)
        except ValueError:
            pass
    raise ValueError(f"Unsupported ICS datetime: {prop_name}:{value}")


def parse_ics(path: str | Path) -> list[CalendarEvent]:
    p = Path(path)
    if not p.exists():
        return []
    lines = unfold_ics(p.read_text(encoding="utf-8", errors="replace"))
    events: list[CalendarEvent] = []
    current: list[str] | None = None
    alarm_depth = 0
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = []
            alarm_depth = 0
            continue
        if current is None:
            continue
        if line == "BEGIN:VALARM":
            alarm_depth += 1
            continue
        if line == "END:VALARM":
            alarm_depth = max(0, alarm_depth - 1)
            continue
        if line == "END:VEVENT":
            props: dict[str, str] = {}
            prop_names: dict[str, str] = {}
            for raw in current:
                if ":" not in raw:
                    continue
                name, value = raw.split(":", 1)
                base = name.split(";", 1)[0].upper()
                if base not in props:
                    props[base] = value
                    prop_names[base] = name
            try:
                start = _parse_datetime(prop_names.get("DTSTART", "DTSTART"), props["DTSTART"])
                end = _parse_datetime(prop_names.get("DTEND", "DTEND"), props.get("DTEND", props["DTSTART"]))
            except Exception:
                current = None
                continue
            events.append(
                CalendarEvent(
                    uid=props.get("UID", ""),
                    summary=unescape_ics_text(props.get("SUMMARY", "")),
                    start=start,
                    end=end,
                    description=unescape_ics_text(props.get("DESCRIPTION", "")),
                    location=unescape_ics_text(props.get("LOCATION", "")),
                    properties=props,
                    source_file=p.name,
                )
            )
            current = None
            continue
        if alarm_depth == 0:
            current.append(line)
    return events


def events_for_date(events: Iterable[CalendarEvent], target: date) -> list[CalendarEvent]:
    selected = [e for e in events if e.start.astimezone(BEIJING).date() == target]
    return sorted(selected, key=lambda e: e.start)


def normalize_flight_number(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def normalize_route_airport(value: str) -> str:
    return re.sub(r"\s+", "", clean_airport_name(value or ""))


def select_exact_flight_event(
    events: Iterable[CalendarEvent],
    target: date,
    *,
    flight_number: str = "",
    departure: str = "",
    arrival: str = "",
) -> CalendarEvent:
    """Select exactly one non-positioning flight without cross-event fallback.

    When selectors are supplied, all three identity fields are required and are
    matched together with the event date. With no selectors, the date itself
    must contain exactly one eligible flight; an ambiguous day is never reduced
    to the first event.
    """

    selectors = (flight_number.strip(), departure.strip(), arrival.strip())
    if any(selectors) and not all(selectors):
        raise FlightSelectionError("精确匹配必须同时提供航班号、起飞机场和落地机场")

    day_flights = [
        event
        for event in events_for_date(events, target)
        if event.is_flight and not event.is_positioning
    ]
    candidates = day_flights
    if all(selectors):
        expected_number = normalize_flight_number(flight_number)
        expected_departure = normalize_route_airport(departure)
        expected_arrival = normalize_route_airport(arrival)
        candidates = []
        for event in day_flights:
            event_departure, event_arrival = event.route
            if (
                normalize_flight_number(event.flight_number) == expected_number
                and normalize_route_airport(event_departure) == expected_departure
                and normalize_route_airport(event_arrival) == expected_arrival
            ):
                candidates.append(event)

    if not candidates:
        requested = (
            f"{target.isoformat()} {flight_number} {departure}→{arrival}".strip()
            if all(selectors)
            else target.isoformat()
        )
        raise FlightSelectionError(f"未找到唯一对应的航班事件：{requested}")
    if len(candidates) > 1:
        identities = [
            f"{event.uid or '<no-uid>'}:{event.flight_number} "
            f"{event.route[0]}→{event.route[1]} {event.start.isoformat()}"
            for event in candidates
        ]
        raise AmbiguousFlightSelectionError(
            "航班事件存在多个候选，拒绝默认选择第一个：" + " | ".join(identities)
        )

    selected = candidates[0]
    selected_departure, selected_arrival = selected.route
    if (
        selected.start.astimezone(BEIJING).date() != target
        or not selected.flight_number
        or not selected_departure
        or not selected_arrival
    ):
        raise FlightSelectionError("候选事件缺少日期、航班号或完整航线，无法安全匹配")
    return selected


CREW_ROLE_SUFFIX_RE = re.compile(
    r"\s*[\(（][A-Za-z0-9,\s/、+\-]+[\)）]\s*$"
)


def strip_crew_role_markers(value: str) -> str:
    name = (value or "").strip()
    while True:
        stripped = CREW_ROLE_SUFFIX_RE.sub("", name).strip()
        if stripped == name:
            return name
        name = stripped


def has_latin_crew_name(value: str) -> bool:
    return bool(re.search(r"[A-Za-z]", strip_crew_role_markers(value)))


def foreign_crew_names(event: CalendarEvent) -> list[str]:
    return [name for name in event.people if has_latin_crew_name(name)]


def extract_airport_mapping(main_py: str | Path) -> dict[str, str]:
    path = Path(main_py)
    if not path.exists():
        return {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "BASE_AIRPORT_CN_TO_ICAO":
                try:
                    value = ast.literal_eval(node.value)
                    if isinstance(value, dict):
                        return {str(k): str(v) for k, v in value.items()}
                except Exception:
                    return {}
    return {}


def resolve_icao(airport_name: str, mapping: dict[str, str]) -> str:
    airport_name = clean_airport_name(airport_name)
    if airport_name in mapping:
        return mapping[airport_name]
    candidates = [(name, code) for name, code in mapping.items() if name and (name in airport_name or airport_name in name)]
    if not candidates:
        return ""
    candidates.sort(key=lambda item: len(item[0]), reverse=True)
    return candidates[0][1]


def update_airport_experience(
    events: Iterable[CalendarEvent],
    experience: dict,
    *,
    as_of: datetime,
    rolling_days: int = 90,
) -> tuple[dict, list[str]]:
    result = dict(experience or {})
    airports = dict(result.get("airports") or {})
    changes: list[str] = []
    cutoff = as_of.date() - timedelta(days=rolling_days)

    for event in sorted(events, key=lambda e: e.end):
        if not event.is_flight or event.is_positioning:
            continue
        if event.end > as_of:
            continue
        dep, arr = event.route
        operation_date = event.start.date().isoformat()
        for airport in (dep, arr):
            if not airport:
                continue
            old = airports.get(airport, {}).get("last_operated") if isinstance(airports.get(airport), dict) else None
            if not old or operation_date > old:
                airports[airport] = {
                    "last_operated": operation_date,
                    "source": "completed_schedule_event",
                    "flight_number": event.flight_number,
                }
                changes.append(f"{airport}: {old or '-'} -> {operation_date}")

    for airport in list(airports):
        value = airports[airport]
        try:
            last_date = date.fromisoformat(value.get("last_operated", ""))
        except Exception:
            continue
        value["within_90_days"] = last_date >= cutoff

    result["airports"] = airports
    result["rolling_days"] = rolling_days
    result["as_of"] = as_of.date().isoformat()
    result["note"] = "机场最近运行日期根据已结束的排班航班自动更新；经历时间、起落和最近操纵落地不自动更新。"
    return result, changes
