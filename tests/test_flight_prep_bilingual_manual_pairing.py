from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


REAL_MANUAL = next(
    (Path(__file__).parents[1] / "knowledge" / "pdf").glob("*20260924*.pdf")
)


def _manual_pages(*pages: int) -> str:
    return "\n".join(
        agent.extract_pdf_layout_text(str(REAL_MANUAL), page, page)
        for page in pages
    )


def _manual_record(
    text_zh: str,
    text_en: str,
    *,
    category: str = "core",
    phase: str = "arrival",
) -> dict[str, object]:
    return {
        "airport": "测试机场",
        "source": "PDF",
        "source_authority": "latest_manual",
        "source_file": "knowledge/pdf/manual.pdf",
        "source_version": "20260924",
        "source_page": "10",
        "source_heading": "测试机场运行特点",
        "source_section": "核心威胁",
        "source_record_id": f"record:{text_zh}",
        "category": category,
        "operational_phase": phase,
        "text_zh": text_zh,
        "text_en": text_en,
        "manual_english_available": True,
        "english_source": "source_backed" if text_en else "manual_coverage_gap",
        "english_airport_name": "Test International",
    }


def test_structural_pairing_keeps_all_three_source_backed_facts() -> None:
    chinese = ["进场：事实甲。", "进场：事实乙。", "进场：事实丙。"]
    english = agent.extract_english_manual_facts(
        """
        II. Core Threats
        III. Operational Characteristics
        (4) Entry:
        1. Fact A.
        2. Fact B.
        3. Fact C.
        """
    )

    assert agent.pair_manual_english_items(chinese, english, "core") == [
        "Fact A.",
        "Fact B.",
        "Fact C.",
    ]


def test_manual_critical_tokens_match_runway_distance_gradient_and_fpa() -> None:
    chinese = "13号跑道入口内移150m，下降梯度5.7%，FPA3.26。"
    english = (
        "The Runway 13 threshold is displaced by 150 meters; "
        "the descent gradient is 5.7%, FPA 3.26."
    )
    fact = agent.source_record_facts(
        "测试机场", [_manual_record(chinese, english)], category="core"
    )[0]

    assert fact.english_source == "source_backed"
    assert agent.validate_bilingual_facts([fact]) == []


def test_manual_pairing_treats_chinese_control_as_atc_equivalent() -> None:
    assert agent.manual_pairing_tokens("管制指挥直飞A点。") == {"ATC"}
    assert agent.manual_pairing_tokens("ATC clears direct to Point A.") == {"ATC"}
    assert agent.manual_pairing_tokens("Air traffic control clears the route.") == {
        "ATC"
    }


def test_manual_numeric_mismatch_fails_safe() -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [
            _manual_record(
                "13号跑道入口内移150m。",
                "The Runway 13 threshold is displaced by 250 meters.",
            )
        ],
        category="core",
    )[0]

    errors = agent.validate_bilingual_facts([fact])

    assert len(errors) == 1
    assert "中英文关键事实不一致" in errors[0]
    assert "150M" in errors[0]
    assert "250M" in errors[0]


def test_manual_counterpart_never_degrades_to_concept_fallback() -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [
            _manual_record(
                "本场存在风切变风险。",
                "Windshear risk exists at this airport.",
            )
        ],
        category="core",
    )[0]

    assert fact.english_source == "source_backed"
    assert fact.en == "Windshear risk exists at this airport."
    assert fact.en != agent.CONCEPT_ENGLISH["wind"][1]


def test_manual_coverage_gap_fails_instead_of_using_generic_fallback() -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [_manual_record("本场存在风切变风险。", "")],
        category="core",
    )[0]

    assert fact.en == ""
    assert fact.english_source == "manual_coverage_gap"
    assert "最新版机场手册英文配对缺失" in agent.validate_bilingual_facts([fact])[0]


def test_english_chapters_are_bound_by_icao_without_cross_airport_pairing() -> None:
    text = """
页码：10
Alpha Airport (AAA/ZAAA)
I. Typical Safety Incidents
1. Alpha event.
页码：20
Bravo Airport (BBB/ZBBB)
I. Typical Safety Incidents
1. Bravo event.
"""
    index = agent.build_english_manual_index(text)

    alpha = agent.match_english_manual_chapter(index, "ZAAA")
    bravo = agent.match_english_manual_chapter(index, "ZBBB")

    assert alpha and alpha["name"] == "Alpha"
    assert alpha["start_page"] == 10
    assert alpha["end_page"] == 19
    assert bravo and bravo["name"] == "Bravo"
    assert agent.match_english_manual_chapter(index, "ZCCC") is None


