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
REAL_PDF_CANDIDATES = sorted(
    (REPO_ROOT / "knowledge" / "pdf").glob(
        "*机场特点汇总(Airport Information)*.pdf"
    )
)
REAL_PDF = REAL_PDF_CANDIDATES[-1] if REAL_PDF_CANDIDATES else Path("missing.pdf")
REAL_PDF_VERSION = agent.manual_version(REAL_PDF) if REAL_PDF.exists() else 0
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


@pytest.mark.parametrize(
    "numbers",
    [
        ("9C7605", "9C7606"),
        ("9C7606", "9C7605"),
        ("9C7605X", "9C7606Y"),
    ],
)
def test_consecutive_main_numbers_remain_one_prep_group(
    numbers: tuple[str, str],
) -> None:
    first = _event(
        "first",
        numbers[0],
        "上海浦东",
        "桂林两江",
        datetime(2026, 8, 11, 6, 0, tzinfo=BEIJING),
        datetime(2026, 8, 11, 8, 0, tzinfo=BEIJING),
    )
    second = _event(
        "second",
        numbers[1],
        "桂林两江",
        "扬州泰州",
        datetime(2026, 8, 11, 9, 0, tzinfo=BEIJING),
        datetime(2026, 8, 11, 11, 0, tzinfo=BEIJING),
    )

    groups = agent.split_flight_prep_groups_by_flight_number([first, second])

    assert [[event.flight_number for event in group] for group in groups] == [
        list(numbers)
    ]


def test_nonconsecutive_main_numbers_split_prep_reports() -> None:
    first = _event(
        "first",
        "9C6809",
        "沈阳桃仙",
        "桂林两江",
        datetime(2026, 8, 11, 6, 50, tzinfo=BEIJING),
        datetime(2026, 8, 11, 10, 40, tzinfo=BEIJING),
    )
    second = _event(
        "second",
        "9C7080",
        "桂林两江",
        "扬州泰州",
        datetime(2026, 8, 11, 11, 25, tzinfo=BEIJING),
        datetime(2026, 8, 11, 13, 45, tzinfo=BEIJING),
    )

    groups = agent.split_flight_prep_groups_by_flight_number([first, second])

    assert [[event.flight_number for event in group] for group in groups] == [
        ["9C6809"],
        ["9C7080"],
    ]
    assert agent.DutyContext(tuple(groups[0])).route == ("沈阳桃仙", "桂林两江")
    assert agent.DutyContext(tuple(groups[1])).route == ("桂林两江", "扬州泰州")


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
    probability = agent.decode_taf_for_time(cross_day, cross_day_time)
    assert "30%概率短时雷雨" in probability
    assert "雷雨" not in probability

    becoming = (
        "TAF ZSPD 030500Z 0306/0412 9999 SCT020 "
        "BECMG 0308/0310 3000 BR BKN008"
    )
    before_becoming = datetime(2026, 8, 3, 15, 0, tzinfo=BEIJING)
    during_becoming = datetime(2026, 8, 3, 17, 0, tzinfo=BEIJING)
    assert "能见度3000米" not in agent.decode_taf_for_time(becoming, before_becoming)
    assert "能见度3000米" in agent.decode_taf_for_time(becoming, during_becoming)

    improving = (
        "TAF ZSPD 030500Z 0306/0412 3000 BR BKN008 "
        "BECMG 0308/0310 9999 SCT020"
    )
    after_improving = datetime(2026, 8, 3, 18, 30, tzinfo=BEIJING)
    improved = agent.decode_taf_for_time(improving, after_improving)
    assert "能见度3000米" not in improved
    assert "能见度10公里以上" in improved


def test_weather_fallback_is_named_for_each_uncovered_airport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _event(
        "one",
        "9C1001",
        "上海浦东",
        "恩施许家坪",
        datetime(2026, 8, 4, 7, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 9, 30, tzinfo=BEIJING),
    )
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(
            icao="", metar="", taf="", error="weather unavailable"
        ),
    )

    sentence, _, _ = agent.weather_risk_sentence(
        ["上海浦东", "恩施许家坪"],
        {"上海浦东": "ZSPD", "恩施许家坪": "ZHES"},
        1,
        target=TARGET,
        flights=[first],
    )

    assert sentence == (
        "上海浦东机场航班时段天气以航前最新TAF/METAR及放行资料为准。"
        "恩施许家坪机场航班时段天气以航前最新TAF/METAR及放行资料为准。"
    )


