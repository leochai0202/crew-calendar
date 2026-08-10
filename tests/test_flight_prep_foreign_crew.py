from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import (
    CalendarEvent,
    foreign_crew_names,
    parse_ics,
    select_exact_flight_event,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_PDF_CANDIDATES = sorted(
    (REPO_ROOT / "knowledge" / "pdf").glob(
        "*机场特点汇总(Airport Information)*.pdf"
    )
)
REAL_PDF = REAL_PDF_CANDIDATES[-1] if REAL_PDF_CANDIDATES else Path("missing.pdf")
REAL_PDF_VERSION = agent.manual_version(REAL_PDF) if REAL_PDF.exists() else 0
TARGET_DATE = date(2026, 7, 23)
EXPECTED_PEOPLE = [
    "MARQUES SANTANNA HELIO(R)",
    "左争世(R)",
    "段洋硕",
    "罗一敏(B)",
]


def _event(
    *,
    uid: str,
    number: str,
    departure: str,
    arrival: str,
    people: list[str],
    checkin: str = "04:25｜新加坡樟宜",
    registration: str = "B32D6",
) -> CalendarEvent:
    description = "\n".join(
        [
            "类型：航班",
            f"航班：{number}",
            f"航线：{departure} → {arrival}",
            f"签到：{checkin}",
            f"机型：A320｜注册号：{registration}",
            "人员名单：",
            *(f"• {name}" for name in people),
            "",
            "版本：2026-07-21 20:54",
        ]
    )
    return CalendarEvent(
        uid=uid,
        summary=f"✈️ {number} {departure}→{arrival}",
        start=datetime(2026, 7, 23, 6, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
        end=datetime(2026, 7, 23, 11, 40, tzinfo=ZoneInfo("Asia/Shanghai")),
        description=description,
        location=departure,
        properties={},
        source_file="flight.ics",
    )


def _write_ics(path: Path, events: list[CalendarEvent]) -> None:
    blocks = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for event in events:
        description = event.description.replace("\\", "\\\\").replace("\n", "\\n")
        blocks.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event.uid}",
                f"SUMMARY:{event.summary}",
                f"DTSTART;TZID=Asia/Shanghai:{event.start:%Y%m%dT%H%M%S}",
                f"DTEND;TZID=Asia/Shanghai:{event.end:%Y%m%dT%H%M%S}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{event.location}",
                "END:VEVENT",
            ]
        )
    blocks.append("END:VCALENDAR")
    path.write_text("\n".join(blocks) + "\n", encoding="utf-8")


def _prepare_stub_repo(root: Path, events: list[CalendarEvent]) -> None:
    (root / "config").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "crew_calendar_main.py", root)
    shutil.copy2(REPO_ROOT / "config" / "pilot_profile.json", root / "config")
    shutil.copy2(REPO_ROOT / "config" / "airport_experience.json", root / "config")
    shutil.copy2(REPO_ROOT / "config" / "airport_supplements.json", root / "config")
    settings = json.loads(
        (REPO_ROOT / "config" / "prep_settings.json").read_text(encoding="utf-8")
    )
    settings["auto_update_airport_experience"] = False
    settings["include_weather_section"] = False
    (root / "config" / "prep_settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_ics(root / "flight.ics", events)


def _stub_airport_risks(
    repo: Path,
    airports: list[str],
    icao_map: dict[str, str],
    max_items: int,
) -> tuple[
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[dict[str, object]]],
    list[str],
    str,
    int,
    str,
]:
    del repo, icao_map, max_items
    risks = {airport: ["雷雨", "滑行路线复杂", "鸟击"] for airport in airports}
    threats = {
        airport: ["跑道程序变化", "雷达引导后注意下降剖面", "TA/RA"]
        for airport in airports
    }
    source_records = {
        airport: [
            {
                "airport": airport,
                "source_file": agent.AIRPORT_MANUAL_FILE,
                "source": "PDF",
                "source_page": "1",
                "source_heading": f"{airport}测试章节",
                "source_section": f"{airport}测试章节",
                "operational_phase": "weather",
                "airport_specific": True,
                "category": "typical",
                "text_zh": "曾发生雷雨影响运行事件。",
                "text_en": "A thunderstorm has affected operations.",
            },
            {
                "airport": airport,
                "source_file": agent.AIRPORT_MANUAL_FILE,
                "source": "PDF",
                "source_page": "1",
                "source_heading": f"{airport}测试章节",
                "source_section": f"{airport}测试章节",
                "operational_phase": "arrival",
                "airport_specific": True,
                "category": "core",
                "text_zh": "雷达引导后应关注下降剖面。",
                "text_en": "Monitor the descent profile after radar vectors.",
            },
        ]
        for airport in airports
    }
    return risks, threats, source_records, [], "stub-20260720.pdf", 20260720, "PDF"