def test_latest_manual_real_chapters_use_exact_icao_and_english_pages() -> None:
    index = agent.build_english_manual_index(
        _manual_pages(983, 1163, 1354, 1359, 1563, 1567)
    )

    assert agent.match_english_manual_chapter(index, "VTBS")["start_page"] == 1163
    assert agent.match_english_manual_chapter(index, "ZSPD")["start_page"] == 1354
    assert agent.match_english_manual_chapter(index, "ZGGG")["start_page"] == 1563
    assert agent.match_english_manual_chapter(index, "ZGKL")["start_page"] == 1567
    assert not any(chapter["start_page"] == 983 for chapter in index)


def test_latest_manual_flattened_history_keeps_two_english_events() -> None:
    facts = agent.extract_english_manual_facts(_manual_pages(1354, 1358))
    incidents = [fact for fact in facts if fact.category == "typical"]

    assert len(incidents) == 2
    assert "radome damage" in incidents[0].text
    assert "Flight-plan data-entry errors" in incidents[1].text
    assert "Flight-plan" not in incidents[0].text


def test_latest_manual_operational_frequency_is_not_discarded_as_metadata() -> None:
    facts = agent.extract_english_manual_facts(_manual_pages(1163, 1164))

    assert any(
        fact.phase == "ground"
        and "129.050" in fact.text
        and "contact them" in fact.text
        for fact in facts
    )


def test_release_clearance_matches_atc_actor_without_ignoring_other_atc() -> None:
    assert agent.manual_pairing_tokens("脱波频率按照 PDC 或放行许可。") == {
        "ATC", "PDC"
    }
    assert agent.manual_pairing_tokens("仅按 PDC 执行。") == {"PDC"}
    assert agent.manual_pairing_tokens("PDC or ATC departure clearance.") == {
        "ATC", "PDC"
    }


def test_missing_english_item_does_not_shift_later_source_order() -> None:
    english = agent.extract_english_manual_facts(
        """
        II. Core Threats
        1. Thunderstorms are frequent.
        """
    )
    paired = agent.pair_manual_english_items(
        ["机位818R不建议单发滑行。", "雷雨天气频繁。"], english, "core"
    )

    assert paired == ["", "Thunderstorms are frequent."]


def test_tokenless_counterparts_are_paired_by_same_phase_source_order() -> None:
    facts = agent.extract_english_manual_facts(
        "II. Core Threats\n1. The apron is slippery.\n2. Taxi routes are complex."
    )
    assert agent.pair_manual_english_items(
        ["机坪湿滑。", "滑行路线复杂。"], facts, "core"
    ) == ["The apron is slippery.", "Taxi routes are complex."]


def test_shared_token_does_not_borrow_ambiguous_later_source_record() -> None:
    facts = [agent.ManualEnglishFact("Follow ATC instructions.", "core", "core", 1)]
    assert agent.pair_manual_english_items(
        ["遵守ATC指令。", "证实ATC指令。"], facts, "core"
    ) == ["", ""]


def test_missing_middle_record_does_not_shift_following_anchor() -> None:
    facts = agent.extract_english_manual_facts(
        "II. Core Threats\n1. RNP approach.\n3. VOR approach."
    )
    assert agent.pair_manual_english_items(
        ["RNP进近。", "ILS进近。", "VOR进近。"], facts, "core"
    ) == ["RNP approach.", "", "VOR approach."]


def test_page_break_continuation_does_not_create_new_record() -> None:
    facts = agent.extract_english_manual_facts(
        "II. Core Threats\n1. Keep clear of the\n页码：20\n"
        "版本：20260924 修订日期：2026.09.24 页码：20\nrunway.\n2. Read back instructions."
    )
    assert [fact.text for fact in facts] == [
        "Keep clear of the runway.", "Read back instructions."
    ]


