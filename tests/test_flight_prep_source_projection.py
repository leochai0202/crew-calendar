from datetime import date, datetime

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


def source_fact(zh, en):
    return agent.attach_source_semantics(agent.BilingualFact(
        "source:one", zh, en, airport="甲机场", category="core",
        source="PDF", source_authority="latest_airport_manual",
        source_verbatim=True, source_text_zh=zh, source_clauses=(zh,),
        source_text_en=en, source_original_texts=(zh,),
        source_fact_ids=("source:one",), source_record_ids=("parent:one",),
        english_source="source_backed", manual_english_counterpart=True,
        english_source_record_id="english:parent",
    ))


def duty():
    return CalendarEvent(uid="test", summary="9C0001 甲机场→乙机场",
                         start=datetime(2026, 10, 26, 9), end=datetime(2026, 10, 26, 11),
                         description="", location="", properties={})


def test_papi_labels_retain_runway_anchors_and_do_not_hide_changed_runways():
    zh = "PAPI信息：08：入口内450米，MEHT20.9m；26：入口内460米，MEHT21.5m。"
    en = "PAPI Information: RWY 08: 450 m inside threshold, MEHT 20.9 m; RWY 26: 460 m inside threshold, MEHT 21.5 m."
    assert agent.manual_pairing_tokens(zh) == agent.manual_pairing_tokens(en)
    assert {"RWY08", "RWY26"} <= agent.manual_pairing_tokens(zh)
    assert agent.validate_bilingual_facts([source_fact(zh, en)]) == []
    assert agent.validate_bilingual_facts([source_fact(zh, en.replace("RWY 26", "RWY 27"))])
    assert agent.validate_bilingual_facts([source_fact(zh, en.replace("450 m", "460 m").replace("460 m inside threshold, MEHT 21.5", "450 m inside threshold, MEHT 21.5"))])
    assert agent.validate_bilingual_facts([source_fact(zh, en.replace("RWY 08:", "RWY 08: 26:"))])
    assert not agent.bilingual_keyed_table_mismatches("PAPI信息：暂无可用数据。", "PAPI Information: Data unavailable.")


def test_stop_taxi_action_is_not_a_displayed_stop_legend():
    fact = source_fact("立即停止滑行并通报ATC。", "Stop taxi and notify ATC immediately.")
    assert agent.validate_bilingual_facts([fact]) == []
    assert fact.en == "Stop taxi and notify ATC immediately."
    assert "STOP" in agent.manual_pairing_tokens('The display reads "Stop".')
    assert agent.manual_pairing_tokens("显示STOP。") != agent.manual_pairing_tokens('The display reads "OK".')


def test_landing_context_and_directing_aircraft_are_comparison_only():
    en = "After the 08L aircraft landed, when directing GREEN 1 aircraft, the T3 sign was absent."
    zh = "08L落地后，指挥GREEN 1时，T3标牌缺失。"
    assert agent.manual_pairing_tokens(zh) == agent.manual_pairing_tokens(en)
    assert "ATC" not in agent.manual_pairing_tokens("When directing aircraft, ground crew uses hand signals.")
    fact = source_fact(zh, en)
    assert fact.en == en and not agent.validate_bilingual_facts([fact])


def test_original_recite_pdc_is_bounded_and_keeps_requirement_polarity():
    fact = source_fact("无需复诵PDC。", "No need to recite PDC")
    assert agent.validate_bilingual_facts([fact]) == []
    assert fact.en == "No need to recite PDC"
    assert agent.bilingual_semantic_mismatches("必须复诵PDC。", fact.en)
    assert agent.bilingual_semantic_mismatches("复诵PDC。", "Recite a poem.")


def test_source_instrument_range_finder_equivalence_is_not_generic_blind_landing():
    en = "The blind landing range finder has a position error relative to the runway end."
    fact = source_fact("盲降测距仪与跑道头位置有误差。", en)
    assert not agent.validate_bilingual_facts([fact])
    assert fact.en == en
    assert agent.bilingual_semantic_mismatches("盲降进近。", "Blind landing approach.")
    assert agent.bilingual_semantic_mismatches("盲降测距仪。", "Emergency landing range finder.")


def test_season_filter_projects_the_same_parent_english_without_translation():
    zh = "春季多雷暴，常伴风切变。夏秋季有台风及雷暴。"
    en = "Spring thunderstorms are often accompanied by wind shear. During summer and autumn, typhoons bring thunderstorms."
    fact = source_fact(zh, en)
    selected = agent.filter_fact_for_duty(fact, duty(), date(2026, 10, 26), [])
    assert selected is not None
    assert selected.zh == "夏秋季有台风及雷暴。"
    assert selected.en == "During summer and autumn, typhoons bring thunderstorms."
    assert selected.en in en
    assert selected.source_text_en == en
    assert selected.source_record_ids == fact.source_record_ids
    assert selected.english_source_record_id == fact.english_source_record_id
    assert agent.validate_bilingual_facts([selected]) == []
    assert agent.validate_source_semantic_preservation(selected) == []


