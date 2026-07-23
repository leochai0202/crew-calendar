from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from crew_agents.ics_utils import (
    AmbiguousFlightSelectionError,
    FlightSelectionError,
    events_for_date,
    has_latin_crew_name,
    parse_ics,
    select_exact_flight_event,
    strip_crew_role_markers,
    update_airport_experience,
)


def test_parse_multi_segment_and_people(tmp_path: Path):
    ics = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:a\r
SUMMARY:✈️ 9C6391 上海浦东→威海大水泊\r
DTSTART;TZID=Asia/Shanghai:20260529T094500\r
DTEND;TZID=Asia/Shanghai:20260529T114500\r
DESCRIPTION:05月29日 周五\\n类型：航班\\n航班：9C6391\\n航线：上海浦东 → 威海大水泊\\n签到：07:55｜上海浦东\\n机型：A320｜注册号：B6971\\n人员名单：\\n• 陈飞(T2\\,R)\\n• 段洋硕\r
LOCATION:上海浦东\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:b\r
SUMMARY:✈️ 9C8981 上海浦东→大连周水子(+1)\r
DTSTART;TZID=Asia/Shanghai:20260529T225000\r
DTEND;TZID=Asia/Shanghai:20260530T005500\r
DESCRIPTION:签到：21:00｜上海浦东\\n人员名单：\\n• 段洋硕\r
END:VEVENT\r
END:VCALENDAR\r
"""
    path = tmp_path / "flight.ics"
    path.write_text(ics, encoding="utf-8")
    events = parse_ics(path)
    assert len(events) == 2
    assert events[0].flight_number == "9C6391"
    assert events[0].route == ("上海浦东", "威海大水泊")
    assert events[0].checkin == "07:55｜上海浦东"
    assert "陈飞(T2,R)" in events[0].people
    assert events[1].end.date().isoformat() == "2026-05-30"
    assert len(events_for_date(events, events[0].start.date())) == 2


def test_airport_experience_only_completed_flights(tmp_path: Path):
    ics = """BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:a\nSUMMARY:✈️ 9C6391 上海浦东→大连周水子\nDTSTART;TZID=Asia/Shanghai:20260601T100000\nDTEND;TZID=Asia/Shanghai:20260601T120000\nDESCRIPTION:类型：航班\nEND:VEVENT\nBEGIN:VEVENT\nUID:b\nSUMMARY:🧳 置位 9C6392 大连周水子→上海浦东\nDTSTART;TZID=Asia/Shanghai:20260602T100000\nDTEND;TZID=Asia/Shanghai:20260602T120000\nDESCRIPTION:类型：置位\nEND:VEVENT\nEND:VCALENDAR\n"""
    path = tmp_path / "flight.ics"
    path.write_text(ics, encoding="utf-8")
    events = parse_ics(path)
    updated, changes = update_airport_experience(
        events,
        {"airports": {}},
        as_of=datetime(2026, 6, 3, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert updated["airports"]["上海浦东"]["last_operated"] == "2026-06-01"
    assert updated["airports"]["大连周水子"]["last_operated"] == "2026-06-01"
    assert changes


def test_exact_flight_selection_uses_date_number_and_both_airports(tmp_path: Path):
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:first
SUMMARY:✈️ 9C1001 上海浦东→广州白云
DTSTART;TZID=Asia/Shanghai:20260723T080000
DTEND;TZID=Asia/Shanghai:20260723T103000
DESCRIPTION:类型：航班\\n航班：9C1001\\n航线：上海浦东 → 广州白云\\n人员名单：\\n• 同日其他人(R)
END:VEVENT
BEGIN:VEVENT
UID:target
SUMMARY:✈️ 9C8552 新加坡樟宜→上海浦东
DTSTART;TZID=Asia/Shanghai:20260723T061500
DTEND;TZID=Asia/Shanghai:20260723T114000
DESCRIPTION:类型：航班\\n航班：9C8552\\n航线：新加坡樟宜 → 上海浦东\\n人员名单：\\n• MARQUES SANTANNA HELIO(R)\\n• 左争世(R)\\n• 段洋硕\\n• 罗一敏(B)
END:VEVENT
END:VCALENDAR
"""
    path = tmp_path / "flight.ics"
    path.write_text(ics, encoding="utf-8")

    event = select_exact_flight_event(
        parse_ics(path),
        datetime(2026, 7, 23).date(),
        flight_number="9C8552",
        departure="新加坡樟宜",
        arrival="上海浦东",
    )

    assert event.uid == "target"
    assert event.people == [
        "MARQUES SANTANNA HELIO(R)",
        "左争世(R)",
        "段洋硕",
        "罗一敏(B)",
    ]
    assert "同日其他人(R)" not in event.people
    with pytest.raises(AmbiguousFlightSelectionError):
        select_exact_flight_event(
            parse_ics(path),
            datetime(2026, 7, 23).date(),
        )
    with pytest.raises(FlightSelectionError):
        select_exact_flight_event(
            parse_ics(path),
            datetime(2026, 7, 23).date(),
            flight_number="9C8552",
            departure="新加坡樟宜",
            arrival="上海虹桥",
        )


def test_exact_flight_selection_rejects_ambiguous_duplicates(tmp_path: Path):
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:a
SUMMARY:✈️ 9C8552 新加坡樟宜→上海浦东
DTSTART;TZID=Asia/Shanghai:20260723T061500
DTEND;TZID=Asia/Shanghai:20260723T114000
DESCRIPTION:类型：航班
END:VEVENT
BEGIN:VEVENT
UID:b
SUMMARY:✈️ 9C8552 新加坡樟宜→上海浦东
DTSTART;TZID=Asia/Shanghai:20260723T061600
DTEND;TZID=Asia/Shanghai:20260723T114100
DESCRIPTION:类型：航班
END:VEVENT
END:VCALENDAR
"""
    path = tmp_path / "flight.ics"
    path.write_text(ics, encoding="utf-8")

    with pytest.raises(AmbiguousFlightSelectionError):
        select_exact_flight_event(
            parse_ics(path),
            datetime(2026, 7, 23).date(),
            flight_number="9C8552",
            departure="新加坡樟宜",
            arrival="上海浦东",
        )


def test_foreign_name_detection_strips_role_markers_only():
    assert strip_crew_role_markers("左争世(R)") == "左争世"
    assert strip_crew_role_markers("罗一敏(B)") == "罗一敏"
    assert strip_crew_role_markers("陈飞(T2,R)") == "陈飞"
    assert not has_latin_crew_name("左争世(R)")
    assert not has_latin_crew_name("罗一敏(B)")
    assert has_latin_crew_name("MARQUES SANTANNA HELIO(R)")
