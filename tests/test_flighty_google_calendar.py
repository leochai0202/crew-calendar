from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import requests

import sync_flighty_google_calendar as sync

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "client_email": "test@test-project.iam.gserviceaccount.com",
    "private_key": "never-print-private-key",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def event(*, number="9C6731", origin="大连周水子", destination="呼和浩特白塔",
          start="20261001T161500", end="20261001T182000", kind="航班", status=""):
    # The production UID includes time and route. Changing either must still
    # update the existing Google event, instead of treating the UID as identity.
    uid = hashlib.md5(f"{number}|{origin}|{destination}|{start}|{end}".encode()).hexdigest()
    return (
        "BEGIN:VEVENT\n"
        f"UID:{uid}@crew-calendar\n"
        f"SUMMARY:✈️ {number} {origin}→{destination}\n"
        f"DTSTART;TZID=Asia/Shanghai:{start}\n"
        f"DTEND;TZID=Asia/Shanghai:{end}\n"
        f"DESCRIPTION:类型：{kind}\\n航班：{number}\\n航线：{origin} → {destination}\n"
        + (f"STATUS:{status}\n" if status else "")
        + "BEGIN:VALARM\nDESCRIPTION:reminder\nTRIGGER:-PT90M\nACTION:DISPLAY\nEND:VALARM\nEND:VEVENT\n"
    )


def write_ics(tmp_path, *events):
    path = tmp_path / "flight.ics"
    path.write_text("BEGIN:VCALENDAR\nVERSION:2.0\n" + "".join(events) + "END:VCALENDAR\n", encoding="utf-8")
    return path


@pytest.fixture
def airports():
    return sync.Airports.load(ROOT)


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    # Main/CLI tests must not depend on a particular live schedule still being
    # retained in Git history after future calendar publications.
    (tmp_path / "config").mkdir()
    for name in ("crew_calendar_main.py", "airport_aliases.json", "config/airport_iata.json"):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    write_ics(tmp_path, event())
    (tmp_path / "positioning.ics").write_bytes((tmp_path / "flight.ics").read_bytes())
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    return tmp_path


class Calendar:
    """Google's persisted state survives new client instances / workflow runs."""
    def __init__(self, events=()):
        self.events = {e["id"]: copy.deepcopy(e) for e in events}
        self.calls = []
        self.next_id = 0

    def create(self, body):
        assert "id" not in body
        self.next_id += 1
        result = copy.deepcopy(body) | {"id": f"googleassigned{self.next_id}"}
        self.events[result["id"]] = result
        self.calls.append(("create", result["id"]))
        return result

    def update(self, event_id, body):
        self.events[event_id].update(copy.deepcopy(body))
        self.calls.append(("update", event_id))
        return self.events[event_id]

    def delete(self, event_id):
        del self.events[event_id]
        self.calls.append(("delete", event_id))


def reconcile(client, snapshot):
    plan = sync.make_plan(snapshot, list(client.events.values()))
    sync.apply_plan(client, plan)
    return plan


def test_title_iata_airline_and_no_alarm_copy(tmp_path, airports):
    snapshot = sync.read_snapshot(write_ics(tmp_path, event()), airports)
    flight, = snapshot.flights.values()
    body = flight.body
    assert body["summary"] == "Spring Airlines 9C6731 DLC → HET"
    assert body["location"] == "DLC"
    assert "Airline: Spring Airlines\nFlight: 9C6731\nFrom: DLC\nTo: HET" in body["description"]
    assert body["description"].endswith("\nCrew")
    assert body["start"] == {"dateTime": "2026-10-01T16:15:00+08:00", "timeZone": "Asia/Shanghai"}
    assert body["reminders"] == {"useDefault": False, "overrides": []}
    assert len(flight.key) == 64


def test_chinese_to_existing_icao_to_iata(airports):
    assert airports.names["大连周水子"] == {"ZYTL"}
    assert airports.codes["ZYTL"]["iata"] == "DLC"
    assert airports.resolve("大连周水子")[0] == "DLC"
    assert airports.resolve("ZYTL")[0] == "DLC"
    assert airports.resolve("DLC")[0] == "DLC"
    assert airports.resolve("呼和浩特白塔(+1)")[0] == "HET"
    assert airports.codes["VDTI"]["iata"] == "KTI"


