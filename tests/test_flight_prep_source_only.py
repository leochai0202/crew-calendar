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


def test_parallel_basic_extractors_do_not_create_ambiguous_duplicate_pairing():
    items = agent.deduplicate_manual_items(["机场标高：13ft。", "运行特点：机场标高：13ft。"])
    assert len(items) == 1
    english = [agent.ManualEnglishFact("Airportelevation:13 ft", "core", "core", 0)]
    assert agent.pair_manual_english_items(items, english, "core") == [english[0].text]


def test_inline_list_boundary_is_not_a_configuration_and_speed_condition():
    _, core = agent.scan_chapter_source_records([
        "二、核心威胁", "1. 注意观察。 2、速度160节。",
        "3. 顺风时建议设置形态2，速度160节。",
    ])
    assert "速度160节。" in core
    assert agent.manual_source_quality_issue("速度160节。") == "detached_operational_fragment"
    assert any("顺风" in item and "形态2，速度160" in item for item in core)


def test_only_compilation_citation_is_hidden_not_operating_chart_references():
    fact = agent.source_record_facts("甲机场", [record("二类复杂机场，注意操作限制（参考EFB-机场特点汇总-公司复杂机场分类规则）。", "Source.")], category="core")[0]
    rendered = agent.chinese_fact_output(fact)
    assert "二类复杂机场，注意操作限制" in rendered
    assert "机场特点汇总" not in rendered
    assert agent.strip_compilation_citations("一类复杂机场（参考三-（6）/EFB-机场特点汇总-操纵权限规则）。") == "一类复杂机场。"
    assert "禁止" in agent.strip_compilation_citations("限制（参考EFB-机场特点汇总，同时禁止起飞）。")
    other = agent.source_record_facts("甲机场", [record("无线电失效时按机场细则3.4执行。", "Source.")], category="core")[0]
    assert "机场细则3.4" in agent.chinese_fact_output(other)
    assert agent.source_operational_value_issue("请通过自动 扶梯到达航站列车。")


def test_page_break_admin_field_does_not_remove_previous_operating_restriction():
    _, core = agent.scan_chapter_source_records([
        "二、核心威胁", "1.加油时上客必须通知消防保障。",
        "页码：2", "廊桥密码：1234", "2.起飞时遵守SID限制。",
    ])
    assert any("通知消防" in item and "密码" not in item for item in core)
    assert any("SID" in item for item in core)


def test_conditional_parent_survives_subitems_and_page_break_in_both_languages():
    _, core = agent.scan_chapter_source_records([
        "6. 特定环境运行特点", "6.8. 冬季运行程序提示：",
        "(1) 必须先取得许可。", "页码：12", "(2) 禁止进入跑道后实施。",
        "6.9. 夜间注意滑行灯。",
    ])
    winter = [item for item in core if "冬季" in item]
    assert len(winter) == 1
    assert "取得许可" in winter[0] and "禁止" in winter[0]
    assert agent.detected_season_scope(winter[0])
    fact = agent.source_record_facts("甲机场", [record(winter[0], "Winter: obtain clearance. Do not use the runway.")], category="core")[0]
    exclusions = []
    assert agent.filter_fact_for_duty(fact, event(), date(2026, 8, 1), exclusions) is None
    assert exclusions and "父条目" in exclusions[0]["reason"]
    kept = agent.filter_fact_for_duty(fact, event(), date(2026, 1, 1), [])
    assert kept.zh == fact.zh and kept.en == fact.en
    facts = agent.extract_english_manual_facts("""VI. Operational characteristics
6.8. Winter operating procedures:
(1) Obtain clearance first.
(2) Do not carry out the procedure on the runway.
6.9. Use lights at night.
""")
    winter_en = [item.text for item in facts if "Winter" in item.text]
    assert len(winter_en) == 1 and "Obtain clearance" in winter_en[0] and "runway" in winter_en[0]


def test_source_page_lookup_tracks_continuation_and_refuses_ambiguous_duplicates():
    pages = agent.source_item_page_map([
        "页码：10", "1.通过定位点时必须保持", "页码：11", "5000ft。", "2.跑道有坡度。",
        "页码：12", "3.跑道有坡度。",
    ], ["通过定位点时必须保持5000ft。", "跑道有坡度。"])
    assert pages["通过定位点时必须保持5000ft。"] == "10-11"
    assert "跑道有坡度。" not in pages


