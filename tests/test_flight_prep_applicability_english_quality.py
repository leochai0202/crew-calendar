from __future__ import annotations

from datetime import date, datetime

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


def _event(uid: str, departure: str, arrival: str) -> CalendarEvent:
    return CalendarEvent(
        uid=uid,
        summary=f"✈️ 9C0001 {departure}→{arrival}",
        start=datetime(2026, 1, 1, 8, 0),
        end=datetime(2026, 1, 1, 10, 0),
        description=(
            f"类型：航班\n航班：9C0001\n航线：{departure} → {arrival}"
        ),
        location=departure,
        properties={},
    )


def _route_fact(*routes: tuple[str, str]) -> agent.BilingualFact:
    return agent.BilingualFact(
        "route-fact",
        "该航线存在明确运行限制。",
        "This route has a specific operating restriction.",
        airport="甲机场",
        route_scope=routes,
        english_source="source_backed",
    )


def test_generic_explicit_route_scope_parses_chinese_forms_and_direction() -> None:
    record = {"category": "core", "operational_phase": "navigation"}

    for text in (
        "航线：甲机场-乙机场，存在限制。",
        "甲机场—乙机场航路存在限制。",
        "甲机场至乙机场航班存在限制。",
        "甲机场到乙机场航线存在限制。",
        "甲机场→乙机场：存在限制。",
        "甲机场往乙机场航路存在限制。",
    ):
        assert agent.record_route_scope(record, text) == (("甲机场", "乙机场"),)

    assert agent.filter_fact_for_duty(
        _route_fact(("甲机场", "乙机场")),
        _event("forward", "甲机场", "乙机场"),
        date(2026, 1, 1),
    ) is not None
    assert agent.filter_fact_for_duty(
        _route_fact(("甲机场", "乙机场")),
        _event("reverse", "乙机场", "甲机场"),
        date(2026, 1, 1),
    ) is None


def test_icao_route_scope_and_any_real_duty_segment_match() -> None:
    scope = agent.record_route_scope(
        {"category": "core", "operational_phase": "navigation"},
        "AAAA-BBBB航路存在限制。",
    )
    duty = agent.DutyContext(
        (
            _event("first", "CCCC", "DDDD"),
            _event("second", "AAAA", "BBBB"),
        )
    )

    assert scope == (("AAAA", "BBBB"),)
    assert agent.filter_fact_for_duty(
        _route_fact(*scope), duty, date(2026, 1, 1)
    ) is not None


def test_typical_history_route_is_evidence_not_applicability_scope() -> None:
    text = "历史上某航班甲机场-乙机场运行时曾触发警告。"

    assert agent.record_route_scope({"category": "typical"}, text) == ()


def test_detached_numeric_fragments_are_rejected_without_text_blacklists() -> None:
    for fragment in ("速度160节。", "高度3000米。", "不超过20节。"):
        assert agent.manual_source_quality_issue(fragment) == (
            "detached_operational_fragment"
        )


def test_numbered_continuation_inherits_parent_identity_and_scope() -> None:
    clauses = agent.split_source_record_clauses(
        "进场：顺风条件下提前建立着陆形态。（2）速度160节。",
        parent_record_id="parent-1",
        source_sequence=7,
    )

    assert len(clauses) == 1
    assert "速度160节" in clauses[0].text
    assert clauses[0].parent_record_id == "parent-1"
    assert clauses[0].source_sequence == 7000
    assert clauses[0].role_scope == ("arrival",)


def test_source_records_for_different_airports_never_cross() -> None:
    records = [
        {
            "airport": "甲机场",
            "fact_id": "alpha",
            "category": "core",
            "text_zh": "甲机场存在地形风险。",
            "text_en": "Terrain risk exists at Alpha Airport.",
        },
        {
            "airport": "乙机场",
            "fact_id": "bravo",
            "category": "core",
            "text_zh": "乙机场存在风切变风险。",
            "text_en": "Windshear risk exists at Bravo Airport.",
        },
    ]

    assert [
        fact.fact_id
        for fact in agent.source_record_facts("甲机场", records, category="core")
    ] == ["alpha"]


def test_generic_aviation_terminology_uses_chinese_semantic_context() -> None:
    cases = (
        ("13号盲降。", "The 13th blind landing.", "Runway 13 ILS approach"),
        ("五边乱流。", "Five-sided Chaos.", "turbulence on final approach"),
        (
            "1000ft未建立着陆形态。",
            "A failed landing attempt occurred at 1000ft.",
            "Landing configuration was not established at 1000ft",
        ),
        ("曾发生滑错路线事件。", "History of route deviation incidents.", "wrong-taxi-route"),
        ("13号跑道入口内移150m。", "Move the entrance of Runway 13 inward by 150 meters.", "threshold of Runway 13 is displaced by 150 meters"),
    )

    for chinese, source_english, expected in cases:
        assert expected.lower() in agent.normalize_aviation_terminology(
            chinese, source_english
        ).lower()


def test_semantic_mismatch_is_failed_safe_even_when_english_is_source_backed() -> None:
    fact = agent.BilingualFact(
        "bad-source-english",
        "13号盲降进近。",
        "Use the emergency procedure for Runway 13.",
        airport="测试机场",
        english_source="source_backed",
    )

    errors = agent.validate_bilingual_facts(
        [agent.professionalize_source_english(fact)]
    )

    assert any("中英文关键概念不一致" in error and "ILS" in error for error in errors)


def test_approved_override_resolves_exact_source_identity_only() -> None:
    source_text = "本场存在明确运行限制。"
    entry = {
        "manual_version": "20260101",
        "icao": "ZAAA",
        "source_record_id": "record-1",
        "source_text_hash": agent.source_text_hash(source_text),
        "text_en": "A specific operating restriction applies at this airport.",
        "approved_by": "USER_CONFIRMED",
        "confirmed_date": "2026-01-02",
        "source_note": "Reviewed bilingual counterpart.",
    }

    matched = agent.approved_english_override(
        manual_version="20260101",
        icao="ZAAA",
        source_record_id="record-1",
        source_text=source_text,
        overrides=[entry],
    )

    assert matched is entry
    assert agent.approved_english_override(
        manual_version="20260101",
        icao="ZAAA",
        source_record_id="record-2",
        source_text=source_text,
        overrides=[entry],
    ) is None


def test_selected_chinese_and_english_fact_id_invariant_fails_safe() -> None:
    complete = agent.BilingualFact(
        "complete", "本场西侧存在复杂地形。", "Complex terrain lies west of the airport."
    )
    missing = agent.BilingualFact(
        "missing", "进近时存在风切变风险。", "", english_source="manual_coverage_gap"
    )

    assert agent.validate_selected_fact_id_parity([complete]) == []
    assert "中英文选定事实身份不一致" in agent.validate_selected_fact_id_parity(
        [complete, missing]
    )[0]