def test_record_pairing_retains_tokenless_following_sentence() -> None:
    facts = agent.extract_english_manual_facts(
        "II. Core Threats\n1. Stand 168 has an uphill gradient. Control taxi speed."
    )
    paired = agent.pair_manual_english_items(
        ["168号机位有上坡。控制滑行速度。"], facts, "core"
    )
    assert paired == ["Stand 168 has an uphill gradient. Control taxi speed."]
    clauses = agent.split_source_record_clauses("168号机位有上坡。控制滑行速度。")
    assert agent.pair_manual_english_clauses(clauses, paired[0]) == [
        "Stand 168 has an uphill gradient.", "Control taxi speed."
    ]


def test_missing_first_clause_does_not_steal_second_clause_translation() -> None:
    clauses = agent.split_source_record_clauses(
        "STAR程序需证实跑道。N1达到50%仍无法滑出时申请拖车。"
    )
    values = agent.pair_manual_english_clauses(
        clauses, "If N1 reaches 50% and the aircraft cannot move, request towing."
    )
    assert values[0] == ""
    assert "N1" in values[1]


def test_equivalent_phase_headings_keep_all_items() -> None:
    facts = agent.extract_english_manual_facts(
        "II. Core Threats\nIII. Operational Characteristics\n"
        "(4) Entry:\n1. RNP approach.\n"
        "5. Post-landing Ground Operations Phase\n1. Stop on the apron."
    )
    assert agent.pair_manual_english_items(
        ["进场：RNP进近。", "着陆后地面：机坪停车。"], facts, "core"
    ) == ["RNP approach.", "Stop on the apron."]


def test_layout_annunciation_spacing_does_not_erase_tokens_or_fixes() -> None:
    assert agent.manual_pairing_tokens("NAVADS-BRPTG 1+2 FAULT，NAVBKUPSPDFAULT，GPS PRIMARYLOST") == agent.manual_pairing_tokens(
        "NAV ADS-B RPTG 1+2 FAULT, NAV BKUP SPD FAULT, GPS PRIMARY LOST"
    )
    assert "OLPAB" in agent.manual_pairing_tokens("ATKAV-OLPAB-NOMAR")
    assert "NAVGPS" in agent.manual_pairing_tokens("Direct NAVGPS.")
    assert agent.manual_pairing_tokens("OLPAB") != agent.manual_pairing_tokens("OBLAP")


def test_runway_pairs_and_labels_preserve_both_ends_in_both_languages() -> None:
    assert agent.manual_pairing_tokens("原17R/35L跑道更名为16R/34L跑道。") == agent.manual_pairing_tokens(
        "The original runway 17R / 35L will be renamed 16R / 34L."
    )
    assert agent.manual_pairing_tokens("东跑道16L。") == agent.manual_pairing_tokens("RWY 16L.")
    assert agent.manual_pairing_tokens("02L落地后。") == agent.manual_pairing_tokens("After landing on 02L.")
    assert agent.manual_pairing_tokens("20R RNP进近。") == agent.manual_pairing_tokens("20R RNP approach.")


def test_explicit_bilingual_acronym_expansions_do_not_ignore_actor_mismatch() -> None:
    assert agent.manual_pairing_tokens("放行许可，飞行操作通告，目视泊位引导系统，2300UTC。") == agent.manual_pairing_tokens(
        "Received clearance, FOIB, VDGS, 2300 UTC."
    )
    assert "ATC" not in agent.manual_pairing_tokens("Terrain clearance.")
    assert agent.manual_pairing_tokens("仅PDC。") != agent.manual_pairing_tokens("PDC or ATC clearance.")


def test_ground_marshaller_is_not_automatically_an_atc_actor() -> None:
    assert "ATC" not in agent.manual_pairing_tokens("地面指挥员下车引导。")
    assert "ATC" in agent.manual_pairing_tokens("管制指挥转向。")
    assert "J3" in agent.manual_pairing_tokens("J3上的停机位。")
    assert agent.bilingual_semantic_mismatches("发生风切变。", "Wind shear occurred.") == []
    assert "windshear" in agent.bilingual_semantic_mismatches("发生风切变。", "Turbulence occurred.")