def test_no_fuzzy_or_conflicting_airport_guess(airports):
    for unknown in ("大连", "大阪", "未知机场", "ZZZZ", "ZZZ", "扬州泰州"):
        with pytest.raises(ValueError):
            airports.resolve(unknown)
    airports.names["大连周水子"].add("ZSPD")
    with pytest.raises(ValueError):
        airports.resolve("大连周水子")


def test_cross_midnight_keeps_exact_instants(tmp_path, airports):
    snapshot = sync.read_snapshot(write_ics(tmp_path, event(start="20261001T230000", end="20261002T011500", destination="呼和浩特白塔(+1)")), airports)
    flight, = snapshot.flights.values()
    assert flight.body["end"]["dateTime"] == "2026-10-02T01:15:00+08:00"
    assert flight.service == "2026-10-01|9C6731"


def test_utc_is_converted_to_beijing(tmp_path, airports):
    text = event().replace("DTSTART;TZID=Asia/Shanghai:20261001T161500", "DTSTART:20261001T081500Z").replace("DTEND;TZID=Asia/Shanghai:20261001T182000", "DTEND:20261001T102000Z")
    snapshot = sync.read_snapshot(write_ics(tmp_path, text), airports)
    assert next(iter(snapshot.flights.values())).body["start"]["dateTime"] == "2026-10-01T16:15:00+08:00"


def test_repeated_run_reuses_google_id_and_remote_persisted_key(tmp_path, airports):
    source = write_ics(tmp_path, event())
    client = Calendar()
    reconcile(client, sync.read_snapshot(source, airports))
    first = copy.deepcopy(client.events)
    # Fresh process with only the server state; no local cache or git state.
    next_run = Calendar(first.values())
    plan = reconcile(next_run, sync.read_snapshot(source, airports))
    assert not next_run.calls
    assert next_run.events == first
    assert plan.skipped == 1


def test_time_and_source_uid_change_updates_original(tmp_path, airports):
    client = Calendar()
    reconcile(client, sync.read_snapshot(write_ics(tmp_path, event()), airports))
    before_id, = client.events
    before_key = sync.private(client.events[before_id])["flighty_key"]
    plan = reconcile(client, sync.read_snapshot(write_ics(tmp_path, event(start="20261001T164500", end="20261001T185000")), airports))
    assert len(plan.update) == 1 and not plan.create and not plan.delete
    assert list(client.events) == [before_id]
    assert sync.private(client.events[before_id])["flighty_key"] == before_key


def test_route_change_updates_original_and_stable_key(tmp_path, airports):
    client = Calendar()
    reconcile(client, sync.read_snapshot(write_ics(tmp_path, event()), airports))
    before_id, = client.events
    before_key = sync.private(client.events[before_id])["flighty_key"]
    plan = reconcile(client, sync.read_snapshot(write_ics(tmp_path, event(destination="上海浦东")), airports))
    assert len(plan.update) == 1 and not plan.create and not plan.delete
    assert list(client.events) == [before_id]
    assert sync.private(client.events[before_id])["flighty_key"] != before_key
    assert client.events[before_id]["summary"] == "Spring Airlines 9C6731 DLC → PVG"


def test_delay_across_midnight_updates_original_event(tmp_path, airports):
    client = Calendar()
    reconcile(client, sync.read_snapshot(write_ics(tmp_path, event(start="20261001T230000", end="20261002T011500")), airports))
    before_id, = client.events
    plan = reconcile(client, sync.read_snapshot(write_ics(tmp_path, event(start="20261002T003000", end="20261002T024500")), airports))
    assert len(plan.update) == 1 and not plan.create and not plan.delete
    assert list(client.events) == [before_id]
    assert sync.private(client.events[before_id])["flighty_service"] == "2026-10-02|9C6731"


def test_ambiguous_daily_repetitions_are_not_paired(tmp_path, airports):
    client = Calendar()
    reconcile(client, sync.read_snapshot(write_ics(tmp_path,
        event(start="20261001T230000", end="20261002T011500"),
        event(start="20261002T230000", end="20261003T011500")), airports))
    plan = reconcile(client, sync.read_snapshot(write_ics(tmp_path,
        event(start="20261002T003000", end="20261002T024500"),
        event(start="20261003T003000", end="20261003T024500")), airports))
    # The existing exact date/key is updated first; remaining daily identities
    # are ambiguous and use replacement instead of order-based pairing.
    assert len(plan.update) == 1
    assert len(plan.create) == len(plan.delete) == 1


