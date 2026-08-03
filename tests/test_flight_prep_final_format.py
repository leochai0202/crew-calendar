from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import (
    AmbiguousFlightSelectionError,
    CalendarEvent,
    normalize_airport_experience_records,
    parse_ics,
    select_continuous_flight_group,
    update_airport_experience,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_PDF = (
    REPO_ROOT
    / "knowledge"
    / "pdf"
    / "AirDropManual-机场特点汇总(Airport Information)20260720-Manual.pdf"
)
TARGET = date(2026, 8, 4)
BEIJING = ZoneInfo("Asia/Shanghai")


def _event(
    uid: str,
    number: str,
    departure: str,
    arrival: str,
    start: datetime,
    end: datetime,
) -> CalendarEvent:
    return CalendarEvent(
        uid=uid,
        summary=f"✈️ {number} {departure}→{arrival}",
        start=start,
        end=end,
        description=(
            f"类型：航班\n航班：{number}\n航线：{departure} → {arrival}\n"
            "人员名单：\n• 段洋硕"
        ),
        location=departure,
        properties={},
        source_file="test.ics",
    )


def _write_ics(path: Path, events: list[CalendarEvent]) -> None:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for event in events:
        description = event.description.replace("\\", "\\\\").replace("\n", "\\n")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event.uid}",
                f"SUMMARY:{event.summary}",
                f"DTSTART;TZID=Asia/Shanghai:{event.start:%Y%m%dT%H%M%S}",
                f"DTEND;TZID=Asia/Shanghai:{event.end:%Y%m%dT%H%M%S}",
                f"DESCRIPTION:{description}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_runtime_repo(destination: Path, *, include_pdf: bool = True) -> None:
    (destination / "config").mkdir(parents=True)
    (destination / "knowledge").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "crew_calendar_main.py", destination)
    shutil.copy2(REPO_ROOT / "flight.ics", destination)
    for name in (
        "prep_settings.json",
        "pilot_profile.json",
        "airport_experience.json",
        "airport_supplements.json",
    ):
        shutil.copy2(REPO_ROOT / "config" / name, destination / "config" / name)
    settings_path = destination / "config" / "prep_settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["auto_update_airport_experience"] = False
    settings["include_weather_section"] = False
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(
        REPO_ROOT / "knowledge" / "airport_information_20260615.txt",
        destination / "knowledge" / "airport_information_20260615.txt",
    )
    if include_pdf:
        pdf_dir = destination / "knowledge" / "pdf"
        pdf_dir.mkdir()
        shutil.copy2(REAL_PDF, pdf_dir / REAL_PDF.name)


def test_real_august_four_duty_merges_both_continuous_segments() -> None:
    selected = select_continuous_flight_group(parse_ics(REPO_ROOT / "flight.ics"), TARGET)

    assert [event.flight_number for event in selected] == ["9C8523", "9C8524"]
    duty = agent.DutyContext(tuple(selected))
    assert duty.route == ("上海浦东", "恩施许家坪")
    assert duty.role_map == {
        "上海浦东": ("departure", "arrival"),
        "恩施许家坪": ("departure", "arrival"),
    }