def test_personal_risk_does_not_repeat_first_core_fact() -> None:
    first = _event(
        "one",
        "9C1001",
        "上海浦东",
        "恩施许家坪",
        datetime(2026, 8, 4, 7, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 9, 0, tzinfo=BEIJING),
    )
    second = _event(
        "two",
        "9C1002",
        "恩施许家坪",
        "上海浦东",
        datetime(2026, 8, 4, 10, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 12, 0, tzinfo=BEIJING),
    )
    sentinel = agent.BilingualFact(
        "sentinel",
        "不应重复到个人风险的机场核心事实",
        "Core fact that must not be repeated in personal risks",
        airport="上海浦东",
    )

    text = agent.duty_risk_text(
        agent.DutyContext((first, second)),
        [{"airport": "恩施许家坪", "within": False}],
        {"上海浦东": [sentinel], "恩施许家坪": []},
        "上海浦东机场航班时段天气以航前最新TAF/METAR及放行资料为准。",
    )

    assert "不应重复到个人风险的机场核心事实" not in text
    assert "2段连续任务" in text
    assert "近3个月未运行过恩施许家坪机场" in text
    assert "最新有效PIB/NOTAM" in text


def test_english_typical_events_are_not_truncated() -> None:
    event = _event(
        "one",
        "9C1001",
        "上海浦东",
        "恩施许家坪",
        datetime(2026, 8, 4, 7, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 9, 0, tzinfo=BEIJING),
    )
    airports = ["上海浦东", "恩施许家坪"]
    typical = {
        airport: [
            agent.BilingualFact(
                f"{airport}-{index}",
                f"事件{index}",
                f"Event {index}",
                airport=airport,
            )
            for index in range(1, 7)
        ]
        for airport in airports
    }
    core = {
        airport: [
            agent.BilingualFact(
                f"{airport}-core",
                "核心事实",
                "Core fact",
                airport=airport,
            )
        ]
        for airport in airports
    }
    profile = json.loads(
        (REPO_ROOT / "config" / "pilot_profile.json").read_text(encoding="utf-8")
    )

    content = agent.render_english_briefing(
        event,
        TARGET,
        profile,
        [],
        typical,
        core,
    )

    assert content.count("Event 6.") == 2
    assert "6. Event 6." not in content


def test_structurally_complete_briefing_has_no_length_floor() -> None:
    event = _event(
        "one",
        "9C1001",
        "上海浦东",
        "恩施许家坪",
        datetime(2026, 8, 4, 7, 0, tzinfo=BEIJING),
        datetime(2026, 8, 4, 9, 0, tzinfo=BEIJING),
    )
    content = (
        "我是来自飞行十五中队的副驾驶段洋硕。\n\n"
        "上海浦东机场典型不安全事件：\n事件。\n\n"
        "恩施许家坪机场典型不安全事件：\n事件。\n\n"
        "核心威胁：\n\n"
        "上海浦东机场：\n来源事实。\n\n"
        "恩施许家坪机场：\n来源事实。\n"
    )

    assert len(content) < 700
    assert agent.validate_content(
        content,
        event,
        {"name": "段洋硕"},
        ["上海浦东", "恩施许家坪"],
        language="zh",
    ) == []


