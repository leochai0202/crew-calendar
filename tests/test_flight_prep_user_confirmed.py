from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


AIRPORT = "合成测试机场"
TCAS = (
    "接近目标高度最后2000ft且有邻近航空器时，合理控制升降率并持续监控冲突趋势；"
    "发生RA时严格执行现行程序。"
)


def _config(repo: Path, **overrides: object) -> dict[str, object]:
    entry = {
        "airport": AIRPORT,
        "topic": "traffic_tcas",
        "text_zh": TCAS,
        "role_scope": ["departure", "arrival"],
        "source": "USER_CONFIRMED",
        "source_note": "用户明确确认的测试运行控制要求",
        "confirmed_date": "2026-09-13",
        **overrides,
    }
    path = repo / agent.USER_CONFIRMED_AIRPORT_FACTS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "facts": [entry]}, ensure_ascii=False),
        encoding="utf-8",
    )
    return entry


def _confirmed(repo: Path) -> agent.BilingualFact:
    return agent.source_record_facts(
        AIRPORT, agent.load_user_confirmed_airport_records(repo)[AIRPORT],
        category="core",
    )[0]


def _duty(role: str) -> CalendarEvent:
    route = (AIRPORT, "另一测试机场") if role == "departure" else ("另一测试机场", AIRPORT)
    return CalendarEvent(
        uid="user-confirmed-test", summary="9C1234", properties={},
        start=datetime(2026, 9, 13, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
        end=datetime(2026, 9, 13, 12, tzinfo=ZoneInfo("Asia/Shanghai")),
        description=f"类型：航班\n航班：9C1234\n航线：{route[0]} → {route[1]}",
        location=route[0], source_file="test.ics",
    )


@pytest.mark.parametrize("role", ["departure", "arrival"])
def test_arbitrary_airport_user_confirmed_uses_complete_fact_pipeline(
    tmp_path: Path, role: str,
) -> None:
    _config(tmp_path)
    fact = _confirmed(tmp_path)
    paragraphs = agent.prepare_operational_facts(
        _duty(role), AIRPORT, date(2026, 9, 13), [fact], max_items=1,
        required_topics=("traffic_tcas",), exclusion_log=[],
    )
    assert len(paragraphs) == 1
    paragraph = paragraphs[0]
    assert all(marker in paragraph.zh for marker in ("2000ft", "RA", "冲突趋势"))
    assert not agent.validate_source_semantic_preservation(paragraph)
    assert not agent.validate_airport_fact_bindings(AIRPORT, paragraphs)
    meta = agent.fact_source_metadata(paragraph)
    assert meta["source"] == "USER_CONFIRMED"
    assert meta["source_authority"] == "user_confirmed"
    assert meta["topic"] == "traffic_tcas"
    assert meta["role_scope"] == ["departure", "arrival"]
    assert meta["confirmed_date"] == "2026-09-13"
    assert meta["source_note"]
    assert meta["source_fact_ids"] == [fact.fact_id]
    assert meta["source_original_texts"] == [TCAS]


def test_arrival_only_manual_does_not_displace_departure_user_confirmation(
    tmp_path: Path,
) -> None:
    _config(tmp_path)
    user = _confirmed(tmp_path)
    source = "进近阶段曾多次触发TA/RA。"
    manual = replace(
        user, fact_id="manual-arrival", semantic_key="manual-arrival",
        source="PDF", source_authority="latest_airport_manual",
        operational_phase="approach", role_scope=("arrival",),
        text_zh=source, source_text_zh=source, source_clauses=(source,),
        source_original_texts=(source,), source_fact_ids=("manual-arrival",),
        source_record_ids=("manual-arrival",), importance=100,
    )
    diagnostics: list[dict[str, object]] = []
    paragraphs = agent.prepare_operational_facts(
        _duty("departure"), AIRPORT, date(2026, 9, 13), [manual, user],
        max_items=1, required_topics=("traffic_tcas",), exclusion_log=diagnostics,
    )
    assert len(paragraphs) == 1
    assert paragraphs[0].source_fact_ids == (user.fact_id,)
    assert "进近阶段" not in paragraphs[0].zh
    assert any(
        item.get("discarded_reason") == "required_topic_role_mismatch"
        for item in diagnostics
    )


def test_required_topic_protects_user_confirmation_from_high_score_budget(
    tmp_path: Path,
) -> None:
    _config(tmp_path)
    user = _confirmed(tmp_path)
    ordinary = replace(
        user, fact_id="takeoff", semantic_key="takeoff", topic="takeoff",
        text_zh="20R跑道必须使用全跑道起飞。", importance=100,
        operational_phase="departure", role_scope=("departure",),
        source_fact_ids=("takeoff",), source_record_ids=("takeoff",),
    )
    selected = agent.select_airport_facts(
        AIRPORT, "departure", [ordinary, user], max_items=1,
        required_topics=("traffic_tcas",),
    )
    assert selected == [user]
    paragraphs = agent.organize_source_grounded_briefing_paragraphs(
        selected, "departure", max_paragraphs=1, required_topics=("traffic_tcas",),
    )
    assert paragraphs[0].source_fact_ids == (user.fact_id,)


@pytest.mark.parametrize("extra", ["", "接近目标高度时可能出现TCAS告警。"])
def test_latest_manual_and_same_topic_user_fact_render_only_once(
    tmp_path: Path, extra: str,
) -> None:
    _config(tmp_path)
    user = _confirmed(tmp_path)
    text = TCAS + extra
    manual = replace(
        user, fact_id="manual-tcas", semantic_key="manual-tcas", source="PDF",
        source_authority="latest_airport_manual", source_version="20260907",
        text_zh=text, source_text_zh=text, source_clauses=(text,),
        source_original_texts=(text,),
        source_fact_ids=("manual-tcas",), source_record_ids=("manual-tcas",),
    )
    paragraphs = agent.prepare_operational_facts(
        _duty("departure"), AIRPORT, date(2026, 9, 13), [user, manual],
        max_items=6, required_topics=("traffic_tcas",), exclusion_log=[],
    )
    assert len(paragraphs) == 1
    assert paragraphs[0].source == "PDF"
    assert set(paragraphs[0].source_fact_ids) == {user.fact_id, "manual-tcas"}
    assert paragraphs[0].zh.count("冲突趋势") == 1
    assert not agent.validate_source_semantic_preservation(paragraphs[0])


def test_user_confirmation_remains_subject_to_role_gate(tmp_path: Path) -> None:
    _config(tmp_path, role_scope=["arrival"])
    fact = _confirmed(tmp_path)
    diagnostics: list[dict[str, object]] = []
    assert not agent.prepare_operational_facts(
        _duty("departure"), AIRPORT, date(2026, 9, 13), [fact], max_items=1,
        required_topics=("traffic_tcas",), exclusion_log=diagnostics,
    )
    assert any(
        item.get("discarded_reason") == "required_topic_role_mismatch"
        for item in diagnostics
    )


def test_user_confirmation_does_not_relax_source_guard(tmp_path: Path) -> None:
    _config(tmp_path)
    fact = _confirmed(tmp_path)
    unsafe = replace(fact, text_zh=TCAS + "应提前制定绕飞预案。")
    assert agent.validate_source_semantic_preservation(unsafe)


def test_latest_manual_does_not_disable_user_confirmed_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config(tmp_path)
    monkeypatch.setattr(agent, "manual_airport_data", lambda *args, **kwargs: (
        {AIRPORT: {"core_threats": ["20R跑道仅用于起飞。"], "matched_header": AIRPORT}},
        "knowledge/pdf/current.pdf", 20260907, "PDF", [],
    ))
    _, threats, records, *_ = agent.airport_risks(tmp_path, [AIRPORT], {}, 100)
    assert TCAS in threats[AIRPORT]
    facts = agent.source_record_facts(AIRPORT, records[AIRPORT], category="core")
    assert {fact.source for fact in facts} == {"PDF", "USER_CONFIRMED"}


def test_missing_config_cannot_invent_required_topic(tmp_path: Path) -> None:
    assert agent.load_user_confirmed_airport_records(tmp_path) == {}
    diagnostics: list[dict[str, object]] = []
    assert not agent.select_airport_facts(
        AIRPORT, "departure", [], required_topics=("traffic_tcas",),
        exclusion_log=diagnostics,
    )
    assert diagnostics[0]["discarded_reason"] == "required_topic_source_missing"


@pytest.mark.parametrize("overrides", [
    {"source": "PDF"}, {"source_note": ""}, {"role_scope": []},
    {"role_scope": ["unknown"]}, {"confirmed_date": "not-a-date"},
])
def test_invalid_confirmation_cannot_grant_source_authority(
    tmp_path: Path, overrides: dict[str, object],
) -> None:
    _config(tmp_path, **overrides)
    with pytest.raises(ValueError):
        agent.load_user_confirmed_airport_records(tmp_path)


def test_user_confirmation_still_passes_source_quality_gate(tmp_path: Path) -> None:
    _config(tmp_path, text_zh="运行限制：。")
    records = agent.load_user_confirmed_airport_records(tmp_path)[AIRPORT]
    diagnostics: list[dict[str, object]] = []
    assert not agent.source_record_facts(
        AIRPORT, records, category="core", exclusion_log=diagnostics,
    )
    assert diagnostics


def test_same_confirmation_has_stable_source_id(tmp_path: Path) -> None:
    _config(tmp_path)
    original = _confirmed(tmp_path)
    _config(tmp_path, source_note="补充审计说明，不改变来源内容")
    assert _confirmed(tmp_path).fact_id == original.fact_id
