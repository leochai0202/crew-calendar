from datetime import date, datetime

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


def event(number="9C7605", route=("甲机场", "乙机场")):
    return CalendarEvent(uid=number, summary=number, start=datetime(2026, 10, 26, 9),
                         end=datetime(2026, 10, 26, 11), description="", location="",
                         properties={"flight_number": number, "route": route})


def record(zh, en="", category="core"):
    return dict(airport="甲机场", source="PDF", source_file="knowledge/pdf/manual.pdf",
                source_verbatim=True, source_page="10", source_heading="甲机场运行特点",
                source_section="典型不安全事件" if category == "typical" else "核心威胁",
                source_version="latest", source_record_id="parent", category=category,
                text_zh=zh, text_en=en, operational_phase="ground", english_source_page="20")


def test_full_chapter_attributes_and_procedures_are_not_small_budget_limited():
    section = {"lines": [
        "1. 概述", "1.1. 基本信息", "(3) 机场标高：7358ft",
        "是否为复杂机场 是 三类综合类复杂机场", "是否存在 EOSID 是 02/20均存在EOSID",
        "2. 离场前地面运行阶段", "2.1. 02号跑道坡度0.59%。",
        "3. 离场阶段", "3.1. 起飞后按SID爬升。",
        "4. 进场进近和着陆阶段", "4.1. GPS不稳定时交叉检查。",
    ]}
    typical, core = agent.extract_manual_lists(section, 1)
    assert not typical
    for token in ("7358ft", "三类", "02/20", "0.59%", "SID", "GPS"):
        assert any(token in item for item in core)
    assert not agent.operational_attribute_text("机场标高7358ft，跑道坡度02号标高2225.6m，跑道")
    assert agent.manual_source_quality_issue("机场标高较高，放形态前检查高度不超过20000ft。") == ""
    assert agent.complete_basic_operational_items([
        "(4) 跑道信息：02/20（3000m×45m）", "(5) PAPI信息：02入口内287m，", "3度。", "1.2. 固有属性"
    ]) == ["跑道信息：02/20（3000m×45m）", "PAPI信息：02入口内287m，3度。"]
    assert agent.complete_basic_operational_items([
        "(4) Runway Information: 02/20 (3000m x 45m)", "(5) PAPI Information: 287m,", "3 degrees.", "1.2. Inherent Attributes"
    ], english=True) == ["Runway Information: 02/20 (3000m x 45m)", "PAPI Information: 287m, 3 degrees."]


def test_source_english_is_not_professionalized_or_generated():
    fact = agent.source_record_facts("甲机场", [record("盲降进近。", "Blind landing approach.")], category="core")[0]
    assert fact.en == "Blind landing approach."
    assert fact.source_text_en == fact.en
    assert fact.english_source_record_id
    assert agent.validate_bilingual_facts([fact])
    missing = agent.source_record_facts("甲机场", [record("机场存在风切变风险。")], category="core")[0]
    assert missing.en == ""
    assert missing.english_source == "manual_coverage_gap"
    assert agent.validate_bilingual_facts([missing])


def test_attributes_cannot_be_promoted_to_typical_events():
    assert agent.typical_source_quality_issue("机场标高：7358ft", "典型不安全事件")
    assert agent.typical_source_quality_issue("三类综合类复杂机场", "典型不安全事件")


def test_raw_source_preserves_unknown_runway_condition_and_does_not_polish():
    zh = "使用20号跑道时注意坡度。"
    fact = agent.source_record_facts("甲机场", [record(zh, "When using Runway 20, note the slope.")], category="core")[0]
    assert fact.zh == zh
    assert not fact.polish_applied
    assert fact.source_record_ids == ("parent",)
    assert fact.english_source_page == "20"
    assert agent.chinese_fact_output(fact) == zh.rstrip("。")


def test_arrival_only_source_is_not_selected_for_departure():
    fact = agent.source_record_facts("甲机场", [dict(record("进近时注意地形。", "Terrain on approach."), role_scope=("arrival",))], category="core")[0]
    duty = CalendarEvent(uid="d", summary="9C7605 甲机场→乙机场", start=datetime(2026, 10, 26, 9),
                         end=datetime(2026, 10, 26, 11), description="", location="", properties={})
    selected = agent.prepare_operational_facts(duty, "甲机场", date(2026, 10, 26), [fact], max_items=1, exclusion_log=[])
    assert not selected


def test_existing_continuous_and_noncontinuous_grouping_is_preserved():
    assert [[item.flight_number for item in group] for group in agent.split_flight_prep_groups_by_flight_number(
        [event("9C7605"), event("9C7606")])] == [["9C7605", "9C7606"]]
    assert [[item.flight_number for item in group] for group in agent.split_flight_prep_groups_by_flight_number(
        [event("9C7289"), event("9C7420")])] == [["9C7289"], ["9C7420"]]


def test_raw_fact_coverage_has_no_twelve_paragraph_budget():
    duty = CalendarEvent(uid="coverage", summary="9C7605 甲机场→乙机场", start=datetime(2026, 10, 26, 9),
                         end=datetime(2026, 10, 26, 11), description="", location="", properties={})
    facts = [agent.source_record_facts("甲机场", [dict(record(f"滑行道T{i}存在限制。", f"Taxiway T{i} has a restriction."), source_record_id=f"source-{i}")], category="core")[0]
             for i in range(1, 25)]
    assert len(agent.prepare_operational_facts(duty, "甲机场", date(2026, 10, 26), facts, max_items=1, exclusion_log=[])) == 24


def test_both_renderers_use_unordered_airport_paragraphs():
    duty = CalendarEvent(uid="format", summary="9C7605 甲机场→乙机场", start=datetime(2026, 10, 26, 9),
                         end=datetime(2026, 10, 26, 11), description="", location="", properties={})
    airports = list(duty.route)
    typical = {airport: [agent.BilingualFact("incident", "曾发生滑行偏差。", "A taxi deviation occurred.", airport=airport, category="typical")] for airport in airports}
    core = {airport: [agent.BilingualFact("core", "滑行道较窄。", "The taxiway is narrow.", airport=airport, category="core")] for airport in airports}
    zh = agent.render_chinese_briefing(duty, date(2026, 10, 26), {}, [], typical, core)
    en = agent.render_english_briefing(duty, date(2026, 10, 26), {}, [], typical, core)
    assert "典型不安全事件：\n\n" in zh
    assert "Typical unsafe events:\n\n" in en
    assert "1. " not in zh and "1. " not in en
    assert "机场典型不安全事件：" not in zh