def _run_stubbed_main(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
    event: CalendarEvent,
    *,
    existing_english: str = "",
) -> Path:
    _prepare_stub_repo(repo, [event])
    if existing_english:
        output = repo / "flight_preparation"
        output.mkdir()
        (output / "latest_en.txt").write_text(existing_english, encoding="utf-8")
    monkeypatch.setattr(agent, "airport_risks", _stub_airport_risks)
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(icao="", metar="", taf="", error=""),
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "flight_prep_agent.py",
            "--repo",
            str(repo),
            "--target-date",
            TARGET_DATE.isoformat(),
            "--flight-number",
            event.flight_number,
            "--departure",
            event.route[0],
            "--arrival",
            event.route[1],
        ],
    )
    assert agent.main() == 0
    return repo / "flight_preparation"


def _paragraph(text: str, heading: str) -> str:
    return next(
        block
        for block in (part.strip() for part in text.split("\n\n"))
        if block.startswith(heading)
    )


def _numbered_count(text: str, heading: str) -> int:
    block = _paragraph(text, heading)
    return sum(
        1
        for line in block.splitlines()[1:]
        if re.match(r"^\d+[.、]\s*", line)
    )


def test_international_flight_without_foreign_name_does_not_trigger_english(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = _event(
        uid="international-chinese-only",
        number="9C8552",
        departure="新加坡樟宜",
        arrival="上海浦东",
        people=["左争世(R)", "段洋硕", "罗一敏(B)"],
    )

    output = _run_stubbed_main(monkeypatch, tmp_path / "international", event)
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))

    assert not agent.should_generate_english(event)
    assert meta["english_generated"] is False
    assert meta["english_trigger_names"] == []
    assert not (output / "latest_en.txt").exists()
    assert not (output / "latest_detail_en.txt").exists()


def test_domestic_flight_with_latin_name_requires_english_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = _event(
        uid="domestic-foreign",
        number="9C1001",
        departure="上海浦东",
        arrival="南昌昌北",
        people=["JOHN SMITH(R)", "左争世(R)", "段洋硕", "罗一敏(B)"],
        checkin="08:00｜上海浦东",
    )

    output = _run_stubbed_main(
        monkeypatch,
        tmp_path / "domestic",
        event,
        existing_english="existing confirmed English briefing\n",
    )
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))

    assert agent.should_generate_english(event)
    assert foreign_crew_names(event) == ["JOHN SMITH(R)"]
    assert meta["foreign_crew_detected"] is True
    assert meta["foreign_crew_names"] == ["JOHN SMITH(R)"]
    assert meta["english_confirmation_required"] is True
    assert meta["english_generated"] is False
    assert (output / "latest_en.txt").read_text(encoding="utf-8") == (
        "existing confirmed English briefing\n"
    )


def test_legacy_automatic_english_setting_cannot_bypass_confirmation() -> None:
    event = _event(
        uid="foreign-confirmation",
        number="9C1001",
        departure="上海浦东",
        arrival="南昌昌北",
        people=["JOHN SMITH(R)", "段洋硕"],
    )

    generate, confirmation, names = agent.english_generation_decision(
        event,
        {"foreign_crew_english_mode": "always"},
    )

    assert generate is False
    assert confirmation is True
    assert names == ["JOHN SMITH(R)"]


