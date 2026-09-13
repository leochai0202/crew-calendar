from __future__ import annotations

from dataclasses import replace

from crew_agents import flight_prep_agent as agent


def _record(
    text: str,
    *,
    source: str = "PDF",
    semantic_key: str = "",
    category: str = "core",
    phase: str = "unspecified",
) -> dict[str, object]:
    return {
        "airport": "测试机场",
        "category": category,
        "source": source,
        "source_authority": agent.SOURCE_AUTHORITY[source],
        "source_version": "20260907" if source == "PDF" else "",
        "source_file": "knowledge/pdf/current.pdf",
        "source_page": "1",
        "source_heading": "测试机场运行特点",
        "source_section": "典型不安全事件" if category == "typical" else "运行特点",
        "operational_phase": phase,
        "role_scope": (),
        "airport_specific": True,
        "importance": 60,
        "semantic_key": semantic_key,
        "text_zh": text,
        "source_original_text": text,
        "source_record_id": "record:" + (semantic_key or text),
    }


def _fact(
    fact_id: str,
    text: str,
    *,
    phase: str = "unspecified",
    topic: str = "",
    importance: int = 60,
    source_record_id: str | None = None,
    role_scope: tuple[str, ...] = (),
) -> agent.BilingualFact:
    return agent.BilingualFact(
        fact_id=fact_id,
        text_zh=text,
        text_en="",
        airport="测试机场",
        source_file="knowledge/pdf/current.pdf",
        source="PDF",
        source_authority="latest_airport_manual",
        source_version="20260907",
        source_page="1",
        source_heading="测试机场运行特点",
        source_section="运行特点",
        operational_phase=phase,
        role_scope=role_scope,
        airport_specific=True,
        category="core",
        importance=importance,
        topic=topic,
        source_text_zh=text,
        source_fact_ids=(fact_id,),
        source_record_ids=(source_record_id or fact_id,),
        source_clauses=(text,),
        source_original_texts=(text,),
    )


def test_latest_manual_wins_same_semantic_identity_over_curated() -> None:
    records = [
        _record("最新版跑道运行事实。", semantic_key="same"),
        _record("旧人工跑道运行事实。", source="CURATED", semantic_key="same"),
    ]
    facts = agent.source_record_facts("测试机场", records, category="core")
    assert [fact.text_zh for fact in facts] == ["最新版跑道运行事实。"]
    assert facts[0].source_authority == "latest_airport_manual"


def test_latest_manual_wins_same_semantic_identity_over_supplement() -> None:
    records = [
        _record("最新版程序事实。", semantic_key="same"),
        _record("无版本补充程序事实。", source="supplement", semantic_key="same"),
    ]
    facts = agent.source_record_facts("测试机场", records, category="core")
    assert len(facts) == 1
    assert facts[0].source == "PDF"


def test_generic_empty_headings_are_structure_only() -> None:
    for value in ("运行限制：。", "导航设施：。", "ABC特点：。"):
        assert agent.is_manual_structure_only(value)
        assert not agent.clean_output_fact(value)


def test_meaningful_generic_heading_keeps_value_without_label() -> None:
    value = agent.naturalize_source_fact("导航设施：ABC台长期不工作。")
    assert value == "ABC台长期不工作。"


def test_operational_subject_and_condition_labels_are_not_stripped() -> None:
    cases = {
        "ATC要求：保持5000ft。": ("ATC要求", "5000ft"),
        "RNP进近程序：ATC指挥可能与程序设计逻辑存在差异。": (
            "RNP进近程序",
            "ATC指挥可能与程序设计逻辑存在差异",
        ),
        "36R跑道限制：必须使用全跑道起飞。": ("36R跑道限制", "必须"),
        "SASAN程序：保持5000ft。": ("SASAN程序", "5000ft"),
        "夜间运行要求：使用指定滑行路线。": ("夜间运行要求", "指定滑行路线"),
    }
    for source, anchors in cases.items():
        naturalized = agent.naturalize_source_fact(source)
        cleaned = agent.clean_output_fact(source)
        assert all(anchor in naturalized for anchor in anchors)
        assert all(anchor in cleaned for anchor in anchors)
        guarded = replace(_fact("label", source), text_zh=naturalized)
        assert not agent.validate_source_semantic_preservation(guarded)
        assert not agent.validate_source_semantic_preservation(
            replace(guarded, text_zh=cleaned)
        )


def test_pdf_cross_line_record_is_reconstructed_before_quality_gate() -> None:
    joined = agent._join_pdf_record_lines(
        ["机组如需运行信息", "或需要飞行计划方面的协助，可通过该频率联系。"]
    )
    assert joined == "机组如需运行信息或需要飞行计划方面的协助，可通过该频率联系。"
    assert not agent.manual_source_quality_issue(joined)