def test_non_continuous_duties_require_manual_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "ambiguous"
    _copy_runtime_repo(repo, include_pdf=False)
    first = _event(
        "a",
        "9C1001",
        "上海浦东",
        "广州白云",
        datetime(2026, 8, 4, 7, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 9, 0, tzinfo=BEIJING),
    )
    second = _event(
        "b",
        "9C1002",
        "西安咸阳",
        "上海虹桥",
        datetime(2026, 8, 4, 15, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 17, 0, tzinfo=BEIJING),
    )
    _write_ics(repo / "flight.ics", [first, second])

    with pytest.raises(AmbiguousFlightSelectionError):
        select_continuous_flight_group([first, second], TARGET)

    monkeypatch.setattr(
        sys,
        "argv",
        ["flight_prep_agent.py", "--repo", str(repo), "--target-date", "2026-08-04"],
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert agent.main() == 2
    meta = json.loads(
        (repo / "flight_preparation" / "latest_meta.json").read_text(encoding="utf-8")
    )
    assert meta["status"] == "NEEDS_SELECTION"
    assert "需要人工指定" in meta["message"]
    assert not (repo / "flight_preparation" / "latest.txt").exists()


def test_weather_numbers_are_not_misread_as_visibility() -> None:
    decoded = agent.decode_weather_report(
        "TAF ZSPD 030500Z 0306/0412 18005MPS 9999 SCT020 "
        "Q1006 TX32/0307Z TN25/0321Z"
    )

    assert "能见度10公里以上" in decoded
    for false_value in ("能见度305米", "能见度306米", "能见度1006米", "能见度307米"):
        assert false_value not in decoded
    assert "CAVOK" in agent.decode_weather_report("METAR ZSPD 030500Z CAVOK Q1006")
    assert "能见度800米" in agent.decode_weather_report("METAR ZSPD 030500Z 0800 BR")
    assert "能见度约805米" in agent.decode_weather_report("METAR KJFK 030500Z 1/2SM BR")


def test_taf_change_groups_apply_only_to_each_operational_time() -> None:
    taf = (
        "TAF ZSPD 030500Z 0306/0412 18005MPS 9999 SCT020 "
        "TEMPO 0307/0309 2000 TSRA BKN010 "
        "FM031000 24005MPS 9999 SCT030"
    )
    before = datetime(2026, 8, 3, 14, 30, tzinfo=BEIJING)
    during = datetime(2026, 8, 3, 15, 30, tzinfo=BEIJING)
    after = datetime(2026, 8, 3, 19, 0, tzinfo=BEIJING)

    assert "雷雨" not in agent.decode_taf_for_time(taf, before)
    assert "雷雨" in agent.decode_taf_for_time(taf, during)
    assert "能见度2000米" in agent.decode_taf_for_time(taf, during)
    assert "雷雨" not in agent.decode_taf_for_time(taf, after)

    cross_day = (
        "TAF ZSPD 312300Z 3123/0108 9999 SCT020 "
        "PROB30 TEMPO 0102/0104 2000 TSRA BKN010"
    )
    cross_day_time = datetime(2026, 8, 1, 10, 30, tzinfo=BEIJING)
    assert "雷雨" in agent.decode_taf_for_time(cross_day, cross_day_time)

    becoming = (
        "TAF ZSPD 030500Z 0306/0412 9999 SCT020 "
        "BECMG 0308/0310 3000 BR BKN008"
    )
    before_becoming = datetime(2026, 8, 3, 15, 0, tzinfo=BEIJING)
    during_becoming = datetime(2026, 8, 3, 17, 0, tzinfo=BEIJING)
    assert "能见度3000米" not in agent.decode_taf_for_time(becoming, before_becoming)
    assert "能见度3000米" in agent.decode_taf_for_time(becoming, during_becoming)


def test_each_repeated_airport_time_is_evaluated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    taf = (
        "TAF ZSPD 030500Z 0306/0412 9999 SCT020 "
        "TEMPO 0307/0309 2000 TSRA BKN010"
    )
    first = _event(
        "one",
        "9C1001",
        "上海浦东",
        "恩施许家坪",
        datetime(2026, 8, 3, 14, 30, tzinfo=BEIJING),
        datetime(2026, 8, 3, 15, 0, tzinfo=BEIJING),
    )
    second = _event(
        "two",
        "9C1002",
        "恩施许家坪",
        "上海浦东",
        datetime(2026, 8, 3, 15, 10, tzinfo=BEIJING),
        datetime(2026, 8, 3, 15, 30, tzinfo=BEIJING),
    )
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(
            icao="ZSPD", metar="", taf=taf, error=""
        ),
    )
    sentence, _, metadata = agent.weather_risk_sentence(
        ["上海浦东"],
        {"上海浦东": "ZSPD"},
        1,
        target=date(2026, 8, 3),
        flights=[first, second],
    )

    decoded = metadata["上海浦东"]["taf_decoded_by_time"]
    assert len(decoded) == 2
    assert "雷雨" not in decoded[0]["decoded"]
    assert "雷雨" in decoded[1]["decoded"]
    assert "雷雨" in sentence