def test_source_semantics_preserve_controls_without_airport_special_cases() -> None:
    def record(airport: str, fact_id: str, text: str) -> dict[str, object]:
        return {
            "airport": airport,
            "fact_id": fact_id,
            "source_file": "knowledge/test-airport-manual.pdf",
            "source": "PDF",
            "source_page": "10",
            "source_heading": f"{airport}运行特点",
            "source_section": "核心威胁",
            "operational_phase": "landing",
            "airport_specific": True,
            "category": "core",
            "text_zh": text,
            "text_en": "",
        }

    distance_airport = "测试甲机场"
    terrain_airport = "测试乙机场"
    taxi_airport = "测试丙机场"
    records = [
        record(
            distance_airport,
            "distance-control",
            "跑道两头均有跑道入口内移，01和19号的实际着陆可用距离为"
            "2410米和2350米，应使用中档刹车。",
        ),
        record(
            distance_airport,
            "landing-restriction",
            "19号跑道只能用于起飞，禁止进近及着陆。",
        ),
        record(
            terrain_airport,
            "terrain-control",
            "机场北侧地形复杂，必须严格按程序飞行。",
        ),
        record(
            taxi_airport,
            "taxi-control",
            "滑行道宽度较窄，需严格控制滑行速度。",
        ),
    ]

    distance_facts = agent.source_record_facts(
        distance_airport, records, category="core"
    )
    distance = next(fact for fact in distance_facts if fact.fact_id == "distance-control")
    assert "01号跑道入口内移" in distance.zh
    assert "实际着陆可用距离为2410米" in distance.zh
    assert "应使用中档刹车" in distance.zh
    assert "19号" not in distance.zh and "2350米" not in distance.zh
    assert distance.excluded_source_clauses
    assert distance.exclusion_reasons
    assert agent.validate_source_semantic_preservation(distance) == []
    assert all(fact.airport == agent.canonical_airport_name(distance_airport) for fact in distance_facts)
    assert all("地形复杂" not in fact.zh for fact in distance_facts)
    assert all("滑行道宽度" not in fact.zh for fact in distance_facts)

    terrain = agent.source_record_facts(
        terrain_airport, records, category="core"
    )[0]
    assert "机场北侧地形复杂" in terrain.zh
    assert "必须严格按程序飞行" in terrain.zh
    assert agent.validate_source_semantic_preservation(terrain) == []

    taxi = agent.source_record_facts(taxi_airport, records, category="core")[0]
    assert "滑行道宽度较窄" in taxi.zh
    assert "需严格控制滑行速度" in taxi.zh
    assert agent.validate_source_semantic_preservation(taxi) == []

    no_measure = agent.source_record_facts(
        "测试丁机场",
        [record("测试丁机场", "no-measure", "滑行道宽度为18米。")],
        category="core",
    )[0]
    assert no_measure.zh == "滑行道宽度为18米。"
    assert no_measure.mitigation == ()
    assert not any(token in no_measure.zh for token in ("应", "建议", "注意", "需"))


def test_source_semantic_validation_detects_removed_measure() -> None:
    fact = agent.BilingualFact(
        "removed-measure",
        "01号跑道实际着陆可用距离为2410米。",
        "",
        airport="测试甲机场",
        source_file="knowledge/test-airport-manual.pdf",
        source="PDF",
        source_page="10",
        source_heading="测试甲机场运行特点",
        source_section="核心威胁",
        category="core",
        source_text_zh=(
            "01号跑道实际着陆可用距离为2410米，应使用中档刹车。"
        ),
        operational_condition=("01号跑道实际着陆可用距离为2410米",),
        applicability=("01号跑道", "着陆"),
        mitigation=("应使用中档刹车",),
    )

    errors = agent.validate_source_semantic_preservation(fact)
    assert any("中档刹车" in error for error in errors)
    assert any("控制措施" in error for error in errors)


def test_source_reference_is_removed_but_operational_fact_is_preserved() -> None:
    record = {
        "airport": "测试机场",
        "fact_id": "complex-airport-category",
        "source_file": "knowledge/test-airport-manual.pdf",
        "source": "PDF",
        "source_page": "10",
        "source_heading": "测试机场运行特点",
        "source_section": "核心威胁",
        "operational_phase": "unspecified",
        "airport_specific": True,
        "category": "core",
        "text_zh": (
            "机场分类：一类操纵复杂机场"
            "（请参考 EFB中机场特点汇总- 复杂机场操作权限规则）。"
        ),
        "text_en": "",
    }

    fact = agent.source_record_facts("测试机场", [record], category="core")[0]

    assert fact.zh == "机场分类：一类操纵复杂机场。"
    assert "参考" not in fact.zh
    assert "EFB" not in fact.zh
    assert "机场特点汇总-" not in fact.zh
    assert any("参考 EFB" in clause for clause in fact.excluded_source_clauses)
    assert "资料交叉引用不进入运行正文" in fact.exclusion_reasons
    assert agent.validate_source_semantic_preservation(fact) == []


def _quality_record(
    airport: str,
    fact_id: str,
    text: str,
    *,
    phase: str = "unspecified",
    category: str = "core",
) -> dict[str, object]:
    return {
        "airport": airport,
        "fact_id": fact_id,
        "source_file": agent.AIRPORT_MANUAL_FILE,
        "source": "PDF",
        "source_page": "10",
        "source_heading": f"{airport}运行特点",
        "source_section": f"{airport}／核心威胁",
        "operational_phase": phase,
        "airport_specific": True,
        "category": category,
        "text_zh": text,
        "text_en": "",
    }


def _quality_duty(
    airport: str = "测试机场",
    flight_number: str = "9C6499",
) -> agent.DutyContext:
    outbound = _event(
        "quality-out",
        flight_number,
        airport,
        "另一测试机场",
        datetime(2026, 8, 8, 10, 0, tzinfo=BEIJING),
        datetime(2026, 8, 8, 12, 0, tzinfo=BEIJING),
    )
    inbound = _event(
        "quality-in",
        "9C6500",
        "另一测试机场",
        airport,
        datetime(2026, 8, 8, 13, 0, tzinfo=BEIJING),
        datetime(2026, 8, 8, 15, 0, tzinfo=BEIJING),
    )
    return agent.DutyContext((outbound, inbound))