def test_pdf_cross_page_footer_does_not_break_open_record() -> None:
    joined = agent._join_pdf_record_lines(
        [
            "机组如需运行信息",
            "非受控文件",
            "版本：20260907 页码：12",
            "或需要飞行计划方面的协助，可通过该频率联系。",
        ]
    )
    assert joined == "机组如需运行信息或需要飞行计划方面的协助，可通过该频率联系。"


def test_unrecoverable_continuation_fragment_is_discarded() -> None:
    assert agent.manual_source_quality_issue("或者需要飞行计划方。")


def test_natural_language_plus_is_cleaned_without_touching_technical_plus() -> None:
    assert "影响，易发生" in agent.naturalize_source_fact("受温度影响+易发生进近偏低。")
    assert "1+2" in agent.naturalize_source_fact("NAV ADS-B RPTG 1+2 FAULT。")


def test_dedicated_typical_section_is_primary_classification() -> None:
    assert not agent.typical_source_quality_issue(
        "易发生进近剖面低、着陆距离远等事件。",
        "测试机场／典型不安全事件",
    )


def test_core_record_is_not_promoted_to_typical_by_event_words() -> None:
    records = [_record("进近风险可能导致复飞。", category="core")]
    assert not agent.bilingual_typical_facts(
        "测试机场", [], [], 9, 5, source_records=records
    )


def test_mixed_role_record_splits_complete_clauses() -> None:
    clauses = agent.split_source_record_clauses(
        "离场时可能收到雷达引导。进近时可能临时改变跑道。"
    )
    assert [clause.role_scope for clause in clauses] == [
        ("departure",),
        ("arrival",),
    ]


def test_arrival_and_departure_port_wording_is_both_role_source() -> None:
    assert agent.explicit_role_scope("进港和离港飞机均可能收到管制指令。", "unspecified") == (
        "departure",
        "arrival",
    )


def test_role_neutral_tcas_fact_is_eligible_for_both_roles() -> None:
    fact = _fact("tcas", "空域内可能出现TA/RA告警。", topic="traffic_tcas")
    assert agent.fact_matches_airport_role(fact, "departure")
    assert agent.fact_matches_airport_role(fact, "arrival")


def test_arrival_final_order_follows_operational_sequence_not_score() -> None:
    facts = [
        replace(_fact("ground", "落地后滑行至机位。", phase="landing_ground"), topic="landing_ground", briefing_priority=999),
        replace(_fact("airspace", "终端空域可能加入等待。"), topic="airspace_atc", briefing_priority=300),
        replace(_fact("approach", "进近程序可能改变。", phase="approach"), topic="approach", briefing_priority=500),
        replace(_fact("landing", "着陆跑道存在坡度。", phase="landing"), topic="landing", briefing_priority=500),
    ]
    ordered = sorted(facts, key=lambda fact: agent.operational_sequence_key("arrival", fact))
    assert [fact.fact_id for fact in ordered] == ["airspace", "approach", "landing", "ground"]


def test_same_record_same_topic_can_merge_with_full_provenance() -> None:
    facts = [
        _fact("a", "19号跑道盲降易出现双截获。", phase="approach", source_record_id="record-1"),
        _fact("b", "19号跑道盲降进近注意能量管理。", phase="approach", source_record_id="record-1"),
    ]
    paragraphs = agent.organize_source_grounded_briefing_paragraphs(
        facts, "arrival", max_paragraphs=4
    )
    assert len(paragraphs) == 1
    assert set(paragraphs[0].source_fact_ids) == {"a", "b"}


def test_unrelated_topics_do_not_merge() -> None:
    facts = [
        _fact("weather", "夏季雷暴较多。", phase="weather"),
        _fact("ground", "落地后滑行道较窄。", phase="landing_ground"),
    ]
    paragraphs = agent.organize_source_grounded_briefing_paragraphs(
        facts, "arrival", max_paragraphs=4
    )
    assert len(paragraphs) == 2


def test_low_value_contact_cannot_displace_runway_fact() -> None:
    facts = [
        _fact("contact", "如需飞行计划方面协助可通过129.050频率联系。", phase="ground", importance=80),
        _fact("runway", "20R跑道仅用于起飞。", phase="departure", importance=60),
    ]
    selected = agent.organize_source_grounded_briefing_paragraphs(
        facts, "departure", max_paragraphs=1
    )
    assert selected[0].fact_id == "runway"