def test_ambiguous_seasonal_projection_still_fails_safe():
    zh = "春季有风切变。夏秋季有台风。"
    en = "Spring wind shear occurs. During summer and autumn, typhoons occur. During summer and autumn, typhoons occur."
    selected = agent.filter_fact_for_duty(source_fact(zh, en), duty(), date(2026, 10, 26), [])
    assert selected is not None and not selected.en
    assert selected.english_source == "manual_coverage_gap"
    assert agent.validate_bilingual_facts([selected])
    assert not agent.unique_source_english_span("夏季有台风。", "Summer has no typhoons. Spring has wind shear.")
    assert not agent.unique_source_english_span("夏季必须注意台风。", "Summer typhoons occur. Spring has wind shear.")


def test_comparison_repairs_only_whitespace_not_original_weather_wording():
    zh = "夏秋季有台风及雷 暴。"
    en = "During summer and autumn, typhoons bring thunderstorms."
    assert agent.unique_source_english_span(zh, "From latespring to summer, thunderstorms bring wind shear. " + en) == en
    assert zh == "夏秋季有台风及雷 暴。"


def test_two_chinese_records_share_disjoint_original_english_sentences():
    zh = ["春季多雷暴及风切变。", "夏秋季有台风。"]
    en = "Spring thunderstorms bring wind shear. During summer and autumn, typhoons occur."
    candidates = [agent.ManualEnglishFact(en, "core", "core", 0)]
    paired = agent.pair_manual_english_items(zh, candidates, "core")
    assert paired == ["Spring thunderstorms bring wind shear.", "During summer and autumn, typhoons occur."]
    assert all(value in en for value in paired)


def test_cross_phase_projection_requires_strong_anchors_and_preserves_parent():
    zh = ["离场：杰普逊航图没有单发离港程序，参考EFB航图。", "运行特点：PBN单发程序适用于08号和26号跑道。"]
    en = "PBN single-engine departure procedures apply to Runways 08 and 26. The JEPPESEN chart has no single-engine departure procedures; Foreign pilots should use the EFB chart."
    paired = agent.pair_manual_english_items(zh, [agent.ManualEnglishFact(en, "core", "operations", 0)], "core")
    assert paired == ["The JEPPESEN chart has no single-engine departure procedures; Foreign pilots should use the EFB chart.", "PBN single-engine departure procedures apply to Runways 08 and 26."]
    facts = [agent.verbatim_manual_fact("甲机场", {
        "text_zh": chinese, "text_en": english, "category": "core",
        "source_record_id": f"parent:{index}", "source_original_text_en": en,
    }, index) for index, (chinese, english) in enumerate(zip(zh, paired))]
    assert len({fact.english_source_record_id for fact in facts}) == 1
    assert all(fact.source_text_en == en for fact in facts)
    assert agent.validate_selected_fact_id_parity(facts) == []


def test_shared_span_cannot_be_borrowed_twice_or_without_a_concept():
    item = "离场：杰普逊未载单发离港程序，参考EFB。"
    english = "The JEPPESEN chart has no single-engine departure procedures; Foreign pilots should use the EFB chart."
    assert agent.project_shared_english_records([item, item], [agent.ManualEnglishFact(english, "core", "operations", 0)], "core", ["", ""]) == ["", ""]
    assert not agent.unique_source_english_span("注意保持间隔。", "Keep separation. Review the chart.")
    assert agent.source_projection_controls_match("需要提醒外籍参考EFB航图。", "Foreign pilots should refer to the EFB chart.")
    assert agent.source_projection_controls_match("不得使用该程序。", "Must not use the procedure.")
    assert agent.source_projection_controls_match("8号机位使用EFB。", "Stand No. 8 uses EFB.")


def test_conditional_english_parent_is_never_projected_as_unconditional_children():
    english = "When using Runway 08, follow the departure procedure. Use the EFB chart."
    assert agent.project_shared_english_records(
        ["离场：08号跑道离场按程序。", "离场：参考EFB航图。"],
        [agent.ManualEnglishFact(english, "core", "operations", 0)], "core", ["", ""],
    ) == ["", ""]
    assert not agent.unique_source_english_span("注意风切变。", "When using Runway 08, follow the procedure. Wind shear occurs.")


def test_engine_out_acceleration_height_is_departure_not_airport_neutral():
    for text in ("按性能计算调整单发加速高度。", "按公布EOSID执行。", "单发离港按公布程序。"):
        phase = agent._source_clause_phase(text, "")
        assert phase == "departure"
        assert agent.explicit_role_scope(text, phase) == ("departure",)
    assert not agent.explicit_role_scope("跑道坡度较大，注意地形。", "terrain")
    phase = agent._source_clause_phase("注意修改性能复飞页面的复飞单发加速高度。", "")
    assert phase == "approach"
    assert agent.explicit_role_scope("注意修改复飞单发加速高度。", phase) == ("arrival",)