def test_chinese_source_pages_follow_current_manual_not_legacy_locations() -> None:
    text = "页码：40\n甲地机场运行特点（AAA/ZAAA）\n正文\n页码：42\n续页\n页码：43\n乙地机场运行特点（BBB/ZBBB）\n正文"
    sections = agent.build_manual_index(text)
    assert sections[0]["start_page"] == 40
    assert sections[0]["end_page"] == 42
    assert sections[1]["start_page"] == 43


def test_arrival_heading_alias_and_decimal_list_without_terminal_dot() -> None:
    facts = agent.extract_english_manual_facts(
        "Arrival / Approach / Landing\n4.1 RNP approach.\n4.2 ILS approach."
    )
    assert [(f.phase, f.sequence, f.text) for f in facts] == [
        ("arrival", 0, "RNP approach."), ("arrival", 1, "ILS approach.")
    ]


def test_multiple_chinese_clauses_share_one_numbered_english_source_item() -> None:
    facts = agent.extract_english_manual_facts(
        "II. Core Threats\n1. RNP approach; ILS approach."
    )
    assert len(facts) == 1
    clauses = agent.split_source_record_clauses("RNP进近。ILS进近。")
    assert agent.pair_manual_english_clauses(clauses, facts[0].text) == [
        "RNP approach;", "ILS approach."
    ]


def test_other_section_does_not_contaminate_last_operational_item() -> None:
    facts = agent.extract_english_manual_facts(
        "6. Operating Characteristics in Specific Environments\n"
        "6.1 Low visibility.\n6.2 Bird-scare cannon blasts.\n"
        "7. Others\n7.1 Dispatch frequencies.\n7.2 Immigration information.\n"
        "7.3 Historical Safety Occurrences (1) A bird strike occurred."
    )
    assert [(f.category, f.text) for f in facts] == [
        ("core", "Low visibility."), ("core", "Bird-scare cannon blasts."),
        ("typical", "A bird strike occurred.")
    ]


def test_route_specific_chinese_exclusion_also_excludes_english_counterpart() -> None:
    fact = agent.BilingualFact(
        "route-specific",
        "甲地至乙地航路存在限制。",
        "The route from Alpha to Bravo has a restriction.",
        airport="测试机场",
        route_scope=(("甲地", "乙地"),),
        english_source="source_backed",
        manual_english_counterpart=True,
    )
    duty = CalendarEvent(
        uid="route",
        summary="✈️ 9C0001 丙地→丁地",
        start=datetime(2026, 10, 5, 8, 0),
        end=datetime(2026, 10, 5, 10, 0),
        description="类型：航班\n航班：9C0001\n航线：丙地 → 丁地",
        location="丙地",
        properties={},
    )

    assert agent.filter_fact_for_duty(fact, duty, date(2026, 10, 5)) is None


def test_typical_event_retains_same_source_backed_identity() -> None:
    fact = agent.source_record_facts(
        "测试机场",
        [
            _manual_record(
                "曾发生偏离指令高度事件。",
                "A deviation from the instructed altitude occurred.",
                category="typical",
                phase="incident",
            )
        ],
        category="typical",
    )[0]

    assert fact.category == "typical"
    assert fact.source_fact_ids == (fact.fact_id,)
    assert fact.english_source == "source_backed"


def test_formal_english_airport_name_comes_from_manual_title() -> None:
    fact = agent.BilingualFact(
        "airport-name",
        "测试事实。",
        "Test fact.",
        airport="测试机场",
        airport_name_en="Test International",
    )

    assert agent.english_airport_name_for_facts("测试机场", [fact]) == (
        "Test International"
    )


def test_user_confirmed_counterpart_requires_exact_chinese_and_role_match() -> None:
    records = [
        {
            "fact_id": "confirmed:one",
            "text_zh": "直飞A点，注意能量管理。",
            "text_en": "When cleared direct to Point A, monitor energy management.",
            "role_scope": ("arrival",),
        }
    ]

    matched = agent.user_confirmed_english_counterpart(
        "直飞A点，注意能量管理。", ("arrival",), records
    )

    assert matched is records[0]
    assert (
        agent.user_confirmed_english_counterpart(
            "直飞B点，注意能量管理。", ("arrival",), records
        )
        is None
    )
    assert (
        agent.user_confirmed_english_counterpart(
            "直飞A点，注意能量管理。", ("departure",), records
        )
        is None
    )