def test_bilingual_render_hides_internal_flight_metadata() -> None:
    event = _event(
        uid="metadata",
        number="9C8552",
        departure="新加坡樟宜",
        arrival="上海浦东",
        people=EXPECTED_PEOPLE,
    )
    profile = json.loads(
        (REPO_ROOT / "config" / "pilot_profile.json").read_text(encoding="utf-8")
    )
    experience = json.loads(
        (REPO_ROOT / "config" / "airport_experience.json").read_text(encoding="utf-8")
    )
    records = agent.experience_records(experience, list(event.route), TARGET_DATE)
    risks = {airport: ["雷雨", "滑行", "鸟击"] for airport in event.route}
    threats = {airport: ["SID", "雷达引导", "TA/RA"] for airport in event.route}
    typical, core, facts = agent.briefing_fact_sets(
        event,
        TARGET_DATE,
        risks,
        threats,
        max_items=5,
    )
    chinese = agent.render_chinese_briefing(
        event, TARGET_DATE, profile, records, typical, core
    )
    english = agent.render_english_briefing(
        event, TARGET_DATE, profile, records, typical, core
    )

    assert chinese.startswith("我是来自飞行十五中队的副驾驶段洋硕")
    assert english.startswith("I am Duan Yangshuo")
    assert "a First Officer in Flight Squadron 15" in english
    assert (
        "I have operated at both Singapore Changi and Shanghai Pudong "
        "within the past three months."
    ) in english
    assert "None of the airports on this flight lacks recent experience." not in english
    chinese_order = [
        chinese.index("上一次飞行中机长/教员对我优缺点的评价"),
        chinese.index("核心威胁："),
    ]
    english_order = [
        english.index("Latest PF/PM feedback:"),
        english.index("Core threats:"),
    ]
    assert chinese_order == sorted(chinese_order)
    assert english_order == sorted(english_order)
    for value in (
        "9C8552",
        "B32D6",
        "MARQUES SANTANNA HELIO",
        "左争世",
        "罗一敏",
        "新加坡樟宜→上海浦东",
        "新加坡樟宜至上海浦东",
        "Singapore Changi-Shanghai Pudong",
        "人员名单",
        "注册号",
    ):
        assert value not in chinese
        assert value not in english
    assert "机组" not in chinese
    assert "个人对本次航班中识别的风险：" not in chinese
    assert "Risks I have identified for this flight:" not in english
    assert "新加坡樟宜机场典型不安全事件：" not in chinese
    assert "Singapore Changi Airport typical unsafe events:" not in english
    assert agent.validate_bilingual_facts(facts) == []


def test_singapore_irs_is_first_core_fact_and_content_stays_role_scoped() -> None:
    event = _event(
        uid="roles",
        number="9C8552",
        departure="新加坡樟宜",
        arrival="上海浦东",
        people=EXPECTED_PEOPLE,
    )
    risks = {airport: ["雷雨", "滑行", "鸟击"] for airport in event.route}
    threats = {airport: ["SID", "雷达引导", "TA/RA"] for airport in event.route}
    typical, core, facts = agent.briefing_fact_sets(
        event,
        TARGET_DATE,
        risks,
        threats,
        max_items=5,
    )

    singapore = core["新加坡樟宜"]
    assert singapore[0].zh == (
        "新加坡属于低纬度机场，驾驶舱准备阶段确认完成IRS完全校准；"
        "同时核对跑道、SID、初始高度、第一航路点和高度速度限制。"
    )
    assert singapore[0].en == (
        "As Singapore is a low-latitude airport, confirm a full IRS alignment during cockpit preparation. "
        "Cross-check the runway, SID, initial altitude, first waypoint, and all altitude and speed constraints."
    )
    assert all(items for items in core.values())
    assert agent.validate_bilingual_facts(facts) == []


def _source_fact(
    fact_id: str,
    airport: str,
    text: str,
    *,
    phase: str = "ground",
    importance: int = 50,
) -> agent.BilingualFact:
    return agent.BilingualFact(
        fact_id,
        text,
        text,
        airport=airport,
        source_file=agent.AIRPORT_MANUAL_FILE,
        source="PDF",
        source_page="1",
        source_heading=f"{airport}测试来源",
        source_section=f"{airport}测试来源章节",
        operational_phase=phase,
        airport_specific=True,
        category="core",
        importance=importance,
        semantic_key=fact_id,
    )