@pytest.mark.parametrize("season", ["冬季", "冬春季"])
def test_august_excludes_winter_scoped_fact(season: str) -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [_quality_record("测试机场", "seasonal", f"{season}大风明显。")],
        category="core",
    )[0]
    exclusions: list[dict[str, object]] = []

    selected = agent.filter_fact_for_duty(
        fact,
        _quality_duty(),
        date(2026, 8, 8),
        exclusions,
    )

    assert selected is None
    assert exclusions and "不在资料明确季节适用月份" in str(exclusions[0]["reason"])


def test_season_mapping_and_explicit_month_ranges_are_centralized() -> None:
    assert agent.SEASON_MONTHS["春季"] == (3, 4, 5)
    assert agent.SEASON_MONTHS["夏季"] == (6, 7, 8)
    assert agent.SEASON_MONTHS["秋季"] == (9, 10, 11)
    assert agent.SEASON_MONTHS["冬季"] == (12, 1, 2)
    assert agent.SEASON_MONTHS["冬春季"] == (12, 1, 2, 3, 4, 5)
    assert agent.detected_season_scope("1—4月执行限制") == (1, 2, 3, 4)
    assert agent.detected_season_scope("5至9月执行限制") == (5, 6, 7, 8, 9)


def test_january_excludes_summer_scoped_fact() -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [_quality_record("测试机场", "summer", "夏季雷雨频繁。")],
        category="core",
    )[0]

    assert agent.filter_fact_for_duty(
        fact,
        _quality_duty(),
        date(2026, 1, 8),
        [],
    ) is None


def test_mixed_annual_and_seasonal_clause_keeps_annual_fact() -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [
            _quality_record(
                "测试机场",
                "mixed-season",
                "全年需核对最低安全高度，冬季需关注结冰。",
            )
        ],
        category="core",
    )[0]

    selected = agent.filter_fact_for_duty(
        fact,
        _quality_duty(),
        date(2026, 8, 8),
        [],
    )

    assert selected is not None
    assert "全年需核对最低安全高度" in selected.zh
    assert "冬季" not in selected.zh and "结冰" not in selected.zh
    assert any("冬季" in clause for clause in selected.excluded_source_clauses)


def test_season_scope_carries_across_semicolon_within_same_source_sentence() -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [
            _quality_record(
                "测试机场",
                "winter-plan",
                "冬季运行保障方案要求集中除冰；除冰液使用按冬季方案执行。",
            )
        ],
        category="core",
    )[0]

    assert agent.filter_fact_for_duty(
        fact,
        _quality_duty(),
        date(2026, 8, 8),
        [],
    ) is None


def test_specific_flight_fact_requires_current_flight_match() -> None:
    records = [
        _quality_record(
            "测试机场",
            "flight-specific",
            "9C7635和9C6135同时刻同行路，注意防止误听指令。",
        )
    ]
    fact = agent.source_record_facts("测试机场", records, category="core")[0]
    exclusions: list[dict[str, object]] = []

    assert agent.filter_fact_for_duty(
        fact,
        _quality_duty(flight_number="9C6499"),
        date(2026, 8, 8),
        exclusions,
    ) is None
    assert exclusions[0]["reason"] == "与当前航班/航线不匹配"

    matching = _quality_duty(flight_number="9C7635")
    assert agent.filter_fact_for_duty(
        fact,
        matching,
        date(2026, 8, 8),
        [],
    ) is not None


def test_explicit_route_scope_requires_current_route_match() -> None:
    record = _quality_record("测试机场", "route-specific", "特定航线运行提醒。")
    record["route_scope"] = [("测试机场", "另一测试机场")]
    fact = agent.source_record_facts("测试机场", [record], category="core")[0]
    assert agent.filter_fact_for_duty(
        fact,
        _quality_duty(),
        date(2026, 8, 8),
        [],
    ) is not None

    mismatch = _quality_record("测试机场", "route-mismatch", "另一特定航线提醒。")
    mismatch["route_scope"] = [("测试机场", "第三测试机场")]
    mismatch_fact = agent.source_record_facts(
        "测试机场", [mismatch], category="core"
    )[0]
    assert agent.filter_fact_for_duty(
        mismatch_fact,
        _quality_duty(),
        date(2026, 8, 8),
        [],
    ) is None