def test_flight_number_change_replaces_old_event(tmp_path, airports):
    client = Calendar()
    reconcile(client, sync.read_snapshot(write_ics(tmp_path, event()), airports))
    old_id, = client.events
    plan = reconcile(client, sync.read_snapshot(write_ics(tmp_path, event(number="9C6733")), airports))
    assert len(plan.create) == len(plan.delete) == 1
    assert old_id not in client.events
    assert len(client.events) == 1


@pytest.mark.parametrize("replacement", ["absent", "cancelled", "reclassified"])
def test_cancellation_removes_only_owned_event(tmp_path, airports, replacement):
    client = Calendar([{"id": "personal", "summary": "Do not delete"}])
    reconcile(client, sync.read_snapshot(write_ics(tmp_path, event()), airports))
    events = [] if replacement == "absent" else [event(status="CANCELLED") if replacement == "cancelled" else event(kind="置位")]
    plan = reconcile(client, sync.read_snapshot(write_ics(tmp_path, *events), airports))
    assert len(plan.delete) == 1
    assert list(client.events) == ["personal"]


@pytest.mark.parametrize("kind", ["置位", "摆渡", "训练", "考勤", "待命", "其他任务", "其他", ""])
def test_non_flight_excluded_even_with_flight_number(tmp_path, airports, kind):
    snapshot = sync.read_snapshot(write_ics(tmp_path, event(kind=kind)), airports)
    assert not snapshot.flights and snapshot.skipped == 1


def test_unknown_iata_warns_and_preserves_existing_service(tmp_path, airports, capsys):
    client = Calendar()
    reconcile(client, sync.read_snapshot(write_ics(tmp_path, event()), airports))
    snapshot = sync.read_snapshot(write_ics(tmp_path, event(destination="未知机场")), airports)
    plan = reconcile(client, snapshot)
    assert not plan.create and not plan.update and not plan.delete
    assert "::warning" in capsys.readouterr().out
    assert len(client.events) == 1


def test_duplicate_source_and_remote_events_are_reconciled(tmp_path, airports):
    snapshot = sync.read_snapshot(write_ics(tmp_path, event(), event()), airports)
    assert len(snapshot.flights) == 1 and snapshot.skipped == 1
    client = Calendar()
    reconcile(client, snapshot)
    original = next(iter(client.events.values()))
    client.events["extra"] = copy.deepcopy(original) | {"id": "extra"}
    plan = reconcile(client, snapshot)
    assert len(plan.delete) == 1
    assert len(client.events) == 1


def test_same_number_multiple_legs_kept_separate(tmp_path, airports):
    snapshot = sync.read_snapshot(write_ics(tmp_path, event(), event(origin="呼和浩特白塔", destination="上海浦东", start="20261001T192000", end="20261001T212000")), airports)
    client = Calendar()
    reconcile(client, snapshot)
    reconcile(client, snapshot)
    assert len(client.events) == 2
    assert len(client.calls) == 2


def test_segment_suffixes_are_preserved(tmp_path, airports):
    snapshot = sync.read_snapshot(write_ics(tmp_path, event(number="9C6731X"), event(number="9C6731Y", origin="呼和浩特白塔", destination="上海浦东")), airports)
    assert len(snapshot.flights) == 2
    assert {f.body["summary"].split()[2] for f in snapshot.flights.values()} == {"9C6731X", "9C6731Y"}


@pytest.mark.parametrize("damage", ["truncated", "bad_time", "floating", "unknown_tz", "all_day", "reverse", "mismatched_number"])
def test_invalid_snapshot_fails_closed(tmp_path, airports, damage):
    text = event()
    if damage == "bad_time":
        text = text.replace("20261001T161500", "not-a-time")
    elif damage == "floating":
        text = text.replace(";TZID=Asia/Shanghai", "")
    elif damage == "unknown_tz":
        text = text.replace("Asia/Shanghai", "Unknown/Zone")
    elif damage == "all_day":
        text = text.replace("20261001T161500", "20261001")
    elif damage == "reverse":
        text = text.replace("20261001T182000", "20261001T152000")
    elif damage == "mismatched_number":
        text = text.replace("SUMMARY:✈️ 9C6731", "SUMMARY:✈️ 9C6732")
    path = write_ics(tmp_path, text)
    if damage == "truncated":
        path.write_text(path.read_text(encoding="utf-8").replace("END:VEVENT", ""), encoding="utf-8")
    with pytest.raises(sync.SyncError):
        sync.read_snapshot(path, airports)