def test_airport_specific_procedures_cannot_cross_airport_boundaries() -> None:
    singapore = _source_fact(
        "wsss_only",
        "新加坡樟宜",
        "FOLLOW GREEN / IRS full alignment",
        importance=100,
    )
    pudong = _source_fact("zspd_only", "上海浦东", "Pudong ADGS")

    selected = agent.select_airport_facts(
        "上海浦东",
        "arrival",
        [singapore, pudong],
    )

    assert [fact.fact_id for fact in selected] == ["zspd_only"]
    assert "FOLLOW GREEN" not in " ".join(fact.zh for fact in selected)
    assert "IRS" not in " ".join(fact.zh for fact in selected)


def test_role_sorting_does_not_invent_or_pad_airport_facts() -> None:
    event = _event(
        uid="no-template-padding",
        number="9C2001",
        departure="伦敦希思罗",
        arrival="巴黎戴高乐",
        people=["段洋硕", "左争世(R)"],
    )
    records = [
        {
            "airport": "巴黎戴高乐",
            "source_file": agent.AIRPORT_MANUAL_FILE,
            "source": "PDF",
            "source_page": "100",
            "source_heading": "巴黎戴高乐机场运行特点",
            "source_section": "巴黎戴高乐／明确内容",
            "operational_phase": "arrival",
            "airport_specific": True,
            "category": "core",
            "text_zh": "只存在第一条有效内容。",
            "text_en": "Only the first valid fact is available.",
        },
        {
            "airport": "巴黎戴高乐",
            "source_file": agent.SUPPLEMENT_FILE,
            "source": "supplement",
            "source_page": "N/A",
            "source_heading": "巴黎戴高乐",
            "source_section": "巴黎戴高乐／补充内容",
            "operational_phase": "weather",
            "airport_specific": False,
            "category": "core",
            "text_zh": "只存在第二条有效内容。",
            "text_en": "Only the second valid fact is available.",
        },
    ]

    facts = agent.airport_operational_facts(
        event,
        "巴黎戴高乐",
        [],
        TARGET_DATE,
        source_records=records,
    )

    assert len(facts) == 2
    combined = " ".join(fact.zh for fact in facts)
    for unsupported in (
        "FOLLOW GREEN",
        "停止排灯",
        "CPDLC",
        "热点",
        "跑道穿越",
        "ADGS",
    ):
        assert unsupported not in combined


def test_special_important_fact_survives_role_phase_sorting() -> None:
    facts = [
        _source_fact(
            "special",
            "测试机场",
            "机场资料明确记载的特殊重要要求",
            phase="special",
            importance=100,
        ),
        *[
            _source_fact(
                f"arrival_{index}",
                "测试机场",
                f"进场事实{index}",
                phase="arrival",
                importance=60,
            )
            for index in range(1, 6)
        ],
    ]

    selected = agent.select_airport_facts("测试机场", "arrival", facts)

    assert len(selected) == 5
    assert "special" in [fact.fact_id for fact in selected]


def test_same_phase_uses_curated_then_supplement_then_pdf_priority() -> None:
    base = _source_fact("pdf", "测试机场", "PDF事实", phase="arrival")
    supplement = replace(
        _source_fact("supplement", "测试机场", "补充事实", phase="arrival"),
        source="supplement",
    )
    curated = replace(
        _source_fact("curated", "测试机场", "精选事实", phase="arrival"),
        source="CURATED",
    )

    selected = agent.select_airport_facts(
        "测试机场",
        "arrival",
        [curated, supplement, base],
    )

    assert [fact.source for fact in selected] == ["CURATED", "supplement", "PDF"]


def test_curated_fact_is_not_dropped_by_five_pdf_facts() -> None:
    pdf_facts = [
        _source_fact(
            f"pdf_{index}",
            "测试机场",
            f"普通PDF事实{index}",
            phase="arrival",
            importance=60,
        )
        for index in range(1, 6)
    ]
    curated = replace(
        _source_fact(
            "curated_special",
            "测试机场",
            "人工精选事实",
            phase="ground",
            importance=85,
        ),
        source="CURATED",
    )

    selected = agent.select_airport_facts(
        "测试机场",
        "arrival",
        [*pdf_facts, curated],
    )

    assert len(selected) == 5
    assert "curated_special" in [fact.fact_id for fact in selected]


