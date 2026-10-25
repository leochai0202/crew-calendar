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