def test_english_title_variants_separate_code_fields_and_multiple_chapters():
    chapters = agent.build_english_manual_index("""页码：10
Alpha Field（AAA/AAAA）
Updated on 2099.1.1
页码：20
Beta International Airport
Responsibility Division: Test
1. Basic information
(1) ICAO/IATAcodes:BBBB/BBB
页码：30
Alpha Field(AAA/AAAA)
Updated on 2099.2.1
页码：48
Continuation of last chapter.
""")
    assert [chapter["icao"] for chapter in chapters] == ["AAAA", "BBBB", "AAAA"]
    assert len(agent.match_english_manual_chapters(chapters, "AAAA")) == 2
    assert agent.match_english_manual_chapter(chapters, "BBBB")["start_page"] == 20
    assert chapters[-1]["end_page"] == 48
    assert not agent.match_english_manual_chapters(chapters, "CCCC")
    isolated = agent.build_english_manual_index("""页码：1
Unidentified Airport
Responsibility Division: Test
页码：2
Other Airport (BBB/BBBB)
Updated on 2099.1.1
(1) ICAO/IATAcodes:BBBB/BBB
""")
    assert len(isolated) == 1 and isolated[0]["name"] == "Other"


def test_operating_tokens_recover_boundaries_without_ignoring_real_differences():
    assert agent.manual_pairing_tokens("执行20R RNP进近，管制可能指令。") == agent.manual_pairing_tokens("The control may instruct an RNP20R approach.")
    assert agent.manual_pairing_tokens("01L落地后经过J14。") == agent.manual_pairing_tokens("After landing at01L pass J14.")
    assert agent.manual_pairing_tokens("执行20R RNP进近。") != agent.manual_pairing_tokens("RNP20L approach.")
    assert "AT01L" in agent.manual_pairing_tokens("Direct to AT01L.")
    assert "ATC" not in agent.manual_pairing_tokens("Control aircraft speed.")
    assert agent.manual_pairing_tokens("显示stop和ok。") == agent.manual_pairing_tokens('Display "Stop" and "OK".')
    assert agent.manual_pairing_tokens("BKKTMA内最小间隔3海里。") == agent.manual_pairing_tokens("Minimum separation 3 nautical miles inBKKTMA.")
    assert agent.manual_pairing_tokens("BKKTMA内最小间隔3海里。") == agent.manual_pairing_tokens("Minimum separation 3 NM inBKKTMA.")
    assert agent.manual_pairing_tokens("BKKTMA内最小间隔3海里。") != agent.manual_pairing_tokens("Minimum separation 5 nautical miles inBKKTMA.")
    assert agent.manual_pairing_tokens("滑行高冲突区，指令及时复诵。") == agent.manual_pairing_tokens("Read back ATC instructions in taxi conflict areas.")
    assert "ATC" not in agent.manual_pairing_tokens("机组复诵起落架指令。")
    assert "ATIS" in agent.manual_pairing_tokens("运行方向切换时听通播。")


def test_semantic_equivalents_keep_negated_restrictions_and_reject_wrong_concepts():
    assert not agent.bilingual_semantic_mismatches("进场后雷达引导，计算高距比。", "Radar guidance on arrival; calculate the altitude-to-range ratio.")
    assert not agent.bilingual_semantic_mismatches("确认PDC后无需复诵。", "Once PDC is confirmed, there is no need for repetition.")
    assert "readback_requirement_polarity" in agent.bilingual_semantic_mismatches("确认PDC后无需复诵。", "PDC readback is required.")
    assert "readback_requirement_polarity" in agent.bilingual_semantic_mismatches("必须复诵PDC。", "PDC readback is not required.")
    assert agent.bilingual_semantic_mismatches("转向五边。", "Five-sided Chaos.")
    assert agent.bilingual_semantic_mismatches("盲降进近。", "An emergency landing approach.")


def test_communication_payload_survives_continuation_but_bare_frequency_does_not():
    _, items = agent.scan_chapter_source_records([
        "三、运行特点", "（一）地面", "1.现场/签派频率：AIRPORTOPS，",
        "频率123.45，有停机位问题时通过该频率联系。",
    ])
    assert any("AIRPORTOPS" in item and "停机位" in item for item in items)
    assert not agent.manual_source_quality_issue(items[0])
    assert agent.source_operational_value_issue("ATIS 123.45")
    assert agent.source_operational_value_issue("现场/签派频率：现场130.5，内场129.8。")
    assert agent.source_operational_value_issue("现场/签派频率：现场频率130.5或129.8；公司签派频率130.5。")