def test_curated_expression_overrides_related_pdf_fact() -> None:
    pdf = replace(
        _source_fact("pdf_energy", "测试机场", "PDF基础表达", phase="arrival"),
        semantic_key="arrival_energy",
    )
    curated = replace(
        _source_fact(
            "curated_energy",
            "测试机场",
            "人工精选修正表达",
            phase="arrival",
            importance=90,
        ),
        source="CURATED",
        semantic_key="arrival_energy",
    )

    selected = agent.select_airport_facts(
        "测试机场",
        "arrival",
        [pdf, curated],
    )

    assert [fact.fact_id for fact in selected] == ["curated_energy"]


def test_final_airport_facts_are_traceable_and_share_bilingual_ids() -> None:
    event = _event(
        uid="traceable",
        number="9C8552",
        departure="新加坡樟宜",
        arrival="上海浦东",
        people=EXPECTED_PEOPLE,
    )
    risks = {airport: ["雷雨", "滑行", "鸟击"] for airport in event.route}
    threats = {airport: ["SID", "雷达引导", "TA/RA"] for airport in event.route}
    typical, core, _ = agent.briefing_fact_sets(
        event,
        TARGET_DATE,
        risks,
        threats,
        max_items=5,
    )

    for airport in event.route:
        facts = [*typical[airport], *core[airport]]
        assert agent.validate_airport_fact_bindings(airport, facts) == []
        zh_ids = [fact.fact_id for fact in facts if fact.zh]
        en_ids = [fact.fact_id for fact in facts if fact.en]
        assert zh_ids == en_ids
        assert all(fact.source_file for fact in facts)
        assert all(fact.source_page for fact in facts)
        assert all(fact.source_heading for fact in facts)
        assert all(fact.source_section for fact in facts)
        assert all(agent.canonical_airport_name(fact.airport) == airport for fact in facts)

    pudong_text = " ".join(fact.zh + " " + fact.en for fact in core["上海浦东"])
    assert "FOLLOW GREEN" not in pudong_text
    assert "full IRS alignment" not in pudong_text


def test_pudong_runway_occupancy_and_adgs_are_independent_facts() -> None:
    facts = {
        fact.fact_id: agent.bind_catalog_fact(fact)
        for fact in agent.PUDONG_ARRIVAL_FACTS
    }

    assert "zspd_runway_occupancy" in facts
    assert "zspd_adgs_entry" in facts
    assert facts["zspd_runway_occupancy"].operational_phase == "landing"
    assert facts["zspd_adgs_entry"].operational_phase == "ground"
    assert "ADGS" not in facts["zspd_runway_occupancy"].zh
    assert "50秒" not in facts["zspd_adgs_entry"].zh


