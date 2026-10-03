"""One-way, read-only flight.ics -> dedicated Google Calendar mirror.

Google-assigned event IDs and stable keys are persisted together in each
event's private extended properties. No state or credentials enter Git history.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from crew_agents.ics_utils import extract_airport_mapping, unfold_ics, unescape_ics_text

ROOT = Path(__file__).resolve().parent
BEIJING = ZoneInfo("Asia/Shanghai")
OWNER = "crew-calendar-flighty-v1"
REQUIRED_ENV = (
    "FLIGHTY_GOOGLE_CALENDAR_ID",
    "FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON",
)
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendars.readonly",
)
FLIGHT_RE = re.compile(r"9C\d{3,4}[A-Z]?")
EXCLUDED = re.compile(r"置位|摆渡|训练|考勤|待命|其他任务|调机|模拟机|positioning|ferry|training|standby", re.I)


class SyncError(RuntimeError):
    """Messages contain only fixed diagnostics, never server bodies or secrets."""


def warning(message: str) -> None:
    # Escape workflow command characters, including untrusted ICS fields.
    safe = str(message).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::warning title=Flighty sync::{safe}")


def airport_name(value: str) -> str:
    return re.sub(r"\(\+1\)|（\+1）", "", value).strip()


@dataclass
class Airports:
    names: dict[str, set[str]]
    codes: dict[str, dict[str, str]]

    @classmethod
    def load(cls, root: Path) -> Airports:
        # Read the existing scraper constant via AST, without importing login or
        # running rebuild_airport_indexes (which writes diagnostic files).
        base = extract_airport_mapping(root / "crew_calendar_main.py")
        if not base:
            raise SyncError("Existing airport mapping is unavailable")
        names: dict[str, set[str]] = defaultdict(set)

        def add(name: str, icao: str) -> None:
            if name.strip() and re.fullmatch(r"[A-Z]{4}", icao):
                names[name.strip()].add(icao)

        for name, icao in base.items():
            add(name, icao)
        csv_path = root / "airports.csv"
        if csv_path.exists():
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    for name in [row.get("cn_name", ""), *re.split(r"[|;；,，、]", row.get("aliases", ""))]:
                        add(name, row.get("icao", "").strip().upper())
        aliases = root / "airport_aliases.json"
        if aliases.exists():
            for icao, values in json.loads(aliases.read_text(encoding="utf-8")).items():
                if isinstance(values, list):
                    for name in values:
                        add(str(name), icao)
        data = json.loads((root / "config" / "airport_iata.json").read_text(encoding="utf-8"))
        codes = data["airports"]
        for icao, info in codes.items():
            if not re.fullmatch(r"[A-Z]{4}", icao) or not re.fullmatch(r"[A-Z]{3}", info["iata"]):
                raise SyncError("Invalid ICAO/IATA supplement")
        if len({v["iata"] for v in codes.values()}) != len(codes):
            raise SyncError("Ambiguous IATA supplement")
        return cls(dict(names), codes)

    def candidates(self, name: str) -> set[str]:
        name = airport_name(name)
        candidates = set(self.names.get(name, ()))
        if re.fullmatch(r"[A-Z]{4}", name) and (
            name in self.codes or any(name in codes for codes in self.names.values())
        ):
            candidates.add(name)
        if re.fullmatch(r"[A-Z]{3}", name):
            candidates.update(c for c, v in self.codes.items() if v["iata"] == name)
        return candidates

    def resolve(self, name: str) -> tuple[str, str]:
        candidates = self.candidates(name)
        if len(candidates) != 1:
            raise ValueError("Unknown or ambiguous airport")
        info = self.codes.get(next(iter(candidates)))
        if not info:
            raise ValueError("No verified IATA mapping")
        return info["iata"], info.get("city", info["iata"])

    def resolve_future(self, name: str) -> tuple[str, str, str]:
        try:
            code, city = self.resolve(name)
            return code, city, "iata"
        except ValueError:
            candidates = self.candidates(name)
            if len(candidates) == 1:
                code = next(iter(candidates))
                return code, code, "icao"
            # Preserve the source spelling, including any next-day annotation.
            # An ambiguous alias must not choose one of its possible airports.
            return name.strip(), name.strip(), "raw"


def parse_time(name: str, value: str) -> datetime:
    # This source always emits explicit Beijing time. Never silently infer a
    # timezone for a floating/all-day/unknown-TZ event.
    if value.endswith("Z") and name.upper() in {"DTSTART", "DTEND"}:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(BEIJING)
    if name not in {"DTSTART;TZID=Asia/Shanghai", "DTEND;TZID=Asia/Shanghai"}:
        raise SyncError("Source event must have an explicit supported timezone")
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=BEIJING)


def read_events(path: Path) -> list[dict[str, tuple[str, str]]]:
    """Strict structural validation before any remote write, including deletes."""
    lines = [line for line in unfold_ics(path.read_bytes().decode("utf-8-sig")) if line]
    if not lines or lines[0] != "BEGIN:VCALENDAR" or lines[-1] != "END:VCALENDAR":
        raise SyncError("Missing or incomplete VCALENDAR; refusing reconciliation")
    stack: list[str] = []
    events = []
    current = None
    for line in lines:
        if line.startswith("BEGIN:"):
            component = line[6:]
            expected = {"VCALENDAR": [], "VEVENT": ["VCALENDAR"], "VALARM": ["VCALENDAR", "VEVENT"]}
            if component not in expected or stack != expected[component]:
                raise SyncError("Unexpected ICS component; refusing reconciliation")
            stack.append(component)
            if component == "VEVENT":
                current = {}
        elif line.startswith("END:"):
            if not stack or stack.pop() != line[4:]:
                raise SyncError("Unbalanced ICS component")
            if line == "END:VEVENT":
                events.append(current)
                current = None
        elif stack == ["VCALENDAR", "VEVENT"]:
            if ":" not in line:
                raise SyncError("Invalid event property")
            name, value = line.split(":", 1)
            key = name.split(";", 1)[0].upper()
            if key in current:
                raise SyncError("Duplicate event property")
            current[key] = (name, value)
    if stack or sum(line == "BEGIN:VCALENDAR" for line in lines) != 1:
        raise SyncError("Incomplete ICS snapshot")
    return events


@dataclass(frozen=True)
class Flight:
    key: str
    service: str
    body: dict


def current_time() -> datetime:
    return datetime.now(BEIJING)


@dataclass
class Snapshot:
    flights: dict[str, Flight] = field(default_factory=dict)
    skipped: int = 0
    protected_services: set[str] = field(default_factory=set)
    as_of: datetime = field(default_factory=current_time)
    future_sources: dict[str, str] = field(default_factory=dict)
    future_airports: Counter = field(default_factory=Counter)


def read_snapshot(path: Path, airports: Airports, *, now: datetime | None = None) -> Snapshot:
    snapshot = Snapshot(as_of=now if now is not None else current_time())
    if snapshot.as_of.utcoffset() is None:
        raise SyncError("Future boundary must have an explicit timezone")
    conflicting_keys: set[str] = set()
    future_groups: dict[str, list[Flight]] = defaultdict(list)
    for props in read_events(path):
        def value(key: str) -> str:
            return unescape_ics_text(props.get(key, (key, ""))[1])

        summary, description = value("SUMMARY"), value("DESCRIPTION")
        types = re.findall(r"^类型[:：]\s*(.+?)\s*$", description, re.M)
        if types != ["航班"] or EXCLUDED.search(summary) or value("STATUS").upper() == "CANCELLED":
            snapshot.skipped += 1
            continue
        numbers = re.findall(r"^航班[:：]\s*(\S+)\s*$", description, re.M)
        if len(numbers) != 1 or not FLIGHT_RE.fullmatch(numbers[0]):
            raise SyncError("Flight has an invalid or ambiguous flight number")
        number = numbers[0]
        if re.findall(r"\b9C\d{3,4}[A-Z]?\b", summary) != [number]:
            raise SyncError("Flight number disagrees between summary and description")
        try:
            start = parse_time(*props["DTSTART"])
            end = parse_time(*props["DTEND"])
        except (KeyError, ValueError):
            raise SyncError("Invalid flight start/end; refusing reconciliation") from None
        if end <= start:
            raise SyncError("Flight end must be after start; source is not repaired")
        future = start >= snapshot.as_of
        service = f"{start.date().isoformat()}|{number}"
        routes = re.findall(r"^航线[:：]\s*(.+?)\s*$", description, re.M)
        try:
            if len(routes) != 1 or len(routes[0].split("→")) != 2:
                raise ValueError("Invalid route")
            origin, destination = (part.strip() for part in routes[0].split("→"))
            if not origin or not destination:
                raise ValueError("Missing airport")
            if future:
                dep, dep_city, dep_kind = airports.resolve_future(origin)
                arr, arr_city, arr_kind = airports.resolve_future(destination)
            else:
                dep, dep_city = airports.resolve(origin)
                arr, arr_city = airports.resolve(destination)
                if dep == arr:
                    raise ValueError("Ambiguous same-airport route")
        except ValueError:
            if future:
                # No reliable source route means an explicit failure, never a
                # successful run with an uncounted future flight.
                raise SyncError(f"FLIGHTY_FUTURE_SOURCE_INVALID {service}: missing or ambiguous source route") from None
            snapshot.skipped += 1
            snapshot.protected_services.add(service)
            warning(f"SKIP {service}: route has no unambiguous verified IATA mapping ({' / '.join(routes)})")
            continue
        key = hashlib.sha256(f"{service}|{dep}|{arr}".encode()).hexdigest()
        airport_lines = f"\nDeparture Airport: {dep}\nArrival Airport: {arr}" if future else ""
        body = {
            "summary": f"Spring Airlines {number} {dep} → {arr}",
            "location": dep,
            "description": f"Airline: Spring Airlines\nFlight: {number}\nFrom: {dep}\nTo: {arr}{airport_lines}\nRoute: {dep_city} → {arr_city}\nCrew",
            "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Shanghai"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Shanghai"},
            "reminders": {"useDefault": False, "overrides": []},
            "extendedProperties": {"private": {"flighty_owner": OWNER, "flighty_key": key, "flighty_service": service, "flighty_route": f"{dep}|{arr}"}},
        }
        flight = Flight(key, service, body)
        if future:
            # Include DTEND too, so equal departures with conflicting arrivals
            # remain independently traceable. No mapped code enters this hash.
            identity = [number, start.isoformat(), end.isoformat(), origin, destination]
            source_key = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
            body["extendedProperties"]["private"]["flighty_source_key"] = source_key
            if source_key in snapshot.future_sources:
                snapshot.skipped += 1  # Identical source copies are one flight.
                continue
            snapshot.future_sources[source_key] = f"{service}|{origin}→{destination}|{start.isoformat()}|{end.isoformat()}"
            category = "raw" if "raw" in (dep_kind, arr_kind) else "icao" if "icao" in (dep_kind, arr_kind) else "iata"
            snapshot.future_airports[category] += 1
            if category != "iata":
                warning(f"FLIGHTY_FUTURE_AIRPORT_FALLBACK {service}: {category} {dep} → {arr}")
            future_groups[key].append(flight)
            continue
        # Historical protection rules remain independent of future records.
        if key in conflicting_keys:
            snapshot.skipped += 1
            continue
        if key in snapshot.flights:
            if snapshot.flights[key].body != body:
                del snapshot.flights[key]
                conflicting_keys.add(key)
                snapshot.protected_services.add(service)
                snapshot.skipped += 2
                warning(f"SKIP {service}: conflicting source times for the same business key")
                continue
            snapshot.skipped += 1
        snapshot.flights[key] = flight
    for key, flights in future_groups.items():
        conflict = len(flights) > 1 or key in snapshot.flights or key in conflicting_keys
        if conflict:
            warning(f"FLIGHTY_FUTURE_SOURCE_CONFLICT {flights[0].service}: retaining {len(flights)} future source identities")
        for flight in flights:
            if conflict:
                source_key = private(flight.body)["flighty_source_key"]
                unique_key = hashlib.sha256(f"{key}|{source_key}".encode()).hexdigest()
                private(flight.body)["flighty_key"] = unique_key
                flight = replace(flight, key=unique_key)
            snapshot.flights[flight.key] = flight
    return snapshot


class GoogleCalendar:
    def __init__(self, config: dict[str, str], session=None):
        self.config = config
        self.session = session or requests.Session()
        self.token = ""
        calendar_id = config["FLIGHTY_GOOGLE_CALENDAR_ID"]
        if not calendar_id.endswith("@group.calendar.google.com"):
            raise SyncError("Configure the actual secondary calendar ID, never primary or its name")
        self.base = "https://www.googleapis.com/calendar/v3/calendars/" + quote(calendar_id, safe="")

    def request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self.session.request(method, url, timeout=(10, 45), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise SyncError("Google transport failure; no automatic write retry") from None
        if not 200 <= response.status_code < 300:
            # A repeated DELETE after a lost response is already complete.
            if method == "DELETE" and response.status_code in (404, 410):
                return {}
            raise SyncError(f"Google {method} failed with HTTP {response.status_code}")
        if response.status_code == 204:
            return {}
        try:
            result = response.json()
        except ValueError:
            raise SyncError("Google returned invalid JSON") from None
        if not isinstance(result, dict):
            raise SyncError("Google returned an unexpected response")
        return result

    def authenticate(self) -> None:
        # config contains the complete JSON read from the process environment.
        # No credential file is written, and parser/library errors are redacted.
        try:
            info = json.loads(self.config["FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON"])
            if not isinstance(info, dict) or info.get("type") != "service_account":
                raise ValueError("Expected service account JSON object")
        except (ValueError, TypeError, KeyError):
            raise SyncError("Invalid service account JSON") from None
        phase = "load_dependency"
        try:
            # Lazy imports keep unconfigured runs safe even before the runner
            # has installed the new dependency from requirements.txt.
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request

            phase = "load_credentials"
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=GOOGLE_SCOPES,
            )
            phase = "refresh_token"
            credentials.refresh(Request())
            self.token = credentials.token
        except Exception as exc:
            raise SyncError(
                "Service account credentials could not be refreshed "
                f"(stage={phase}, error_type={type(exc).__name__})"
            ) from None
        if not isinstance(self.token, str) or not self.token:
            raise SyncError("Service account refresh did not return an access token")

    def api(self, method: str, suffix: str = "", **kwargs) -> dict:
        return self.request(method, self.base + suffix, headers={"Authorization": f"Bearer {self.token}"}, **kwargs)

    def validate_calendar(self) -> None:
        calendar = self.api("GET")
        if calendar.get("id") != self.config["FLIGHTY_GOOGLE_CALENDAR_ID"] or calendar.get("summary") != "Flighty航班":
            raise SyncError("Configured ID must identify the dedicated Flighty航班 calendar")
        if calendar.get("timeZone") != "Asia/Shanghai":
            raise SyncError("Set the dedicated Google Calendar timezone to Asia/Shanghai")

    def list_owned(self) -> list[dict]:
        events, seen_pages = [], set()
        params = {"privateExtendedProperty": f"flighty_owner={OWNER}", "showDeleted": "false", "maxResults": 2500}
        while True:
            result = self.api("GET", "/events", params=dict(params))
            items = result.get("items", [])
            if not isinstance(items, list):
                raise SyncError("Invalid event listing; refusing reconciliation")
            events.extend(items)
            page = result.get("nextPageToken")
            if not page:
                return events
            if not isinstance(page, str) or page in seen_pages:
                raise SyncError("Invalid event pagination; refusing reconciliation")
            seen_pages.add(page)
            params["pageToken"] = page

    def create(self, body: dict) -> dict:
        # Do not supply an arbitrary ID. Server-generated ID and our private
        # stable key persist atomically, even if the response is lost.
        return self.api("POST", "/events", params={"sendUpdates": "none"}, json=body)

    def update(self, event_id: str, body: dict) -> dict:
        return self.api("PATCH", "/events/" + quote(event_id, safe=""), params={"sendUpdates": "none"}, json=body)

    def delete(self, event_id: str) -> dict:
        return self.api("DELETE", "/events/" + quote(event_id, safe=""), params={"sendUpdates": "none"})


def private(event: dict) -> dict:
    return event.get("extendedProperties", {}).get("private", {})


def same_body(remote: dict, desired: dict) -> bool:
    for key in ("summary", "location", "description"):
        if remote.get(key) != desired[key]:
            return False
    for key in ("start", "end"):
        try:
            instant = datetime.fromisoformat(remote[key]["dateTime"].replace("Z", "+00:00"))
            if instant != datetime.fromisoformat(desired[key]["dateTime"]) or remote[key].get("timeZone") != "Asia/Shanghai":
                return False
        except (KeyError, ValueError, TypeError):
            return False
    reminders = remote.get("reminders", {})
    return (
        reminders.get("useDefault") is False
        and not reminders.get("overrides")
        and all(private(remote).get(k) == v for k, v in private(desired).items())
    )


def route_identity(body: dict) -> tuple[str, str]:
    props = private(body)
    return props.get("flighty_service", "").split("|")[-1], props.get("flighty_route", "")


def nearby_departure(remote: dict, desired: dict) -> bool:
    try:
        old = datetime.fromisoformat(remote["start"]["dateTime"].replace("Z", "+00:00"))
        new = datetime.fromisoformat(desired["start"]["dateTime"])
        return old.utcoffset() is not None and abs(new - old) <= timedelta(hours=24)
    except (KeyError, ValueError, TypeError):
        return False


@dataclass
class Plan:
    create: list[Flight] = field(default_factory=list)
    update: list[tuple[dict, Flight]] = field(default_factory=list)
    delete: list[dict] = field(default_factory=list)
    skipped: int = 0


def future_event(event: dict, as_of: datetime) -> bool:
    try:
        start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
        return start.utcoffset() is not None and start >= as_of
    except (KeyError, ValueError, TypeError):
        return False


def make_plan(snapshot: Snapshot, remote_events: list[dict]) -> Plan:
    owned = {}
    for event in remote_events:
        if private(event).get("flighty_owner") != OWNER or event.get("status") == "cancelled":
            continue
        if not event.get("id") or not private(event).get("flighty_key") or not private(event).get("flighty_service"):
            raise SyncError("Managed event lacks identity; refusing reconciliation")
        if event.get("recurrence") or event.get("recurringEventId"):
            raise SyncError("Managed event was made recurring; manual review required")
        owned[event["id"]] = event
    plan = Plan(skipped=snapshot.skipped)
    unmatched = []
    remaining = list(snapshot.flights.values())
    # Reserve exact future source identities before business-key matching. This
    # retains IDs across fallback upgrades and when a conflict appears/resolves.
    for identity_field in ("flighty_source_key", "flighty_key"):
        unmatched = []
        for flight in sorted(remaining, key=lambda f: f.key):
            identity = private(flight.body).get(identity_field)
            matches = sorted((e for e in owned.values()
                              if identity and private(e).get(identity_field) == identity), key=lambda e: e["id"])
            if matches:
                event = matches[0]
                del owned[event["id"]]
                if same_body(event, flight.body):
                    plan.skipped += 1
                else:
                    plan.update.append((event, flight))
                # Extra copies remain in owned and are removed below.
            else:
                unmatched.append(flight)
        remaining = unmatched
    desired_services = Counter(f.service for f in snapshot.flights.values())
    desired_routes = Counter(route_identity(f.body) for f in snapshot.flights.values())
    for flight in unmatched:
        candidates = [e for e in owned.values() if private(e)["flighty_service"] == flight.service]
        # A unique date+flight-number permits a route correction in place.
        # Multi-leg ambiguity must never be resolved by list order.
        if desired_services[flight.service] == 1 and len(candidates) == 1:
            event = candidates[0]
            del owned[event["id"]]
            plan.update.append((event, flight))
        else:
            identity = route_identity(flight.body)
            moved = [e for e in owned.values()
                     if route_identity(e) == identity
                     and private(e)["flighty_key"] not in snapshot.flights
                     and private(e)["flighty_service"] not in snapshot.protected_services
                     and nearby_departure(e, flight.body)]
            # An isolated flight delayed across midnight can change the date
            # component of its key. Never pair ambiguous daily repetitions.
            if desired_routes[identity] == 1 and len(moved) == 1:
                event = moved[0]
                del owned[event["id"]]
                plan.update.append((event, flight))
            else:
                plan.create.append(flight)
    for event in owned.values():
        if (private(event)["flighty_service"] in snapshot.protected_services
                and not future_event(event, snapshot.as_of)):
            plan.skipped += 1
            warning("Preserving an existing mirror for a skipped, unresolved route")
        else:
            plan.delete.append(event)
    return plan


def apply_plan(client: GoogleCalendar, plan: Plan) -> None:
    # Finish creates/updates before deleting obsolete mirrors. On any uncertain
    # write, stop; the next run re-reads Google's durable identity properties.
    for flight in plan.create:
        result = client.create(flight.body)
        if not result.get("id"):
            raise SyncError("Insert result missing event ID; re-list on next run")
    for event, flight in plan.update:
        result = client.update(event["id"], flight.body)
        if result.get("id") != event["id"]:
            raise SyncError("Update result missing event ID; re-list on next run")
    for event in plan.delete:
        client.delete(event["id"])


def check_future(snapshot: Snapshot, remote_events: list[dict]) -> None:
    # Re-list after all writes. An API success response alone is not evidence
    # that every future source record exists in the target calendar.
    counts = Counter(private(event).get("flighty_source_key") for event in remote_events
                     if event.get("id") and event.get("status") != "cancelled"
                     and private(event).get("flighty_owner") == OWNER
                     and private(event).get("flighty_source_key") in snapshot.future_sources)
    missing = sorted(set(snapshot.future_sources) - counts.keys())
    google_count = sum(counts.values())
    print(f"FLIGHTY_FUTURE_CHECK source={len(snapshot.future_sources)} google={google_count} missing={len(missing)}")
    duplicates = sum(count - 1 for count in counts.values())
    print(f"FLIGHTY_FUTURE_DUPLICATES count={duplicates}")
    if missing:
        warning(f"FLIGHTY_FUTURE_GAP missing={len(missing)}")
        for key in missing:
            warning(f"MISSING={snapshot.future_sources[key]}")
        raise SyncError("Future completeness check failed")
    if duplicates:
        raise SyncError("Future source identities have duplicate Google events")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview only; with credentials compare live state, otherwise assume an empty target")
    args = parser.parse_args(argv)
    config = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENV}
    configured = all(config.values())
    if not configured and not args.dry_run:
        print("FLIGHTY_SYNC=SKIPPED_NOT_CONFIGURED")
        return 0
    try:
        snapshot = read_snapshot(ROOT / "flight.ics", Airports.load(ROOT))
        print(f"FLIGHTY_FUTURE_SOURCE count={len(snapshot.future_sources)} as_of={snapshot.as_of.isoformat()}")
        print(f"FLIGHTY_FUTURE_FALLBACK iata={snapshot.future_airports['iata']} icao={snapshot.future_airports['icao']} raw={snapshot.future_airports['raw']}")
        client = None
        remote = []
        if configured:
            client = GoogleCalendar(config)
            client.authenticate()
            client.validate_calendar()
            remote = client.list_owned()
        else:
            print("FLIGHTY_DRY_RUN=OFFLINE_EMPTY_TARGET (create counts are a preview; no remote comparison)")
        plan = make_plan(snapshot, remote)
        for flight in sorted(snapshot.flights.values(), key=lambda f: (f.service, f.key)):
            print(f"FLIGHTY_TITLE={flight.service} {flight.body['summary']}")
        print(f"FLIGHTY_PLAN create={len(plan.create)} update={len(plan.update)} delete={len(plan.delete)} skip={plan.skipped}")
        if args.dry_run:
            print("FLIGHTY_SYNC=DRY_RUN")
        else:
            apply_plan(client, plan)
            check_future(snapshot, client.list_owned())
            print("FLIGHTY_SYNC=SUCCESS")
        return 0
    except Exception as exc:
        # Third-party exceptions may contain request bodies or credentials.
        message = str(exc) if isinstance(exc, SyncError) else type(exc).__name__
        warning(f"FLIGHTY_SYNC=ERROR {message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
