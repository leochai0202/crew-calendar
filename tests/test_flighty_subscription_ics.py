from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from ics import Calendar

import generate_flighty_subscription_ics as subscription
import sync_flighty_google_calendar as flighty

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 14, 16, tzinfo=flighty.BEIJING)


def source_event(number="9C7681", origin="上海虹桥", destination="揭阳潮汕",
                 start="20261015T102000", end="20261015T123000", kind="航班"):
    def text(value):
        return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")

    description = "\\n".join([
        f"类型：{kind}", f"航班：{number}", f"航线：{text(origin)} → {text(destination)}",
        "人员名单：", "私密机长甲", "私密乘务乙", "签到：08:40", "注册号：B-TEST",
        "机型：A320-TEST", "版本：PRIVATE-SCHEDULE-VERSION", "secret=never-print-secret",
    ])
    return "\r\n".join([
        "BEGIN:VEVENT", f"UID:source-{number}@test",
        f"SUMMARY:✈️ {number} {text(origin)}→{text(destination)}",
        f"DTSTART;TZID=Asia/Shanghai:{start}", f"DTEND;TZID=Asia/Shanghai:{end}",
        f"DESCRIPTION:{description}", "BEGIN:VALARM", "ACTION:DISPLAY",
        "TRIGGER:-PT90M", "DESCRIPTION:私密机长甲", "END:VALARM", "END:VEVENT",
    ]) + "\r\n"