@pytest.mark.parametrize(
    "placeholder",
    ["目前数据库中无数据", "暂无数据", "未收录", "无", "N/A", "未发现明确事件"],
)
def test_typical_placeholder_renders_as_unnumbered_no_data(placeholder: str) -> None:
    airport = "测试机场"
    records = [
        _quality_record(
            airport,
            "placeholder",
            placeholder,
            phase="incident",
            category="typical",
        )
    ]
    facts = agent.bilingual_typical_facts(
        airport,
        [],
        [],
        8,
        5,
        source_records=records,
        event=_quality_duty(airport),
        target=date(2026, 8, 8),
    )

    assert len(facts) == 1
    assert facts[0].category == "typical_no_data"
    assert facts[0].zh == agent.TYPICAL_NO_DATA_TEXT_ZH


def test_profile_labels_become_one_traceable_natural_paragraph() -> None:
    airport = "测试机场"
    records = [
        _quality_record(airport, "classification", "机场分类：一类操纵复杂机场。"),
        _quality_record(airport, "highland", "高原机场：一般高原机场。"),
        _quality_record(
            airport,
            "terrain",
            "地形：150°～320°，且MSA根据距离有3300米和6000米不等。",
            phase="terrain",
        ),
    ]

    paragraphs = agent.airport_operational_facts(
        _quality_duty(airport),
        airport,
        [],
        date(2026, 8, 8),
        source_records=records,
    )

    assert len(paragraphs) == 1
    paragraph = paragraphs[0]
    assert "该机场属于一般高原机场和一类操纵复杂机场" in paragraph.zh
    assert "150°至320°方向存在地形" in paragraph.zh
    assert "3300米" in paragraph.zh and "6000米" in paragraph.zh
    assert not any(label in paragraph.zh for label in ("机场分类：", "高原机场：", "地形："))
    assert set(paragraph.source_fact_ids) == {"classification", "highland", "terrain"}
    assert agent.validate_source_semantic_preservation(paragraph) == []


def test_same_topic_merge_preserves_numbers_units_and_source_control() -> None:
    airport = "测试机场"
    records = [
        _quality_record(
            airport,
            "taxi-width",
            "滑行道宽度为18米。",
            phase="ground",
        ),
        _quality_record(
            airport,
            "taxi-speed",
            "资料要求需严格控制滑行速度。",
            phase="ground",
        ),
    ]
    paragraphs = agent.airport_operational_facts(
        _quality_duty(airport),
        airport,
        [],
        date(2026, 8, 8),
        source_records=records,
    )

    assert len(paragraphs) == 1
    assert "18米" in paragraphs[0].zh
    assert "需严格控制滑行速度" in paragraphs[0].zh
    assert set(paragraphs[0].source_fact_ids) == {"taxi-width", "taxi-speed"}
    assert agent.validate_source_semantic_preservation(paragraphs[0]) == []


@pytest.mark.parametrize(
    "source",
    [
        "曾因风切变导致低空不稳定状态后机组复飞。",
        "建议机组操纵起飞时保持较低的拉杆速率。",
        "有机组反映进近阶段出现导航信号异常。",
    ],
)
def test_clean_output_fact_preserves_manual_crew_subject(source: str) -> None:
    cleaned = agent.clean_output_fact(source)

    assert "机组" in cleaned
    assert "我们复飞" not in cleaned
    assert "建议我们操纵" not in cleaned
    assert "据运行反馈" not in cleaned


def test_core_fact_selection_rejects_opposite_airport_role_before_importance() -> None:
    def fact(fact_id: str, phase: str, importance: int = 60) -> agent.BilingualFact:
        return agent.BilingualFact(
            fact_id,
            fact_id,
            fact_id,
            airport="测试机场",
            source_file="knowledge/test.pdf",
            source="PDF",
            source_page="1",
            source_heading="测试机场运行特点",
            source_section="核心威胁",
            operational_phase=phase,
            category="core",
            importance=importance,
        )

    facts = [
        fact("departure", "departure"),
        fact("arrival", "arrival", 100),
        fact("approach", "approach", 100),
        fact("landing", "landing", 100),
        fact("ground", "ground"),
        fact("weather", "weather"),
    ]

    departure = agent.select_airport_facts("测试机场", "departure", facts)
    arrival = agent.select_airport_facts("测试机场", "arrival", facts)

    assert {item.fact_id for item in departure} == {"departure", "ground", "weather"}
    assert "departure" not in {item.fact_id for item in arrival}
    assert {"arrival", "approach", "landing", "ground", "weather"} == {
        item.fact_id for item in arrival
    }