def test_gate_access_administration_is_not_an_aircraft_surface_restriction():
    for text in ("机组进入登机口时请拨打门禁电话开门。", "For flights entering boarding gates, call the access control phone to open the door."):
        assert agent.source_operational_value_issue(text) == "passenger_or_staff_access_administration"
    assert not agent.source_operational_value_issue("滑行靠近登机口时注意飞机净距，必要时电话联系机务。")
    assert not agent.source_operational_value_issue("Contact operations on this frequency for TOBT and stand information.")


def test_border_administration_does_not_leave_an_orphaned_second_sentence():
    chinese = "国际航班机组边检请走人工，自助系统每天只能通过一次。容易被困在自助通道，需要工作人员退回。"
    english = "Manual immigration clearance is recommended. Self-service kiosks are restricted to one entry each day."
    assert not agent.filter_source_administrative_sentences(chinese)
    assert not agent.filter_source_administrative_sentences(english, english=True)
    assert not agent.source_operational_value_issue("Request ATC clearance before crossing the runway.")
    assert agent.filter_source_administrative_sentences("海关飞机停放区域影响滑行道净距，注意飞机翼尖。")


def test_source_procedure_subject_is_not_stripped_from_short_reference():
    for label in ("减噪程序", "释压程序", "通信失效程序", "通讯失效程序", "应急程序"):
        zh = label + "：见机场细则。"
        assert agent.chinese_fact_output(source_fact(zh, "Refer to aerodrome procedures.")) == zh.rstrip("。")


def test_structural_equivalent_is_bound_but_missing_atis_is_not_ignored():
    zh = ["离场：早出港航班参考实际通播和放行选择离场跑道。"]
    english = "For early departure flights, select the departure runway based on real-time air traffic updates and clearance requirements."
    candidates = [agent.ManualEnglishFact("Follow the published departure procedure.", "core", "departure", 0),
                  agent.ManualEnglishFact(english, "core", "departure", 1)]
    paired = agent.pair_manual_english_items(zh, candidates, "core")
    assert paired == [english]
    assert agent.validate_bilingual_facts([source_fact(zh[0], paired[0])])  # exact ATIS source detail still missing


def test_unnumbered_runway_and_direction_parents_keep_original_boundaries():
    english = agent.extract_english_manual_facts("""V. Post-landing Taxi Operations
After landing RWY 08, vacate via T1.
DepartureTaxi(RWY26):
Taxi via T2 and hold short of T3.
SouthboundArrival
Use the published arrival.
VI. Departure
Follow the SID.
""")
    assert english[0].phase == "landing_ground"
    assert "DepartureTaxi" not in english[0].text
    assert english[1].text == "DepartureTaxi(RWY26): Taxi via T2 and hold short of T3."
    assert english[1].phase == "ground"
    assert "SouthboundArrival" in english[2].text and english[2].phase == "arrival"
    assert english[-1].phase == "departure"
    _, chinese = agent.scan_chapter_source_records([
        "三、运行特点", "RWY08离场滑行：", "（1）经T1滑行。", "（2）T2前等待。",
        "RWY26离场滑行：", "（1）经T3滑行。",
    ])
    assert len(chinese) == 2
    assert "RWY08" in chinese[0] and "T1" in chinese[0] and "T2" in chinese[0]
    assert "RWY26" in chinese[1] and "T3" in chinese[1]
    assert not agent.source_parent_has_condition("飞机在30号跑道进近过程中，09：")
    siblings = agent.extract_english_manual_facts("""IV. Arrival Approach Landing
1. Precautions:
(1) When using RWY08, note the following:
Maintain 3000ft.
(2) When using RWY26, maintain 4000ft.
""")
    assert len(siblings) == 2
    assert "RWY26" not in siblings[0].text
    assert "RWY08" not in siblings[1].text
    _, siblings_zh = agent.scan_chapter_source_records([
        "三、运行特点", "4.注意事项：", "（1）使用RWY08时：", "保持3000ft。",
        "（2）使用RWY26时保持4000ft。",
    ])
    assert len(siblings_zh) == 2
    assert "RWY26" not in siblings_zh[0]
    assert "RWY08" not in siblings_zh[1]


def test_chinese_heading_with_english_name_is_not_an_english_chapter():
    text = """页码：20
甲乙机场运行特点 Example Airport (AAAA/AAA)
更新日期2026.10.19
责任中队：四中队
一、位置：机场周边平坦。
页码：21
丙丁机场运行特点 Other Airport (BBBB/BBB)
二、运行特点：注意地形。
页码：100
Example Airport (AAAA/AAA)
Updated on 2026.10.19
Responsibility Division: Fourth Division
I. Core Threats
1. Runway 08 has a displaced threshold.
页码：102
Other Airport (BBBB/BBB)
Updated on 2026.10.19
II. Core Threats
1. Terrain is high to the north.
"""
    chapters = agent.build_english_manual_index(text)
    assert [(c["icao"], c["start_page"], c["end_page"]) for c in chapters] == [
        ("AAAA", 100, 101), ("BBBB", 102, 102),
    ]
    assert agent.match_english_manual_chapters(chapters, "AAAA") == chapters[:1]
