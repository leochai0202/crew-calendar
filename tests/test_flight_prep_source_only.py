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


def test_full_chapter_unknown_sections_and_record_boundaries():
    typical, core = agent.scan_chapter_source_records([
        "一、典型不安全事件", "1.曾发生滑行偏差。", "二、核心威胁",
        "1.指挥特点：", "（1）进近时先证实跑道。", "2.新版本特别说明：",
        "跑道坡度为0.8%，着陆时注意。", "三、运行特点", "（一）离场：",
        "1.起飞后按SID爬升。", "版本：20990101 修订日期：2099.1.1 页码：10",
        "爬升期间不得提前转弯。", "（二）进场：", "1.着陆后快速脱离。",
    ])
    assert typical == ["曾发生滑行偏差。"]
    assert any("0.8%" in item for item in core)
    assert not any("先证实跑道" in item and "0.8%" in item for item in core)
    assert any(item.startswith("离场：") and "SID" in item and "不得提前" in item for item in core)
    assert any(item.startswith("进场：") and "快速脱离" in item for item in core)
    assert not any("版本" in item for item in core)


def test_operational_value_filter_distinguishes_communication_from_contacts():
    for text in ("酒店接送信息：班车每日到达。", "廊桥密码：1234。", "联系电话：123456。", "ATIS 123.45"):
        assert agent.source_operational_value_issue(text)
    for text in ("通讯失效后按航图执行。", "滑行时管制可能要求提前换频，注意证实。", "收到离场许可后按要求复诵。", "A hotel building is an obstacle near Runway 13."):
        assert not agent.source_operational_value_issue(text)
    assert agent.source_operational_value_issue("The password for the covered bridge is provided by staff.")


def test_phase_label_does_not_hide_detached_numeric_fragment():
    for text in ("进场：速度160节。", "离场：高度3000米。", "地面：不超过20节。"):
        assert agent.manual_source_quality_issue(text) == "detached_operational_fragment"
    assert not agent.manual_source_quality_issue("进场：通过定位点时速度不超过160节。")


def test_verbatim_guard_uses_real_source_controls_not_legacy_editor_controls():
    fact = agent.source_record_facts("甲机场", [record("确认PDC之后无需复诵，直接联系地面。", "After confirming PDC, contact ground directly.")], category="core")[0]
    assert not agent.validate_source_semantic_preservation(fact)
    from dataclasses import replace
    assert agent.validate_source_semantic_preservation(replace(fact, text_zh="PDC。"))


def test_source_token_equivalence_does_not_change_source_numbers():
    assert agent.manual_pairing_tokens("高度20000ft。") == agent.manual_pairing_tokens("Altitude 20,000 ft.")
    assert agent.manual_pairing_tokens("机位s126。") == agent.manual_pairing_tokens("Stand S126.")
    assert agent.manual_pairing_tokens("高度20000ft。") != agent.manual_pairing_tokens("Altitude 21,000 ft.")


def test_english_unumbered_prose_and_unknown_numbered_sections_are_scanned():
    facts = agent.extract_english_manual_facts("""Example Airport (AAA/AAAA)
Responsibility Division: Test
1. New operating restriction: Aircraft must remain on the taxi route.
II. Core Threats
Terrain requires careful monitoring during approach.
""")
    assert any("Aircraft must remain" in fact.text for fact in facts)
    assert any("Terrain requires" in fact.text for fact in facts)
    assert all("Responsibility" not in fact.text for fact in facts)


def test_verbatim_renderer_removes_only_structural_labels():
    for source, expected in (("地形：周边有山。", "周边有山"), ("道面特点：跑道坡度较大。", "跑道坡度较大"),
                             ("ATC要求：保持5000ft。", "ATC要求：保持5000ft")):
        fact = agent.source_record_facts("甲机场", [record(source, "Source text.")], category="core")[0]
        assert agent.chinese_fact_output(fact) == expected


def test_english_other_section_is_scanned_and_administration_is_excluded():
    facts = agent.extract_english_manual_facts("""IV. Other
1. In case of radio failure, follow the published procedure.
2. Hotel accommodation: staff shuttle information.
""")
    assert len(facts) == 1
    assert "radio failure" in facts[0].text


def test_basic_attributes_pair_in_same_generic_phase_as_english_basic_fields():
    assert agent._chinese_manual_fact_phase("机场标高：7000ft", "core") == "operations"
    assert agent._chinese_manual_fact_phase("跑道信息：01/19（3000m×45m）", "core") == "operations"
    assert agent._chinese_manual_fact_phase("PAPI信息：入口内300m，3度。", "core") == "operations"


def test_basic_field_pairing_uses_field_identity_not_translated_position():
    english = [agent.ManualEnglishFact("PAPI Information: 300m, 3 degrees.", "core", "ground", 0),
               agent.ManualEnglishFact("Airport elevation: 7000ft.", "core", "operations", 1)]
    paired = agent.pair_manual_english_items(["机场标高：7000ft", "PAPI信息：300m，3度。"], english, "core")
    assert paired == [english[1].text, english[0].text]
    assert agent.manual_source_quality_issue("固有属性 是/否 备注 是否为高原机场 否 是否存在EOSID 否") == "unparsed_attribute_table"
