"""Publish the shared Flighty future bodies as a minimal, credential-free ICS."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import sync_flighty_google_calendar as flighty

ROOT = Path(__file__).resolve().parent


def escape_text(value: str) -> str:
    """RFC 5545 TEXT escaping, without allowing injected content lines."""
    if any(ord(char) < 32 and char not in "\t\r\n" for char in value):
        raise ValueError("Unsupported control character in calendar text")
    return (value.replace("\\", "\\\\").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "\\n")
            .replace(";", "\\;").replace(",", "\\,"))


def fold_line(line: str) -> str:
    """Fold at 75 UTF-8 octets, including each continuation's leading space."""
    parts, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += width
    parts.append(current)
    return "\r\n".join(parts)


def render_calendar(snapshot: flighty.Snapshot) -> bytes:
    # Selection and date boundary belong exclusively to the shared builder.
    selected = [f for f in snapshot.flights.values()
                if flighty.private(f.body).get("flighty_source_key") in snapshot.future_sources]
    keys = [flighty.private(f.body)["flighty_source_key"] for f in selected]
    if len(keys) != len(set(keys)) or set(keys) != set(snapshot.future_sources):
        raise ValueError("Incomplete or duplicate future source bodies")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//Crew Calendar//Flighty Subscription//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:Flighty Flights", "X-WR-TIMEZONE:Asia/Shanghai",
        # Future-only Beijing events use standard time; include the timezone
        # component required for the TZID parameters, also for Apple clients.
        "BEGIN:VTIMEZONE", "TZID:Asia/Shanghai", "BEGIN:STANDARD",
        "DTSTART:20000101T000000", "TZOFFSETFROM:+0800", "TZOFFSETTO:+0800",
        "TZNAME:CST", "END:STANDARD", "END:VTIMEZONE",
    ]
    stamp = snapshot.as_of.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for flight in sorted(selected, key=lambda f: (f.body["start"]["dateTime"], flighty.private(f.body)["flighty_source_key"])):
        body = flight.body
        source_key = flighty.private(body)["flighty_source_key"]
        start = datetime.fromisoformat(body["start"]["dateTime"]).astimezone(flighty.BEIJING)
        end = datetime.fromisoformat(body["end"]["dateTime"]).astimezone(flighty.BEIJING)
        lines.extend([
            "BEGIN:VEVENT", f"UID:{source_key}@crew-calendar-flighty",
            f"DTSTAMP:{stamp}", f"SUMMARY:{escape_text(body['summary'])}",
            f"DTSTART;TZID=Asia/Shanghai:{start:%Y%m%dT%H%M%S}",
            f"DTEND;TZID=Asia/Shanghai:{end:%Y%m%dT%H%M%S}",
            f"LOCATION:{escape_text(body['location'])}",
            f"DESCRIPTION:{escape_text(body['description'])}", "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode("utf-8")


def generate(root: Path, *, now: datetime | None = None) -> int:
    snapshot = flighty.read_snapshot(root / "crew_schedule.ics", flighty.Airports.load(root),
                                    now=now, historical_path=root / "flight.ics")
    content = render_calendar(snapshot)  # Complete serialization before touching last-good.
    target = root / "flighty.ics"
    temporary = root / "flighty.ics.tmp"
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return len(snapshot.future_sources)


def main() -> int:
    try:
        count = generate(ROOT)
    except Exception as exc:
        # Never log source bodies, paths containing credentials, or raw errors.
        print(f"::warning title=Flighty subscription::FLIGHTY_SUBSCRIPTION=ERROR {type(exc).__name__}; last-good preserved")
        return 1
    print(f"FLIGHTY_SUBSCRIPTION=SUCCESS events={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