def test_explicit_ground_role_scope_uses_only_source_operational_markers() -> None:
    assert agent.explicit_role_scope("ACARS确认PDC后无需复诵。", "ground") == (
        "departure",
    )
    assert agent.explicit_role_scope("落地后沿滑行道滑入机位。", "ground") == (
        "arrival",
    )
    assert agent.explicit_role_scope("滑行道宽度为18米。", "ground") == ()
    assert agent.explicit_role_scope(
        "冬春季大风乱流明显；24号向阳落地，对着陆目视有影响。",
        "weather",
    ) == ("arrival",)


def test_manual_details_and_explicit_operation_subsections_are_recovered() -> None:
    section = {
        "lines": [
            "测试机场运行特点",
            "一、典型不安全事件",
            "二、核心威胁",
            "1.跑道有坡度，注意着陆时下沉。",
            "三、运行特点",
            "（一）地面：",
            "1.有PDC。",
            "（1）ACARS确认，无需复诵PDC。",
            "（二）离场：",
            "1.离场以雷达引导为主，可以申请直飞TESTA。",
            "（四）进场：",
            "1.进场通常使用BY ATC程序。",
            "（七）典型不安全事件详述：",
            "1.曾发生管制指挥下降较晚，机组在低高度复飞。",
            "2.历史上曾发生AFLOOR警告事件。",
        ]
    }

    typical, core = agent.extract_manual_lists(section, 20)

    assert len(typical) == 2
    assert "机组在低高度复飞" in typical[0]
    assert "AFLOOR" in typical[1]
    assert any(item.startswith("地面：") and "PDC" in item for item in core)
    assert any(item.startswith("离场：") and "TESTA" in item for item in core)
    assert any(item.startswith("进场：") and "BY ATC" in item for item in core)
    phases = {
        phase
        for item in core
        for _, _, phase in agent.split_manual_fact_item(item)
    }
    assert {"ground", "departure", "arrival"}.issubset(phases)


def test_manual_matching_uses_unique_exact_name_when_icao_mapping_is_stale() -> None:
    index = [
        {
            "section_type": "narrative",
            "icao": "ZSYA",
            "name_key": "扬州泰州",
            "strong_aliases": ["扬州泰州"],
            "weak_aliases": ["扬州", "泰州"],
        },
        {
            "section_type": "narrative",
            "icao": "ZAAA",
            "name_key": "其他机场",
            "strong_aliases": ["其他机场"],
            "weak_aliases": [],
        },
    ]

    matches = agent.match_manual_sections(index, "扬州泰州", "ZSYZ")

    assert [section["icao"] for section in matches] == ["ZSYA"]


def test_topic_organization_does_not_invent_control_measure_or_cross_airport() -> None:
    records = [
        _quality_record("甲机场", "plain-a", "滑行道宽度为18米。", phase="ground"),
        _quality_record("乙机场", "plain-b", "滑行道宽度为20米。", phase="ground"),
    ]
    paragraphs = agent.airport_operational_facts(
        _quality_duty("甲机场"),
        "甲机场",
        [],
        date(2026, 8, 8),
        source_records=records,
    )
    content = "".join(fact.zh for fact in paragraphs)

    assert "18米" in content and "20米" not in content
    assert not any(word in content for word in ("应", "建议", "注意", "需", "必须"))


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


@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含机场手册PDF")
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
    assert "本阶段经历时间75小时" in intro
    assert "起落12个" in intro
    assert "近90天起落8个" in intro
    assert "7月28日上海浦东机场" in intro
    assert "A320" not in intro
    assert "近一个月起落" not in intro
    assert "（含模拟机）" not in intro
    assert "近期机场经历" not in content
    assert "近期注意点" not in content
    assert "个人对本次航班中识别的风险：" not in content
    assert "•" not in content
    assert "None" not in content and "null" not in content
    assert (
        "上一次作为PF教员评价：30尺以下带杆量欠一点；"
        "着陆后快速脱离道口前及时减速至30节以下；作为PM机长评价：增加SOP熟练度，"
        "标准喊话声音大一些。"
    ) in content
    assert not re.search(r"(?m)^\d+[.、]曾", content)
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
    assert (
        "01号跑道入口内移，实际着陆可用距离为2410米，应使用中档刹车"
        in content
    )
    assert "19号跑道只能用于起飞，禁止进近及着陆" in content
    assert "2350米" not in content
    assert (
        "01号跑道起飞有载重限制，应结合FLY SMART计算结果采取措施，"
        "如计算需要再关空调起飞"
    ) in content

    assert meta["flight_numbers"] == ["9C8523", "9C8524"]
    assert meta["airports"] == ["上海浦东", "恩施许家坪"]
    assert meta["airport_information_version"] == REAL_PDF_VERSION
    assert meta["airport_information_type"] == "PDF"
    assert meta["foreign_crew_detected"] is False
    assert meta["english_confirmation_required"] is False
    assert meta["english_generated"] is False
    assert not (output / "latest_en.txt").exists()
    assert not (output / "2026-08-04_航前准备_详细版.txt").exists()
    excluded = meta["excluded_source_clauses"]
    assert any(
        item["airport"] == "恩施许家坪"
        and "19号跑道" in item["clause"]
        and "禁止进近着陆" in item["reason"]
        for item in excluded
    )
    assert hashlib.sha256((REPO_ROOT / "flight.ics").read_bytes()).hexdigest() == original_hash