def test_non_singapore_real_route_uses_only_its_own_source_facts() -> None:
    event = select_exact_flight_event(
        parse_ics(REPO_ROOT / "flight.ics"),
        date(2026, 7, 5),
        flight_number="9C7278Y",
        departure="石家庄正定",
        arrival="上海虹桥",
    )
    records = {
        "石家庄正定": [
            {
                "fact_id": "zbsj_departure_ground",
                "semantic_key": "zbsj_departure_ground",
                "airport": "石家庄正定",
                "source_file": agent.AIRPORT_MANUAL_FILE,
                "source": "PDF",
                "source_page": "341",
                "source_heading": "石家庄/正定机场运行特点",
                "source_section": "三、运行特点／地面／B8滑行路线",
                "operational_phase": "ground",
                "airport_specific": True,
                "category": "core",
                "text_zh": "使用B8滑行道时，我们应核对B、B7、C至B8前的实际路线，有疑问立即向地面证实。",
                "text_en": "When using taxiway B8, we must verify the actual route via B, B7, and C to the B8 holding point and confirm any doubt with Ground.",
            },
            {
                "fact_id": "zbsj_departure_runway_entry",
                "semantic_key": "zbsj_departure_runway_entry",
                "airport": "石家庄正定",
                "source_file": agent.AIRPORT_MANUAL_FILE,
                "source": "PDF",
                "source_page": "340",
                "source_heading": "石家庄/正定机场运行特点",
                "source_section": "三、运行特点／地面／跑道占用",
                "operational_phase": "departure",
                "airport_specific": True,
                "category": "core",
                "text_zh": "从收到进跑道指令到对正跑道应不超过50秒。",
                "text_en": "The interval from receiving the runway-entry clearance to lining up should not exceed 50 seconds.",
            },
        ],
        "上海虹桥": [
            {
                "fact_id": "zsss_arrival_spacing",
                "semantic_key": "zsss_arrival_spacing",
                "airport": "上海虹桥",
                "source_file": agent.AIRPORT_MANUAL_FILE,
                "source": "PDF",
                "source_page": "414,416",
                "source_heading": "上海/虹桥机场运行特点",
                "source_section": "二、核心威胁／前后机间隔与不稳定进近",
                "operational_phase": "approach",
                "airport_specific": True,
                "category": "core",
                "text_zh": "虹桥五边间隔较小，前后机间隔不足或进近不稳定时复飞较多，我们应持续监控间隔并坚持稳定进近标准。",
                "text_en": "Final-approach spacing at Hongqiao can be tight. We must monitor separation and maintain stabilized-approach criteria because inadequate spacing or an unstable approach has led to go-arounds.",
            },
            {
                "fact_id": "zsss_stand_guidance",
                "semantic_key": "zsss_stand_guidance",
                "airport": "上海虹桥",
                "source_file": agent.AIRPORT_MANUAL_FILE,
                "source": "PDF",
                "source_page": "414",
                "source_heading": "上海/虹桥机场运行特点",
                "source_section": "二、核心威胁／桥位引导灯",
                "operational_phase": "ground",
                "airport_specific": True,
                "category": "core",
                "text_zh": "进入126或127桥位时，引导灯距离数值临近停止线可能快速下降或跳变，我们应谨慎控制进位速度，避免过线。",
                "text_en": "When entering stands 126 or 127, the docking-guidance distance may decrease rapidly or jump near the stop line; we must control the entry speed carefully and avoid overshooting.",
            },
        ],
    }

    core = {
        airport: agent.airport_operational_facts(
            event,
            airport,
            [],
            date(2026, 7, 5),
            source_records=records[airport],
        )
        for airport in event.route
    }

    assert [len(core[airport]) for airport in event.route] == [2, 2]
    combined = " ".join(fact.zh + " " + fact.en for facts in core.values() for fact in facts)
    for foreign_fact in ("FOLLOW GREEN", "IRS完全校准", "full IRS alignment", "浦东"):
        assert foreign_fact not in combined
    for airport in event.route:
        assert agent.validate_airport_fact_bindings(airport, core[airport]) == []


def test_xining_nanchang_real_route_keeps_own_special_limits() -> None:
    event = select_exact_flight_event(
        parse_ics(REPO_ROOT / "flight.ics"),
        date(2026, 7, 8),
        flight_number="9C7258",
        departure="西宁曹家堡",
        arrival="南昌昌北",
    )
    empty_sources = {airport: [] for airport in event.route}
    typical, core, _ = agent.briefing_fact_sets(
        event,
        date(2026, 7, 8),
        {airport: ["有明确机场资料"] for airport in event.route},
        {airport: ["有明确机场资料"] for airport in event.route},
        max_items=5,
        source_records=empty_sources,
    )

    combined = " ".join(
        fact.zh + " " + fact.en
        for airport in event.route
        for fact in [*typical[airport], *core[airport]]
    )
    assert "7166ft" in combined
    assert "CN104" in combined
    assert "GPS" in combined
    for foreign_fact in ("FOLLOW GREEN", "IRS完全校准", "full IRS alignment", "浦东"):
        assert foreign_fact not in combined
    for airport in event.route:
        assert agent.validate_airport_fact_bindings(
            airport,
            [*typical[airport], *core[airport]],
        ) == []