def test_airport_experience_migrates_known_pollution_and_ignores_future() -> None:
    normalized, changes = normalize_airport_experience_records(
        {
            "西宁": {"last_operated": "2026-04-09"},
            "西宁曹家堡": {"last_operated": "2026-07-27"},
            "曹家堡上海虹桥": {"last_operated": "2026-04-09"},
            "石家": {"last_operated": "2026-04-18"},
            "庄正定泉州晋江": {"last_operated": "2026-04-18"},
            "ZYTL": {"last_operated": "2026-06-30"},
            "ZSYA": {"last_operated": "2026-06-30"},
        }
    )
    assert normalized["西宁曹家堡"]["last_operated"] == "2026-07-27"
    assert normalized["上海虹桥"]["last_operated"] == "2026-04-09"
    assert normalized["石家庄正定"]["last_operated"] == "2026-04-18"
    assert normalized["泉州晋江"]["last_operated"] == "2026-04-18"
    assert normalized["大连周水子"]["last_operated"] == "2026-06-30"
    assert normalized["扬州泰州"]["last_operated"] == "2026-06-30"
    assert changes

    future = _event(
        "future",
        "9C9999",
        "上海浦东",
        "恩施许家坪",
        datetime(2026, 8, 4, 7, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 9, 0, tzinfo=BEIJING),
    )
    updated, _ = update_airport_experience(
        [future],
        {"airports": {}},
        as_of=datetime(2026, 8, 3, 12, 0, tzinfo=BEIJING),
    )
    assert updated["airports"] == {}


@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含20260720机场手册PDF")
def test_real_august_four_final_confirmed_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    original_hash = hashlib.sha256((REPO_ROOT / "flight.ics").read_bytes()).hexdigest()
    repo = tmp_path / "real-august-four"
    _copy_runtime_repo(repo)
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(icao="", metar="", taf="", error=""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["flight_prep_agent.py", "--repo", str(repo), "--target-date", "2026-08-04"],
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    agent.extract_pdf_text.cache_clear()

    assert agent.main() == 0

    output = repo / "flight_preparation"
    content = (output / "latest.txt").read_text(encoding="utf-8")
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))
    assert content.startswith("我是来自飞行十五中队的副驾驶段洋硕")
    intro = content.split("\n\n", 1)[0]
    assert "A320" not in intro
    assert "近期机场经历" not in content
    assert "近期注意点" not in content
    assert "最新有效PIB/NOTAM以航前放行资料为准" in content
    assert "•" not in content
    assert "None" not in content and "null" not in content
    assert (
        "上一次作为PF教员评价：RNP进近五边速度180节时注意形态二，"
        "入口前关注飞机状态；作为PM机长评价：增加SOP熟练度，"
        "标准喊话声音大一些。"
    ) in content
    assert "上海浦东机场典型不安全事件：\n1." in content
    assert "恩施许家坪机场典型不安全事件：\n1." in content
    assert content.count("核心威胁：") == 1
    core = content.split("核心威胁：", 1)[1]
    assert core.index("上海浦东机场：") < core.index("恩施许家坪机场：")
    assert not re.search(r"(?m)^\d+[.、]", core)
    assert "\n\n" in core.split("上海浦东机场：", 1)[1].split("恩施许家坪机场：", 1)[0]
    assert "\n\n" in core.split("恩施许家坪机场：", 1)[1]
    for raw_heading in (
        "常用程序：",
        "指挥特点：",
        "注意事项：",
        "气象特点：",
        "道面特点：",
        "其他威胁：",
        "运行特点：",
    ):
        assert raw_heading not in content

    assert meta["flight_numbers"] == ["9C8523", "9C8524"]
    assert meta["airports"] == ["上海浦东", "恩施许家坪"]
    assert meta["airport_information_version"] == 20260720
    assert meta["airport_information_type"] == "PDF"
    assert meta["foreign_crew_detected"] is False
    assert meta["english_confirmation_required"] is False
    assert meta["english_generated"] is False
    assert not (output / "latest_en.txt").exists()
    assert not (output / "2026-08-04_航前准备_详细版.txt").exists()
    assert hashlib.sha256((REPO_ROOT / "flight.ics").read_bytes()).hexdigest() == original_hash