def test_explicit_fly_to_prefix_uses_registry_aliases_and_keeps_history_neutral():
    registry = {"AAAA": {"canonical_zh": "甲地机场"}, "BBBB": {"canonical_zh": "乙地机场"}, "CCCC": {"canonical_zh": "丙地机场"}}
    text = "甲地飞乙地管制可能要求直飞FIXAA。"
    routes = agent.record_route_scope({"category": "core"}, text, registry)
    assert routes == (("甲地机场", "乙地机场"),)
    assert agent.route_scope_matches_duty(routes, {("甲地机场", "乙地机场")})
    assert not agent.route_scope_matches_duty(routes, {("乙地机场", "甲地机场")})
    assert not agent.route_scope_matches_duty(routes, {("甲地机场", "丙地机场")})
    assert agent.record_route_scope({"category": "typical"}, text, registry) == ()


def test_other_section_phase_is_equivalent_in_legacy_and_numbered_chapters():
    for title in ("四、其他", "7. 其他"):
        _, core = agent.scan_chapter_source_records([title, "1.无线电失效时按公布程序执行。"])
        assert core == ["运行特点：无线电失效时按公布程序执行。"]
        assert agent._chinese_manual_fact_phase(core[0], "core") == "operations"
    facts = agent.extract_english_manual_facts("""1. Overview
1.1. Basic Information
(1) Airportname: Example Airport
IV. Other
1. In case of radio failure follow the published procedure.
""")
    assert len(facts) == 1 and facts[0].phase == "operations"


def test_raw_seasonal_exclusion_does_not_require_removed_controls_or_allow_new_ones():
    from dataclasses import replace
    fact = agent.source_record_facts("甲机场", [record("冬季提前做好除冰。全年注意保持间隔。", "Winter deicing. Maintain separation all year.")], category="core")[0]
    kept = agent.filter_fact_for_duty(fact, event(), date(2026, 8, 1), [])
    assert kept is not None and "冬季" not in kept.zh
    assert kept.excluded_source_clauses
    assert not agent.validate_source_semantic_preservation(kept)
    assert agent.validate_source_semantic_preservation(replace(kept, text_zh=kept.zh + "提前复飞。"))
    assert agent.validate_bilingual_facts([kept])  # never publish a partially projected bilingual record


def test_decimal_slope_is_not_list_numbering_but_actual_numbering_still_fails():
    from dataclasses import replace
    duty = replace(event(), summary="9C7605 甲机场→乙机场")
    profile = {"name": "段洋硕"}
    typical = {airport: [] for airport in duty.route}
    core = {airport: [agent.BilingualFact("core", "0.59%为跑道坡度。", "Runway slope is 0.59%.", airport=airport, source_verbatim=True)] for airport in duty.route}
    content = agent.render_chinese_briefing(duty, date(2026, 8, 1), profile, [], typical, core)
    assert "核心威胁不得使用数字编号" not in agent.validate_content(content, duty, profile, list(duty.route), language="zh")
    numbered = content.replace("0.59%为跑道坡度。", "1. 跑道有坡度。")
    assert "核心威胁不得使用数字编号" in agent.validate_content(numbered, duty, profile, list(duty.route), language="zh")
    assert agent.clean_manual_item("0.59%为跑道坡度。") == "0.59%为跑道坡度。"
    assert agent.strip_manual_ordinal_prefix("3.2度下滑角") == "3.2度下滑角"
    assert agent.strip_manual_ordinal_prefix("3.2. 使用程序。") == "使用程序。"
    assert agent.strip_manual_ordinal_prefix("1.2021年7月曾发生事件。") == "2021年7月曾发生事件。"


def test_english_incidents_require_an_explicit_heading_not_a_prose_mention():
    for title in ("I. Typical Unsafe Incidents", "2. Typical Safety Events:", "3.4 Historical Safety Occurrences", "Detailed Description of Typical Unsafe Incidents (1) An event occurred."):
        assert agent._english_manual_heading(title) == ("typical", "incident")
    assert agent._english_manual_heading("Review typical unsafe events before departure.") != ("typical", "incident")
    facts = agent.extract_english_manual_facts("""II. Core Threats
1. Review typical unsafe events before departure.
""")
    assert facts and all(fact.category == "core" for fact in facts)


