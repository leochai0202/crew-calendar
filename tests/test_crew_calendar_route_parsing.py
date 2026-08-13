import json
from datetime import datetime

import pytest

import crew_calendar_main as calendar


HEADER = "08月17日 周一"


@pytest.fixture(autouse=True)
def _airport_indexes() -> None:
    calendar.rebuild_airport_indexes()


def _card(route: str = "") -> str:
    route_line = f"\n{route}" if route else ""
    return (
        "9C7021\nB6667\nA320\n"
        "19:45 上海浦东 航班动态"
        f"{route_line}\n21:35 - 00:05\n"
        "人员名单：\n段洋硕"
    )


def test_detail_ready_complete_chinese_route_is_extracted() -> None:
    item = calendar.parse_flight_card(
        _card("上海浦东→沈阳桃仙"), HEADER, 2026, _card("上海浦东→沈阳桃仙")
    )

    assert (item["dep"], item["arr"]) == ("ZSPD", "ZYTX")
    assert (item["dep_cn"], item["arr_cn"]) == ("上海浦东", "沈阳桃仙")
    assert item["route_parse_failed"] is False


def test_route_split_across_explicit_dom_fields_is_extracted() -> None:
    card = {
        "text": _card(),
        "route_fields": [
            {"label": "departure-airport", "value": "上海浦东"},
            {"label": "arrival-airport", "value": "沈阳桃仙"},
        ],
    }
    text = calendar.detail_card_parse_text(card)
    dep, arr, dep_cn, arr_cn, diagnostics = calendar.extract_airports_with_diagnostics(
        text, text, "9C7021", checkin_place="上海浦东"
    )

    assert (dep, arr, dep_cn, arr_cn) == (
        "ZSPD",
        "ZYTX",
        "上海浦东",
        "沈阳桃仙",
    )
    assert diagnostics["final_stage"] == "detail_card_route"


def test_prepare_items_uses_explicit_dom_route_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    card = {
        "text": _card(),
        "route_fields": [
            {"label": "departure-airport", "value": "上海浦东"},
            {"label": "arrival-airport", "value": "沈阳桃仙"},
        ],
    }

    items = calendar.prepare_items(
        [{"day_header": HEADER, "day_block": _card(), "cards": [card]}],
        2026,
    )

    flights = [item for item in items if item.get("flight_no") == "9C7021"]
    assert len(flights) == 1
    assert (flights[0]["dep_cn"], flights[0]["arr_cn"]) == (
        "上海浦东",
        "沈阳桃仙",
    )
    assert flights[0]["route_parse_failed"] is False


def test_detail_ready_icao_pair_keeps_reliable_icao_priority() -> None:
    text = _card("ZSPD\nZYTX")
    dep, arr, dep_cn, arr_cn, diagnostics = calendar.extract_airports_with_diagnostics(
        text, text, "9C7021", checkin_place="上海浦东"
    )

    assert (dep, arr, dep_cn, arr_cn) == (
        "ZSPD",
        "ZYTX",
        "上海浦东",
        "沈阳桃仙",
    )
    assert diagnostics["final_stage"] == "reliable_icao_pair"


def test_checkin_airport_only_disambiguates_two_confirmed_endpoints() -> None:
    text = _card("沈阳桃仙\n上海浦东")
    route, _ = calendar.extract_detail_card_route(text, checkin_place="上海浦东")

    assert route == ("ZSPD", "ZYTX", "上海浦东", "沈阳桃仙")


def test_checkin_airport_alone_never_invents_destination() -> None:
    route, diagnostics = calendar.extract_detail_card_route(
        _card(), checkin_place="上海浦东"
    )

    assert route == ("", "", "", "")
    assert diagnostics[-1]["candidate_count"] == 1


def test_historical_flight_number_never_fills_current_route(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(calendar.ROUTE_DIAGNOSTIC_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(calendar, "existing_last_good_route_for_task", lambda *args: True)

    item = calendar.parse_flight_card(_card(), HEADER, 2026, _card())

    assert item["flight_no"] == "9C7021"
    assert item["dep"] == item["arr"] == ""
    assert item["dep_cn"] == item["arr_cn"] == ""
    assert item["preserve_last_good_date"] is True


def test_route_parse_failure_writes_sanitized_diagnostic(monkeypatch, tmp_path, caplog) -> None:
    monkeypatch.setenv(calendar.ROUTE_DIAGNOSTIC_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(calendar, "existing_last_good_route_for_task", lambda *args: False)
    caplog.set_level("WARNING")

    item = calendar.parse_flight_card(_card(), HEADER, 2026, _card())
    diagnostic = tmp_path / "route_parse_failed_20260817_9C7021.txt"
    payload = json.loads(diagnostic.read_text(encoding="utf-8"))

    assert item["route_parse_failed"] is True
    assert item["preserve_last_good_date"] is False
    assert payload["status"] == "ROUTE_PARSE_FAILED"
    assert payload["flight_no"] == "9C7021"
    assert payload["detected_icao_candidates"] == []
    assert "段洋硕" not in payload["sanitized_card_text"]
    assert "ROUTE_PARSE_FAILED_NO_LAST_GOOD_DATA" in caplog.text


def test_last_good_route_protects_whole_date_from_partial_replacement() -> None:
    protected = {
        "start_dt": datetime(2026, 8, 17, 21, 35),
        "preserve_last_good_date": True,
    }
    same_date_complete = {
        "start_dt": datetime(2026, 8, 17, 10, 0),
        "preserve_last_good_date": False,
    }
    other_date = {
        "start_dt": datetime(2026, 8, 18, 10, 0),
        "preserve_last_good_date": False,
    }

    kept, protected_dates = calendar.exclude_dates_protected_by_last_good_route(
        [protected, same_date_complete, other_date]
    )

    assert protected_dates == {"20260817"}
    assert kept == [other_date]


@pytest.mark.parametrize(
    ("flight_no", "route", "expected"),
    [
        ("9C7115", "上海浦东 丽江三义", ("上海浦东", "丽江三义")),
        ("9C7116", "丽江三义—上海浦东", ("丽江三义", "上海浦东")),
    ],
)
def test_august_fourteen_routes_do_not_regress(flight_no, route, expected) -> None:
    text = (
        f"{flight_no}\nB32KS\nA320\n11:55 上海浦东 航班动态\n"
        f"{route}\n13:45 - 17:35"
    )
    parsed, _ = calendar.extract_detail_card_route(text, checkin_place=expected[0])

    assert parsed[2:] == expected


def test_schedule_uploads_route_diagnostic_only_from_failure_glob() -> None:
    workflow = (
        calendar.Path(".github/workflows/schedule.yml").read_text(encoding="utf-8")
    )

    assert "crew-route-diagnostic-${{ github.run_id }}" in workflow
    assert "debug_output/route_parse_failed_*.txt" in workflow
    assert "debug_output/route_parse_failed_*.png" in workflow
    assert "if-no-files-found: ignore" in workflow