def write_source(path, events):
    path.write_bytes(("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(events) + "END:VCALENDAR\r\n").encode())


@pytest.fixture
def source_root(tmp_path):
    (tmp_path / "config").mkdir()
    for name in ("crew_calendar_main.py", "airport_aliases.json", "config/airport_iata.json"):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    write_source(tmp_path / "crew_schedule.ics", [source_event()])
    write_source(tmp_path / "flight.ics", [])
    (tmp_path / "positioning.ics").write_bytes(b"must not be read or changed")
    return tmp_path


def build(root):
    return flighty.read_snapshot(root / "crew_schedule.ics", flighty.Airports.load(root),
                                now=NOW, historical_path=root / "flight.ics")


def test_history_and_future_google_body_parity_with_suffixes(source_root):
    events = [source_event(),
        source_event("9C7651X", "揭阳潮汕", "合肥新桥", "20261016T100000", "20261016T120000", "置位"),
        source_event("9C7651Y", "合肥新桥", "伊犁伊宁", "20261016T130000", "20261016T170000", "其他"),
        source_event("9C7652X", "伊犁伊宁", "合肥新桥", "20261017T100000", "20261017T140000", "training"),
        source_event("9C7652Y", "合肥新桥", "揭阳潮汕", "20261017T150000", "20261017T170000", "ferry"),
        source_event("", "宁波栎社", "上海虹桥", kind="摆渡"),
    ]
    past = source_event("9C6731", start="20261013T100000", end="20261013T120000")
    write_source(source_root / "crew_schedule.ics", [past, *events])
    write_source(source_root / "flight.ics", [past])
    before = {p.name: p.read_bytes() for p in source_root.glob("*.ics")}
    snapshot = build(source_root)
    assert subscription.generate(source_root, now=NOW) == 6
    data = (source_root / "flighty.ics").read_bytes()
    parsed = Calendar(data.decode())
    expected = {snapshot.subscription_source_keys[f.key] + "@crew-calendar-flighty": f.body
                for f in snapshot.flights.values()}
    assert len(parsed.events) == 6
    assert len(snapshot.future_sources) == 5
    assert {e.uid for e in parsed.events} == set(expected)
    for event in parsed.events:
        body = expected[event.uid]
        assert event.name == body["summary"]
        assert event.location == body["location"]
        if flighty.private(body).get("flighty_source_key") in snapshot.future_sources:
            assert event.description == body["description"]
        else:
            assert event.description.replace("\nDeparture Airport: SHA\nArrival Airport: SWA", "") == body["description"]
        assert "Departure Airport: " in event.description and "Arrival Airport: " in event.description
        assert event.begin.datetime == datetime.fromisoformat(body["start"]["dateTime"])
        assert event.end.datetime == datetime.fromisoformat(body["end"]["dateTime"])
        assert not event.alarms
    assert {e.name for e in parsed.events} == {
        "Spring Airlines 9C7681 SHA → SWA", "Spring Airlines 9C7651X SWA → HFE",
        "Spring Airlines 9C7651Y HFE → YIN", "Spring Airlines 9C7652X YIN → HFE",
        "Spring Airlines 9C7652Y HFE → SWA", "Spring Airlines 9C6731 SHA → SWA",
    }
    for forbidden in ("私密机长甲", "私密乘务乙", "人员名单", "签到", "注册号", "B-TEST", "机型", "A320-TEST",
                      "PRIVATE-SCHEDULE-VERSION", "never-print-secret", "VALARM", "source-9C"):
        assert forbidden not in data.decode()
    assert all((source_root / name).read_bytes() == original for name, original in before.items())


def test_headers_crlf_and_utf8_octet_folding(source_root):
    raw_name = "未知机场航站楼" * 30 + "\\T1;A,B"
    write_source(source_root / "crew_schedule.ics", [source_event(origin=raw_name)])
    subscription.generate(source_root, now=NOW)
    data = (source_root / "flighty.ics").read_bytes()
    assert data.endswith(b"END:VCALENDAR\r\n")
    assert b"\n" not in data.replace(b"\r\n", b"")
    assert b"\r" not in data.replace(b"\r\n", b"")
    for line in data.split(b"\r\n"):
        assert len(line) <= 75
        line.decode("utf-8")  # A folded physical line never splits a codepoint.
    for header in ("VERSION:2.0", "PRODID:-//Crew Calendar//Flighty Subscription//EN",
                   "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Flighty Flights",
                   "X-WR-TIMEZONE:Asia/Shanghai", "TZID:Asia/Shanghai"):
        assert (header + "\r\n").encode() in data
    event, = Calendar(data.decode()).events
    assert event.location == raw_name
    assert event.description == next(iter(build(source_root).flights.values())).body["description"]
    assert b"\r\n " in data


def test_text_escaping_and_description_newlines_round_trip(source_root):
    snapshot = build(source_root)
    body = next(iter(snapshot.flights.values())).body
    value = "one\\two;three,four\n中文换行"
    body["description"] = value
    data = subscription.render_calendar(snapshot)
    assert b"one\\\\two\\;three\\,four\\n" in data
    event, = Calendar(data.decode()).events
    assert event.description == value


@pytest.mark.parametrize("origin,expected", [("上海虹桥", "SHA"), ("扬州泰州", "ZSYZ"), ("新机场名称", "新机场名称")])
def test_uses_shared_airport_fallback(source_root, origin, expected):
    write_source(source_root / "crew_schedule.ics", [source_event(origin=origin)])
    subscription.generate(source_root, now=NOW)
    event, = Calendar((source_root / "flighty.ics").read_text(encoding="utf-8")).events
    assert event.location == expected
    assert f"Departure Airport: {expected}" in event.description


def test_uid_survives_refresh_and_source_order(source_root):
    entries = [source_event(), source_event("9C7682", start="20261015T230000", end="20261016T010000")]
    write_source(source_root / "crew_schedule.ics", entries)
    subscription.generate(source_root, now=NOW)
    first = Calendar((source_root / "flighty.ics").read_text(encoding="utf-8"))
    write_source(source_root / "crew_schedule.ics", list(reversed(entries)))
    subscription.generate(source_root, now=NOW + timedelta(minutes=5))
    second = Calendar((source_root / "flighty.ics").read_text(encoding="utf-8"))
    assert {e.name: e.uid for e in first.events} == {e.name: e.uid for e in second.events}
    night = next(e for e in second.events if "9C7682" in e.name)
    assert night.begin.to("Asia/Shanghai").format("YYYY-MM-DD HH:mm") == "2026-10-15 23:00"
    assert night.end.to("Asia/Shanghai").format("YYYY-MM-DD HH:mm") == "2026-10-16 01:00"


def test_conflicting_future_sources_have_distinct_stable_uids(source_root):
    write_source(source_root / "crew_schedule.ics", [source_event(), source_event(end="20261015T125000")])
    assert subscription.generate(source_root, now=NOW) == 2
    data = (source_root / "flighty.ics").read_bytes()
    events = Calendar(data.decode()).events
    assert len({e.uid for e in events}) == 2
    subscription.generate(source_root, now=NOW)
    assert (source_root / "flighty.ics").read_bytes() == data


def test_no_history_or_future_produces_valid_empty_subscription(source_root):
    write_source(source_root / "crew_schedule.ics", [])
    assert subscription.generate(source_root, now=NOW) == 0
    assert not Calendar((source_root / "flighty.ics").read_text(encoding="utf-8")).events


@pytest.mark.parametrize("phase", ["source", "render", "write", "replace"])
def test_failure_preserves_last_good_and_other_ics(source_root, monkeypatch, capsys, phase):
    target = source_root / "flighty.ics"
    target.write_bytes(b"last-good\r\n")
    monkeypatch.setattr(subscription, "ROOT", source_root)
    monkeypatch.setattr(flighty, "current_time", lambda: NOW)

    def fail(*args, **kwargs):
        if phase == "replace":
            assert len(Calendar(Path(args[0]).read_text(encoding="utf-8")).events) == 1
            assert target.read_bytes() == b"last-good\r\n"
        raise OSError("never-print-private-key never-print-token")

    if phase == "source":
        (source_root / "crew_schedule.ics").write_bytes(b"BEGIN:VCALENDAR\r\n")
    elif phase == "render":
        monkeypatch.setattr(subscription, "render_calendar", fail)
    elif phase == "write":
        monkeypatch.setattr(subscription.os, "fsync", fail)
    else:
        monkeypatch.setattr(subscription.os, "replace", fail)
    before = {p: p.read_bytes() for p in source_root.glob("*.ics")}
    assert subscription.main() == 1
    assert all(p.read_bytes() == content for p, content in before.items())
    assert not (source_root / "flighty.ics.tmp").exists()
    output = capsys.readouterr().out
    assert "::warning" in output and "FLIGHTY_SUBSCRIPTION=ERROR" in output
    assert "never-print-private-key" not in output and "never-print-token" not in output


def test_no_google_auth_or_network_and_complete_atomic_replace(source_root, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Subscription generator must be offline")

    monkeypatch.setattr(flighty.GoogleCalendar, "__init__", forbidden)
    monkeypatch.setattr(flighty.requests.sessions.Session, "request", forbidden)
    for name in flighty.REQUIRED_ENV:
        monkeypatch.setenv(name, "never-print-secret")
    real_replace = subscription.os.replace
    observed = []

    def replace_complete(source, target):
        assert Path(source).name == "flighty.ics.tmp" and Path(target).name == "flighty.ics"
        data = Path(source).read_bytes()
        assert data.endswith(b"END:VCALENDAR\r\n")
        assert len(Calendar(data.decode()).events) == 1
        observed.append(True)
        real_replace(source, target)

    monkeypatch.setattr(subscription.os, "replace", replace_complete)
    assert subscription.generate(source_root, now=NOW) == 1
    assert observed == [True]
    assert not (source_root / "flighty.ics.tmp").exists()


def test_future_completeness_failure_cannot_publish_partial_feed(source_root, monkeypatch):
    snapshot = build(source_root)
    snapshot.flights.clear()
    target = source_root / "flighty.ics"
    target.write_bytes(b"last-good")
    monkeypatch.setattr(flighty, "read_snapshot", lambda *args, **kwargs: snapshot)
    with pytest.raises(ValueError, match="Incomplete"):
        subscription.generate(source_root, now=NOW)
    assert target.read_bytes() == b"last-good"


def test_workflow_order_is_nonblocking_and_has_no_credentials():
    workflow = (ROOT / ".github/workflows/schedule.yml").read_text(encoding="utf-8")
    names = ["Clean ICS people lists", "Generate Flighty subscription ICS", "Publish ICS files through GitHub API", "Sync Flighty Google Calendar"]
    assert [workflow.index("- name: " + name) for name in names] == sorted(workflow.index("- name: " + name) for name in names)
    step = workflow.split("- name: Generate Flighty subscription ICS", 1)[1].split("- name:", 1)[0]
    for gate in ("steps.scraper.outcome == 'success'", "steps.scraper.outputs.auth_status == 'AUTHENTICATED'", "steps.ics_clean.outcome == 'success'"):
        assert gate in step
    assert "continue-on-error: true" in step and "::warning" in step
    assert "python -B generate_flighty_subscription_ics.py" in step
    assert "secrets." not in step and "\n        env:" not in step
    assert "GOOGLE" not in step and "GITHUB_TOKEN" not in step and "CREW_" not in step
    publish = workflow.split("- name: Publish ICS files through GitHub API", 1)[1].split("- name:", 1)[0]
    assert '-Filter "*.ics"' in publish and "github_api_publish.py" in publish
    assert "flighty_subscription" not in publish
    google = workflow.split("- name: Sync Flighty Google Calendar", 1)[1]
    assert "flighty_subscription" not in google


@pytest.mark.parametrize("entry", [
    source_event(),
    source_event("9C7651X", "揭阳潮汕", "合肥新桥", "20261016T100000", "20261016T120000"),
    source_event("9C7651Y", destination="揭阳潮汕(+1)", start="20261015T230000", end="20261016T010000"),
])
def test_uid_is_identical_before_at_and_after_departure(source_root, entry):
    write_source(source_root / "crew_schedule.ics", [entry])
    write_source(source_root / "flight.ics", [entry])
    snapshot = build(source_root)
    flight, = snapshot.flights.values()
    source_key = flighty.private(flight.body)["flighty_source_key"]
    start = datetime.fromisoformat(flight.body["start"]["dateTime"])
    end = datetime.fromisoformat(flight.body["end"]["dateTime"])
    expected_uid = source_key + "@crew-calendar-flighty"
    expected_event = None
    for now in (NOW, start, start + timedelta(seconds=1), end + timedelta(days=1)):
        before = {p: p.read_bytes() for p in (source_root / "flight.ics", source_root / "crew_schedule.ics")}
        assert subscription.generate(source_root, now=now) == 1
        data = (source_root / "flighty.ics").read_bytes()
        event, = Calendar(data.decode()).events
        assert event.uid == expected_uid
        properties = (event.uid, event.name, event.location, event.description, event.begin, event.end)
        if expected_event is None:
            expected_event = properties
        assert properties == expected_event
        assert subscription.generate(source_root, now=now) == 1
        assert (source_root / "flighty.ics").read_bytes() == data
        assert all(p.read_bytes() == original for p, original in before.items())


def test_uid_matches_preexisting_production_future_algorithm(source_root):
    # Captured from the deployed future-only feed for this unchanged source.
    expected_uid = "92e274a6f6c769c9bbbe28d302081ef2f67a1a476ac19a0469ea81d7804c91f0@crew-calendar-flighty"
    write_source(source_root / "flight.ics", [source_event()])
    for now in (NOW, datetime(2026, 10, 16, tzinfo=flighty.BEIJING)):
        subscription.generate(source_root, now=now)
        event, = Calendar((source_root / "flighty.ics").read_text(encoding="utf-8")).events
        assert event.uid == expected_uid


def test_history_only_skips_unknown_airports_conflicts_and_positioning(source_root):
    good = source_event("9C6731", start="20261013T100000", end="20261013T120000")
    unknown = source_event("9C6732", origin="未知机场", start="20261013T130000", end="20261013T150000")
    conflict1 = source_event("9C6733", start="20261013T160000", end="20261013T180000")
    conflict2 = source_event("9C6733", start="20261013T160000", end="20261013T183000")
    positioning = source_event("9C6734", start="20261013T190000", end="20261013T210000", kind="置位")
    write_source(source_root / "flight.ics", [good, good, unknown, conflict1, conflict2, positioning])
    write_source(source_root / "crew_schedule.ics", [])
    snapshot = build(source_root)
    assert not snapshot.future_sources
    assert len(snapshot.flights) == len(snapshot.subscription_source_keys) == 1
    assert subscription.generate(source_root, now=NOW) == 1
    data = (source_root / "flighty.ics").read_bytes()
    event, = Calendar(data.decode()).events
    assert event.name == "Spring Airlines 9C6731 SHA → SWA"
    assert subscription.generate(source_root, now=NOW) == 1
    assert (source_root / "flighty.ics").read_bytes() == data


def test_subscription_metadata_and_rendering_do_not_patch_google_history(source_root):
    past = source_event("9C6731", start="20261013T100000", end="20261013T120000")
    write_source(source_root / "flight.ics", [past])
    snapshot = build(source_root)
    before = copy.deepcopy(snapshot.flights)
    historical = next(f for f in snapshot.flights.values() if f.service == "2026-10-13|9C6731")
    legacy_key = hashlib.sha256(b"2026-10-13|9C6731|SHA|SWA").hexdigest()
    assert flighty.private(historical.body) == {
        "flighty_owner": flighty.OWNER, "flighty_key": legacy_key,
        "flighty_service": "2026-10-13|9C6731", "flighty_route": "SHA|SWA",
    }
    assert "Departure Airport:" not in historical.body["description"]
    assert "Arrival Airport:" not in historical.body["description"]
    remotes = [copy.deepcopy(f.body) | {"id": "existing-google-id-" + f.key} for f in snapshot.flights.values()]
    original_plan = flighty.make_plan(snapshot, remotes)
    assert not original_plan.create and not original_plan.update and not original_plan.delete
    subscription.render_calendar(snapshot)
    assert snapshot.flights == before
    assert flighty.make_plan(snapshot, remotes) == original_plan
    snapshot.subscription_source_keys.clear()
    assert flighty.make_plan(snapshot, remotes) == original_plan
    flighty.check_future(snapshot, remotes)


@pytest.mark.parametrize("damage", ["duplicate", "missing", "future_mismatch"])
def test_incomplete_subscription_metadata_keeps_last_good(source_root, monkeypatch, damage):
    write_source(source_root / "flight.ics", [source_event("9C6731", start="20261013T100000", end="20261013T120000")])
    snapshot = build(source_root)
    future_key = next(f.key for f in snapshot.flights.values() if "flighty_source_key" in flighty.private(f.body))
    historical_key = next(key for key in snapshot.flights if key != future_key)
    if damage == "duplicate":
        snapshot.subscription_source_keys[historical_key] = snapshot.subscription_source_keys[future_key]
    elif damage == "missing":
        del snapshot.subscription_source_keys[historical_key]
    else:
        snapshot.subscription_source_keys[future_key], snapshot.subscription_source_keys[historical_key] = (
            snapshot.subscription_source_keys[historical_key], snapshot.subscription_source_keys[future_key])
    target = source_root / "flighty.ics"
    target.write_bytes(b"last-good")
    monkeypatch.setattr(flighty, "read_snapshot", lambda *args, **kwargs: snapshot)
    with pytest.raises(ValueError, match="Incomplete or duplicate"):
        subscription.generate(source_root, now=NOW)
    assert target.read_bytes() == b"last-good"