@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含机场手册PDF")
def test_real_august_eight_applies_season_task_and_topic_quality(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    original_hash = hashlib.sha256((REPO_ROOT / "flight.ics").read_bytes()).hexdigest()
    repo = tmp_path / "real-august-eight"
    _copy_runtime_repo(repo)
    monkeypatch.setattr(
        sys,
        "argv",
        ["flight_prep_agent.py", "--repo", str(repo), "--target-date", "2026-08-08"],
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    agent.extract_pdf_text.cache_clear()

    assert agent.main() == 0

    output = repo / "flight_preparation"
    content = (output / "latest.txt").read_text(encoding="utf-8")
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "SUCCESS"
    assert meta["flight_numbers"] == ["9C6499", "9C6500"]
    assert meta["airports"] == ["沈阳桃仙", "嘉峪关酒泉"]

    shenyang = content.split("沈阳桃仙机场：", 1)[1].split(
        "嘉峪关酒泉机场：", 1
    )[0]
    jiayuguan = content.split("嘉峪关酒泉机场：", 1)[1]
    for required in (
        "离地姿态大",
        "擦机尾",
        "A2",
        "A8",
        "FLYSMART",
        "雷达引导",
        "高截获",
        "ILS",
        "程序、跑道和离场点",
    ):
        assert required in shenyang
    for forbidden in (
        "冬春季",
        "冬季甩冰",
        "冬季运行保障方案",
        "除防冰",
        "防冰液",
        "9C7635",
        "9C6135",
    ):
        assert forbidden not in shenyang

    assert "嘉峪关酒泉机场典型不安全事件：" not in content
    assert "一般高原机场" in jiayuguan
    assert "一类操纵复杂机场" in jiayuguan
    assert "150°至320°" in jiayuguan
    assert "3300米" in jiayuguan and "6000米" in jiayuguan
    assert "释压程序" in jiayuguan
    assert "20000英尺" in jiayuguan
    assert "冬春季" not in jiayuguan
    for label in ("机场分类：", "高原机场：", "特殊复杂程序：", "地形："):
        assert label not in jiayuguan

    excluded = meta["excluded_source_clauses"]
    assert any("冬春季" in item["clause"] and "目标月份为8月" in item["reason"] for item in excluded)
    assert any("9C7635" in item["clause"] and item["reason"] == "与当前航班/航线不匹配" for item in excluded)
    assert any(len(ids) > 1 for ids in meta["core_paragraph_fact_ids"]["嘉峪关酒泉"])
    assert hashlib.sha256((REPO_ROOT / "flight.ics").read_bytes()).hexdigest() == original_hash


@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含机场手册PDF")
def test_real_august_eleven_writes_two_source_grounded_prep_reports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    original_hash = hashlib.sha256((REPO_ROOT / "flight.ics").read_bytes()).hexdigest()
    repo = tmp_path / "real-august-eleven"
    _copy_runtime_repo(repo)
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(icao="", metar="", taf="", error=""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["flight_prep_agent.py", "--repo", str(repo), "--target-date", "2026-08-11"],
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    agent.extract_pdf_text.cache_clear()

    assert agent.main() == 0

    output = repo / "flight_preparation"
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "SUCCESS"
    assert meta["flight_numbers"] == ["9C6809", "9C7080"]
    assert len(meta["prep_groups"]) == 2
    assert [group["flight_numbers"] for group in meta["prep_groups"]] == [
        ["9C6809"],
        ["9C7080"],
    ]
    assert [group["airports"] for group in meta["prep_groups"]] == [
        ["沈阳桃仙", "桂林两江"],
        ["桂林两江", "扬州泰州"],
    ]

    first_path = output / meta["prep_groups"][0]["output"]
    second_path = output / meta["prep_groups"][1]["output"]
    assert first_path != second_path
    first = first_path.read_text(encoding="utf-8")
    second = second_path.read_text(encoding="utf-8")
    assert "沈阳桃仙机场：" in first and "桂林两江机场：" in first
    assert "扬州泰州机场：" not in first
    assert "桂林两江机场：" in second and "扬州泰州机场：" in second
    assert "沈阳桃仙机场：" not in second
    first_core = first.split("核心威胁：", 1)[1]
    first_shenyang = first_core.split("沈阳桃仙机场：", 1)[1].split(
        "桂林两江机场：", 1
    )[0]
    first_guilin = first_core.split("桂林两江机场：", 1)[1]
    second_core = second.split("核心威胁：", 1)[1]
    second_guilin = second_core.split("桂林两江机场：", 1)[1].split(
        "扬州泰州机场：", 1
    )[0]
    second_yangzhou = second_core.split("扬州泰州机场：", 1)[1]
    assert "24 号向阳落地" not in first_shenyang
    assert "ILS06/24" not in first_shenyang
    assert "自行转向五边" not in first_shenyang
    assert "甩冰" not in first_shenyang
    assert "跑道有坡度" in first_guilin
    assert "19号跑道盲降" in first_guilin
    assert "PDC" not in first_guilin
    assert "19号跑道盲降" not in second_guilin
    assert "着陆时的下沉" not in second_guilin
    assert "夜间灯光" not in second_guilin
    assert any(
        marker in second_guilin
        for marker in ("PDC", "雷达引导", "OVTAN", "BY ATC", "by ATC")
    )
    assert "现场/签派频率" not in second_guilin
    assert "ZJ方向进场" in second_yangzhou
    assert "扬州泰州机场典型不安全事件：" in second
    assert "1000 英尺" in second
    assert "400 英尺" in second
    assert "AFLOOR" in second
    assert "机组执行" in second
    assert "我们执行" not in second
    assert "机组复飞" in first
    assert "我们复飞" not in first
    for content in (first, second):
        intro = content.split("\n\n", 1)[0]
        assert "本阶段经历时间75小时" in intro
        assert "起落12个" in intro
        assert "近90天起落8个" in intro
        assert "上一次实际操纵落地为7月28日上海浦东机场" in intro
        assert "近一个月起落" not in intro
        assert "（含模拟机）" not in intro
        assert "个人对本次航班中识别的风险：" not in content
        assert "核心威胁：" in content
        assert not re.search(r"(?m)^\s*(?:\d+[.、]|[•●▪])\s*\S", content)
        assert (
            "上一次作为PF教员评价：30尺以下带杆量欠一点；"
            "着陆后快速脱离道口前及时减速至30节以下"
        ) in content
        assert "RNP进近五边速度180节" not in content

    for group in meta["prep_groups"]:
        for airport in group["airports"]:
            core_sources = [
                item
                for item in group["airport_fact_sources"][airport]
                if item["category"] == "core"
            ]
            assert core_sources
            assert all(item["source_fact_ids"] for item in core_sources)
            assert all(item["source_file"] for item in core_sources)
            assert all(item["source_original_text"] for item in core_sources)

    first_sources = meta["prep_groups"][0]["airport_fact_sources"]
    second_sources = meta["prep_groups"][1]["airport_fact_sources"]
    assert not {
        item["operational_phase"]
        for item in first_sources["沈阳桃仙"]
        if item["category"] == "core"
    }.intersection({"arrival", "approach", "landing", "landing_ground"})
    assert all(
        item["operational_phase"]
        not in {"arrival", "approach", "landing", "landing_ground"}
        or "departure" in item["role_scope"]
        for item in second_sources["桂林两江"]
        if item["category"] == "core"
    )
    yangzhou_typical = [
        item
        for item in second_sources["扬州泰州"]
        if item["category"] == "typical"
    ]
    assert len(yangzhou_typical) >= 2
    assert all(item["source_fact_ids"] for item in yangzhou_typical)
    assert all(item["source_text_zh"] for item in yangzhou_typical)
    assert any("9C6552" in item["source_text_zh"] for item in yangzhou_typical)
    assert any("AFLOOR" in item["source_text_zh"] for item in yangzhou_typical)

    assert hashlib.sha256((REPO_ROOT / "flight.ics").read_bytes()).hexdigest() == original_hash