def test_conflicting_times_skip_entire_group_without_guessing(tmp_path, airports, capsys):
    source = write_ics(tmp_path, event(), event(start="20261001T164500"), event(), event(number="9C6732"))
    before = source.read_bytes()
    snapshot = sync.read_snapshot(source, airports)
    assert snapshot.skipped == 3
    assert len(snapshot.flights) == 1
    assert "2026-10-01|9C6731" in snapshot.protected_services
    assert "conflicting source times" in capsys.readouterr().out
    assert source.read_bytes() == before


def test_folded_description_and_alarm_are_parsed(tmp_path, airports):
    text = event().replace("\\n航线", "\\n\n 航线")
    snapshot = sync.read_snapshot(write_ics(tmp_path, text), airports)
    assert len(snapshot.flights) == 1


def configured_env(monkeypatch):
    monkeypatch.setenv("FLIGHTY_GOOGLE_CALENDAR_ID", "test@group.calendar.google.com")
    monkeypatch.setenv("FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps(SERVICE_ACCOUNT_INFO))


@pytest.fixture
def service_account_auth(monkeypatch):
    from google.oauth2 import service_account

    observed = {"refresh_requests": []}

    class Credentials:
        token = None

        def refresh(self, request):
            observed["refresh_requests"].append(request)
            if "error" in observed:
                raise observed["error"]
            self.token = observed.get("token", "private-token")

    def from_info(info, *, scopes):
        observed["info"] = info
        observed["scopes"] = scopes
        return Credentials()

    monkeypatch.setattr(service_account.Credentials, "from_service_account_info", from_info)
    return observed


@pytest.mark.parametrize("missing", sync.REQUIRED_ENV)
def test_unconfigured_skip_does_not_read_or_write_source(tmp_path, monkeypatch, capsys, missing):
    configured_env(monkeypatch)
    monkeypatch.delenv(missing)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    assert sync.main([]) == 0  # No flight.ics is required for safe skip.
    assert capsys.readouterr().out.strip() == "FLIGHTY_SYNC=SKIPPED_NOT_CONFIGURED"
    assert not list(tmp_path.iterdir())


def test_offline_dry_run_needs_no_credentials_or_writes(monkeypatch, capsys, isolated_root):
    for key in sync.REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    before = {p: p.read_bytes() for p in isolated_root.glob("*.ics")}
    assert sync.main(["--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "FLIGHTY_DRY_RUN=OFFLINE_EMPTY_TARGET" in output
    assert "FLIGHTY_PLAN create=" in output and "update=0 delete=0" in output
    assert "Spring Airlines 9C6731 DLC → HET" in output
    assert all(p.read_bytes() == b for p, b in before.items())


class Session:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = next(self.replies)
        if isinstance(response, Exception):
            raise response
        status, body = response
        result = requests.Response()
        result.status_code = status
        result._content = json.dumps(body).encode()
        return result


def api_client(replies):
    config = {
        "FLIGHTY_GOOGLE_CALENDAR_ID": "test@group.calendar.google.com",
        "FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps(SERVICE_ACCOUNT_INFO),
    }
    return sync.GoogleCalendar(config, Session(replies))


def test_service_account_pagination_insert_and_delete_use_google_ids(tmp_path, airports, service_account_auth, capsys):
    from google.auth.transport.requests import Request

    client = api_client([
        (200, {"id": "test@group.calendar.google.com", "summary": "Flighty航班", "timeZone": "Asia/Shanghai"}),
        (200, {"items": [{"id": "first"}], "nextPageToken": "next"}),
        (200, {"items": [{"id": "second"}]}),
        (200, {"id": "serverid"}), (204, None),
    ])
    client.authenticate()
    client.validate_calendar()
    assert [e["id"] for e in client.list_owned()] == ["first", "second"]
    body = next(iter(sync.read_snapshot(write_ics(tmp_path, event()), airports).flights.values())).body
    assert client.create(body)["id"] == "serverid"
    client.delete("serverid")
    calls = client.session.calls
    assert service_account_auth["info"] == SERVICE_ACCOUNT_INFO
    assert set(service_account_auth["scopes"]) == {
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.calendars.readonly",
    }
    refresh_request, = service_account_auth["refresh_requests"]
    assert isinstance(refresh_request, Request)
    assert refresh_request.session is not client.session
    assert all(c[2]["headers"]["Authorization"] == "Bearer private-token" for c in calls)
    assert calls[1][2]["params"]["privateExtendedProperty"] == f"flighty_owner={sync.OWNER}"
    assert "pageToken" not in calls[1][2]["params"]
    assert calls[2][2]["params"]["pageToken"] == "next"
    assert "id" not in calls[3][2]["json"]
    assert calls[4][1].endswith("/events/serverid")
    assert all(c[2]["allow_redirects"] is False for c in calls)
    output = capsys.readouterr()
    assert "private-token" not in output.out + output.err
    assert "never-print-private-key" not in output.out + output.err


@pytest.mark.parametrize("metadata", [
    {"id": "wrong", "summary": "Flighty航班", "timeZone": "Asia/Shanghai"},
    {"id": "test@group.calendar.google.com", "summary": "Personal", "timeZone": "Asia/Shanghai"},
    {"id": "test@group.calendar.google.com", "summary": "Flighty航班", "timeZone": "UTC"},
])
def test_wrong_calendar_or_timezone_fails_before_mutation(metadata):
    client = api_client([(200, metadata)])
    with pytest.raises(sync.SyncError):
        client.validate_calendar()
    assert [c[0] for c in client.session.calls] == ["GET"]


def test_primary_calendar_rejected():
    config = {key: "never-print-secret" for key in sync.REQUIRED_ENV}
    config["FLIGHTY_GOOGLE_CALENDAR_ID"] = "primary"
    with pytest.raises(sync.SyncError):
        sync.GoogleCalendar(config)


@pytest.mark.parametrize("failure", [(403, {"error": "never-print-secret"}), requests.ConnectionError("never-print-secret")])
def test_google_failure_never_modifies_ics_or_leaks_secrets(monkeypatch, capsys, failure, isolated_root, service_account_auth):
    configured_env(monkeypatch)
    client = api_client([failure])
    monkeypatch.setattr(sync, "GoogleCalendar", lambda _: client)
    before = {p: p.read_bytes() for p in isolated_root.glob("*.ics")}
    assert sync.main([]) == 1
    output = capsys.readouterr().out
    assert "FLIGHTY_SYNC=ERROR" in output
    assert "never-print-secret" not in output
    assert all(p.read_bytes() == b for p, b in before.items())


def test_lost_insert_response_recovers_from_remote_persistence(tmp_path, airports):
    client = Calendar()
    snapshot = sync.read_snapshot(write_ics(tmp_path, event()), airports)
    create = client.create

    def lost_response(body):
        create(body)
        raise sync.SyncError("Google transport failure; no automatic write retry")

    client.create = lost_response
    with pytest.raises(sync.SyncError):
        reconcile(client, snapshot)
    next_run = Calendar(client.events.values())
    reconcile(next_run, snapshot)
    assert not next_run.calls
    assert len(next_run.events) == 1


def test_failed_insert_does_not_delete_last_good_mirror(tmp_path, airports):
    client = Calendar()
    reconcile(client, sync.read_snapshot(write_ics(tmp_path, event()), airports))
    source = write_ics(tmp_path, event(number="9C6733"))
    before = source.read_bytes()

    def fail(body):
        raise sync.SyncError("Google POST failed with HTTP 503")

    client.create = fail
    with pytest.raises(sync.SyncError):
        reconcile(client, sync.read_snapshot(source, airports))
    assert source.read_bytes() == before
    assert len(client.events) == 1 and not any(c[0] == "delete" for c in client.calls)


def test_online_dry_run_reads_remote_but_does_not_write(monkeypatch, capsys, isolated_root, service_account_auth):
    configured_env(monkeypatch)
    client = api_client([
        (200, {"id": "test@group.calendar.google.com", "summary": "Flighty航班", "timeZone": "Asia/Shanghai"}),
        (200, {"items": []}),
    ])
    monkeypatch.setattr(sync, "GoogleCalendar", lambda _: client)
    assert sync.main(["--dry-run"]) == 0
    assert "FLIGHTY_SYNC=DRY_RUN" in capsys.readouterr().out
    assert [c[0] for c in client.session.calls] == ["GET", "GET"]


@pytest.mark.parametrize("raw_json", [
    '{"private_key":"never-print-private-key", BROKEN}',
    '[]',
    '{"type":"authorized_user","refresh_token":"never-print-secret"}',
    '{"type":"service_account","private_key":"never-print-private-key"}',
])
def test_invalid_service_account_json_fails_without_leaking_or_writing(raw_json, monkeypatch, capsys, isolated_root):
    configured_env(monkeypatch)
    monkeypatch.setenv("FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON", raw_json)
    before = {p: p.read_bytes() for p in isolated_root.glob("*.ics")}
    assert sync.main([]) == 1
    output = capsys.readouterr()
    assert "FLIGHTY_SYNC=ERROR" in output.out
    for sensitive in (raw_json, "never-print-private-key", "never-print-secret"):
        assert sensitive not in output.out + output.err
    assert all(p.read_bytes() == data for p, data in before.items())


def test_refresh_failure_redacts_private_key_token_and_secret(monkeypatch, capsys, isolated_root, service_account_auth):
    from google.auth.exceptions import RefreshError

    configured_env(monkeypatch)
    service_account_auth["error"] = RefreshError(
        "never-print-private-key private-token never-print-secret " + json.dumps(SERVICE_ACCOUNT_INFO)
    )
    client = api_client([])
    monkeypatch.setattr(sync, "GoogleCalendar", lambda _: client)
    before = {p: p.read_bytes() for p in isolated_root.glob("*.ics")}
    assert sync.main([]) == 1
    output = capsys.readouterr()
    assert "Service account credentials could not be refreshed" in output.out
    for sensitive in ("never-print-private-key", "private-token", "never-print-secret", json.dumps(SERVICE_ACCOUNT_INFO)):
        assert sensitive not in output.out + output.err
    assert not client.session.calls
    assert all(p.read_bytes() == data for p, data in before.items())


def test_refresh_without_token_fails_safely(service_account_auth):
    service_account_auth["token"] = None
    client = api_client([])
    with pytest.raises(sync.SyncError, match="did not return an access token"):
        client.authenticate()
    assert not client.session.calls


def test_legacy_oauth_secrets_do_not_enable_sync(tmp_path, monkeypatch, capsys):
    assert sync.REQUIRED_ENV == ("FLIGHTY_GOOGLE_CALENDAR_ID", "FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON")
    configured_env(monkeypatch)
    monkeypatch.delenv("FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON")
    for old_secret in ("GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET", "GOOGLE_CALENDAR_REFRESH_TOKEN"):
        monkeypatch.setenv(old_secret, "never-print-secret")
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    assert sync.main([]) == 0
    assert capsys.readouterr().out.strip() == "FLIGHTY_SYNC=SKIPPED_NOT_CONFIGURED"


def test_workflow_is_nonblocking_and_requires_completed_ics_pipeline():
    workflow = (ROOT / ".github/workflows/schedule.yml").read_text(encoding="utf-8")
    clean = workflow.split("- name: Clean ICS people lists", 1)[1].split("- name:", 1)[0]
    step = workflow.split("- name: Sync Flighty Google Calendar", 1)[1]
    assert "id: ics_clean" in clean
    for gate in (
        "!cancelled()", "steps.scraper.outcome == 'success'",
        "steps.scraper.outputs.auth_status == 'AUTHENTICATED'",
        "steps.ics_clean.outcome == 'success'", "steps.ics_publish.outcome == 'success'",
        "steps.ics_publish.outputs.publish_status == 'PUBLISHED'",
        "steps.ics_publish.outputs.publish_status == 'NO_CHANGES'",
    ):
        assert gate in step
    assert "continue-on-error: true" in step
    assert "timeout-minutes: 5" in step
    assert "python -B sync_flighty_google_calendar.py" in step
    for key in sync.REQUIRED_ENV:
        assert f"${{{{ secrets.{key} }}}}" in step
    env_block = step.split("env:", 1)[1].split("run:", 1)[0]
    assert len([line for line in env_block.splitlines() if line.strip()]) == 2
    for old_secret in ("GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET", "GOOGLE_CALENDAR_REFRESH_TOKEN"):
        assert old_secret not in step
    assert "github_api_publish.py" not in step
    assert "crew_calendar_email_entry.py" not in step
    assert "CREW_STORAGE_STATE" not in step
    assert workflow.index("calendar_d2_prep_check") < workflow.index("id: flighty_sync")