def test_explicit_operating_dates_exclude_expired_items_but_not_event_history():
    fact = agent.source_record_facts("甲机场", [record("2025年10月25日至2025年12月23日，滑行道施工关闭。", "Source.")], category="core")[0]
    assert agent.source_date_matches_target(fact, date(2025, 10, 26))
    assert not agent.source_date_matches_target(fact, date(2026, 10, 26))
    assert agent.filter_fact_for_duty(fact, event(), date(2026, 10, 26), []) is None
    from dataclasses import replace
    assert agent.source_date_matches_target(replace(fact, category="typical"), date(2026, 10, 26))
    no_year = replace(fact, text_zh="10月25日-12月23日，滑行道施工关闭。")
    assert agent.source_date_matches_target(no_year, date(2026, 10, 26))
    assert not agent.source_date_matches_target(no_year, date(2026, 8, 1))
    cross_year = replace(fact, text_zh="11月1日-2月28日，滑行道限制使用。")
    assert agent.source_date_matches_target(cross_year, date(2027, 1, 1))
    assert not agent.source_date_matches_target(cross_year, date(2027, 6, 1))


def test_mixed_role_original_record_splits_both_languages_under_same_parent(monkeypatch, tmp_path):
    original = "航路：进场时注意地形。进离场均需遵守程序。"
    english = "Terrain on arrival. Follow procedures for departures and arrivals."
    data = {"甲机场": {"source_verbatim": True, "core_threats": [original],
                          "english_core_threats": [english], "manual_english_available": True,
                          "source_page": "10", "english_source_page": "20", "matched_header": "甲机场运行特点"}}
    monkeypatch.setattr(agent, "manual_airport_data", lambda *args, **kwargs: (data, str(tmp_path / "knowledge/manual.pdf"), 20990101, "PDF", []))
    _, _, records, *_ = agent.airport_risks(tmp_path, ["甲机场"], {"甲机场": "AAAA"}, 1)
    facts = agent.source_record_facts("甲机场", records["甲机场"], category="core")
    assert len(facts) == 2
    assert facts[0].parent_record_id == facts[1].parent_record_id
    assert facts[0].fact_id != facts[1].fact_id
    assert all(fact.en in english for fact in facts)
    assert all(original in fact.source_original_texts for fact in facts)
    from dataclasses import replace
    departure = replace(event(), summary="9C7605 甲机场→乙机场")
    selected = agent.prepare_operational_facts(departure, "甲机场", date(2026, 8, 1), facts, max_items=1, exclusion_log=[])
    assert len(selected) == 1 and "地形" not in selected[0].zh and "Terrain" not in selected[0].en
    assert not agent.validate_bilingual_facts(selected)
    assert not agent.validate_source_semantic_preservation(selected[0])


def test_administrative_sentences_do_not_delete_refuelling_operating_restrictions():
    zh = "地面：加油时要求在电子平板输入姓名作为签名。加油时禁止上客。如果上客需要通知消防车。廊桥密码1234。"
    clean = agent.filter_source_administrative_sentences(zh)
    assert clean == "地面：加油时禁止上客。如果上客需要通知消防车。"
    en = "During refueling, enter a name as a signature. Boarding is prohibited during refueling. If boarding is necessary, notify fire trucks. Thecodeforthejetbridgeis1234."
    kept = agent.filter_source_administrative_sentences(en, english=True)
    assert "Boarding is prohibited" in kept and "notify fire trucks" in kept
    assert "signature" not in kept and "jetbridge" not in kept
    assert agent.filter_source_administrative_sentences("During refueling, record the signature and notify fire trucks.", english=True) == "During refueling, record the signature and notify fire trucks."


def test_inherited_condition_continuation_keeps_its_original_parent():
    text = "遇到军方活动时，过FIXAA高度3600m。距35号跑道37nm，五边通常顺风较大。进离场均需遵守程序。"
    clauses = agent.split_source_record_clauses(text, preserve_condition_bundles=True)
    assert any("军方活动" in clause.text and "37nm" in clause.text for clause in clauses)
    assert not any("37nm" in clause.text and "军方活动" not in clause.text for clause in clauses)
    assert clauses[-1].text == "进离场均需遵守程序。"
    assert not clauses[-1].condition_scope


def test_tcas_topic_does_not_disappear_behind_an_arrival_phase():
    fact = agent.BilingualFact("x", "进近阶段曾触发TA/RA。", "", operational_phase="arrival")
    assert agent.classify_fact_topic(fact) == "traffic_tcas"


def test_ground_runway_vacating_restrictions_are_arrival_only():
    for text in ("17号落地塔台可能指挥A4直角脱离。", "脱离时注意滑行道标志。", "着陆后使用快速脱离道。"):
        assert agent.explicit_role_scope(text, "ground") == ("arrival",)
    assert agent.explicit_role_scope("起飞前注意滑行道标志。", "ground") == ("departure",)
    assert not agent.explicit_role_scope("滑行时注意道面标志。", "ground")