def test_required_topic_is_generic_and_source_backed() -> None:
    facts = [
        replace(
            _fact(
                "ordinary",
                "20R跑道必须使用全跑道起飞。",
                phase="departure",
                topic="takeoff",
                importance=100,
            ),
            restriction=True,
        ),
        _fact("tcas", "空域内可能出现TA/RA告警。", topic="traffic_tcas", importance=50),
    ]
    selected = agent.select_airport_facts(
        "测试机场",
        "departure",
        facts,
        max_items=1,
        required_topics=("traffic_tcas",),
    )
    assert [fact.fact_id for fact in selected] == ["tcas"]
    paragraphs = agent.organize_source_grounded_briefing_paragraphs(
        facts,
        "departure",
        max_paragraphs=1,
        required_topics=("traffic_tcas",),
    )
    assert len(paragraphs) == 1
    assert paragraphs[0].source_fact_ids == ("tcas",)


def test_arrival_only_required_fact_cannot_enter_departure_briefing() -> None:
    diagnostics: list[dict[str, object]] = []
    selected = agent.select_airport_facts(
        "测试机场",
        "departure",
        [
            _fact(
                "arrival-tcas",
                "进近阶段可能出现TA/RA告警。",
                phase="approach",
                topic="traffic_tcas",
                role_scope=("arrival",),
            )
        ],
        max_items=1,
        required_topics=("traffic_tcas",),
        exclusion_log=diagnostics,
    )
    assert not selected
    assert any(
        item.get("discarded_reason") == "required_topic_role_mismatch"
        for item in diagnostics
    )


def test_departure_only_required_fact_cannot_enter_arrival_briefing() -> None:
    diagnostics: list[dict[str, object]] = []
    selected = agent.select_airport_facts(
        "测试机场",
        "arrival",
        [
            _fact(
                "departure-tcas",
                "离场阶段可能出现TA/RA告警。",
                phase="departure",
                topic="traffic_tcas",
                role_scope=("departure",),
            )
        ],
        max_items=1,
        required_topics=("traffic_tcas",),
        exclusion_log=diagnostics,
    )
    assert not selected
    assert any(
        item.get("discarded_reason") == "required_topic_role_mismatch"
        for item in diagnostics
    )


def test_role_neutral_required_tcas_is_selectable_for_both_roles() -> None:
    neutral = _fact(
        "neutral-tcas",
        "空域内可能出现TA/RA告警。",
        topic="traffic_tcas",
    )
    for role in ("departure", "arrival"):
        selected = agent.select_airport_facts(
            "测试机场",
            role,
            [neutral],
            max_items=1,
            required_topics=("traffic_tcas",),
        )
        assert [fact.fact_id for fact in selected] == ["neutral-tcas"]


def test_missing_required_topic_creates_diagnostic_not_fact() -> None:
    diagnostics: list[dict[str, object]] = []
    selected = agent.select_airport_facts(
        "测试机场",
        "departure",
        [_fact("runway", "20R跑道仅用于起飞。", phase="departure")],
        max_items=2,
        required_topics=("traffic_tcas",),
        exclusion_log=diagnostics,
    )
    assert all(fact.topic != "traffic_tcas" for fact in selected)
    assert diagnostics[0]["discarded_reason"] == "required_topic_source_missing"


def test_source_guard_still_rejects_new_control_measure() -> None:
    source = "春夏季雷暴较多，存在低空风切变风险。"
    fact = _fact("weather", source, phase="weather")
    unsafe = replace(fact, text_zh=source.rstrip("。") + "，应制定绕飞预案。")
    errors = agent.validate_source_semantic_preservation(unsafe)
    assert errors


def test_malformed_repeated_speed_fragment_fails_quality_gate() -> None:
    assert agent.manual_source_quality_issue(
        "10000或10000ft下....250kts除非得到ATC指令。"
    ) == "来源包含无法可靠恢复的数字或标点错位"


def test_information_map_text_is_not_a_typical_incident() -> None:
    assert agent.typical_source_quality_issue(
        "国际航班备降场信息图，本图不是航图，仅供飞行员参考。",
        "测试机场／典型不安全事件",
    ) == agent.TYPICAL_NOT_EVENT_REASON


def test_pushback_precedes_taxi_waiting_in_operational_order() -> None:
    pushback = replace(
        _fact("push", "机坪可能给出推出开车指令。", phase="ground"),
        topic="ground_pushback",
        briefing_priority=250,
    )
    waiting = replace(
        _fact("wait", "滑行等待位置较近。", phase="ground"),
        topic="ground_waiting",
        briefing_priority=999,
    )
    ordered = sorted(
        [waiting, pushback],
        key=lambda fact: agent.operational_sequence_key("departure", fact),
    )
    assert [fact.fact_id for fact in ordered] == ["push", "wait"]