@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含机场手册PDF")
def test_real_9c8552_exact_event_requires_english_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "real-9c8552"
    (repo / "config").mkdir(parents=True)
    (repo / "knowledge" / "pdf").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "crew_calendar_main.py", repo)
    shutil.copy2(REPO_ROOT / "flight.ics", repo)
    for name in (
        "prep_settings.json",
        "pilot_profile.json",
        "airport_experience.json",
        "airport_supplements.json",
    ):
        shutil.copy2(REPO_ROOT / "config" / name, repo / "config" / name)
    settings_path = repo / "config" / "prep_settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["auto_update_airport_experience"] = False
    settings["include_weather_section"] = False
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(
        REPO_ROOT / "knowledge" / "airport_information_20260615.txt",
        repo / "knowledge" / "airport_information_20260615.txt",
    )
    shutil.copy2(REAL_PDF, repo / "knowledge" / "pdf" / REAL_PDF.name)

    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(icao="", metar="", taf="", error=""),
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "flight_prep_agent.py",
            "--repo",
            str(repo),
            "--target-date",
            "2026-07-23",
            "--flight-number",
            "9C8552",
            "--departure",
            "新加坡樟宜",
            "--arrival",
            "上海浦东",
        ],
    )
    agent.extract_pdf_text.cache_clear()

    assert agent.main() == 0

    output = repo / "flight_preparation"
    chinese = (output / "latest.txt").read_text(encoding="utf-8")
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))

    assert meta["flight_numbers"] == ["9C8552"]
    assert meta["matched_event_uids"]
    assert meta["matched_people"] == EXPECTED_PEOPLE
    assert meta["english_trigger_names"] == ["MARQUES SANTANNA HELIO(R)"]
    assert meta["foreign_crew_detected"] is True
    assert meta["english_confirmation_required"] is True
    assert meta["english_generated"] is False
    assert meta["airport_information_version"] == REAL_PDF_VERSION
    assert meta["airport_information_type"] == "PDF"
    assert not (output / "latest_en.txt").exists()

    for value in (
        "9C8552",
        "B32D6",
        "MARQUES SANTANNA HELIO",
        "左争世",
        "罗一敏",
        "新加坡樟宜→上海浦东",
        "新加坡樟宜至上海浦东",
        "Singapore Changi-Shanghai Pudong",
        "人员名单",
        "注册号",
    ):
        assert value not in chinese
    assert chinese.startswith("我是来自飞行十五中队的副驾驶段洋硕")
    assert "刘总好" not in chinese
    assert "机组" in chinese
    assert "请我们注意" not in chinese

    assert "新加坡属于低纬度机场" in chinese
    assert "确认完成IRS完全校准" in chinese
    assert "FOLLOW GREEN" not in _paragraph(chinese, "上海浦东机场：")
    assert "50秒" not in _paragraph(chinese, "上海浦东机场：")
    assert "zspd_adgs_entry" in meta["airport_fact_ids"]["上海浦东"]["core"]
    assert "zspd_runway_occupancy" not in meta["airport_fact_ids"]["上海浦东"]["core"]
    assert set(meta["airport_fact_sources"]) == {"新加坡樟宜", "上海浦东"}
    for airport, facts in meta["airport_fact_sources"].items():
        assert all(item["airport"] == airport for item in facts)
        assert all(item["source_file"] for item in facts)
        assert all(item["source_page"] for item in facts)
        assert all(item["source_heading"] for item in facts)
        assert all(item["source_section"] for item in facts)
        assert all(item["fact_id"] for item in facts)

    pudong_core = chinese.split("核心威胁：", 1)[1].split("上海浦东机场：", 1)[1]
    for token in ("进场", "雷雨", "TA/RA", "鸟击", "下降剖面", "ADGS"):
        assert token in pudong_core

    for artifact in (
        "非受控文件",
        "非受 控文件",
        "FOR REFERENCE ONLY",
        "版本号",
        "责任中队",
        "机场运行特点",
        "指挥特点：",
        "气象特点：",
        "道面特点：",
        "西宁",
        "南昌",
        "丽江",
    ):
        assert artifact not in chinese

    selected = select_exact_flight_event(
        parse_ics(repo / "flight.ics"),
        TARGET_DATE,
        flight_number="9C8552",
        departure="新加坡樟宜",
        arrival="上海浦东",
    )
    assert selected.people == EXPECTED_PEOPLE
