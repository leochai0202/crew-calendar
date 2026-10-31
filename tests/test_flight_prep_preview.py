"""Review artifacts are complete, visibly unverified and cannot publish."""
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.flight_prep_preview import write_preview, NOTICE
from test_flight_prep_independent_languages import flight


def facts():
    zh = agent.BilingualFact("zh:test", "沿W19经MASGU、ATKAV和OLPAB。", "Follow W19 via MASGU, ATKAV and OBLAP.", airport="AAAA",
        category="core", source="PDF", source_verbatim=True, source_file="manual.pdf", source_version="test",
        source_page="10", english_source_page="20", source_text_zh="沿W19经MASGU、ATKAV和OLPAB。",
        source_record_ids=("zh:test",), english_source_record_id="en:test")
    en = replace(zh, fact_id="en:test", language="en", source_page="20", source_record_ids=("en:test",),
                 source_text_en="Follow W19 via MASGU, ATKAV and OBLAP.", english_source="source_backed")
    return zh, en


def group():
    zh, en = facts()
    evidence = []
    errors = agent.validate_cross_language_conflicts([zh], [en], conflict_evidence=evidence)
    assert errors
    return dict(group_index=1, airport_fact_sources={"AAAA": [agent.fact_source_metadata(zh)]},
        english_fact_sources={"AAAA": [agent.fact_source_metadata(en)]}, conflict_evidence=evidence,
        _content="我是测试。\n\n" + agent.chinese_fact_output(zh) + "。\n",
        _english_content="I am Test.\n\n" + agent.english_paragraph_output(en) + "\n"), errors


def test_preview_preserves_complete_both_languages_and_source_conflict(tmp_path):
    data, errors = group()
    write_preview(tmp_path, "2026-01-01", [data], errors, "manual.pdf", "test")
    meta = json.loads((tmp_path / "preview_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "PREVIEW" and not meta["publishable"]
    assert not meta["release_eligible"] and meta["release_status"] == "FAILED_SAFE"
    for name, text in (("zh", "沿W19经MASGU、ATKAV和OLPAB。"), ("en", "Follow W19 via MASGU, ATKAV and OBLAP.")):
        body = (tmp_path / f"preview_{name}.txt").read_text(encoding="utf-8")
        assert body.startswith(NOTICE) and text in body and "UNVERIFIED" in body
    review = (tmp_path / "review.md").read_text(encoding="utf-8")
    assert "p.10" in review and "p.20" in review and "OLPAB" in review and "OBLAP" in review
    assert not (tmp_path / ".success").exists()


@pytest.mark.parametrize("mode", ["preview", "release"])
@pytest.mark.parametrize("blocked", [False, True])
def test_real_entry_gates_preview_and_preserves_formal_last_good(tmp_path, monkeypatch, mode, blocked):
    config = tmp_path / "config"
    config.mkdir()
    (config / "prep_settings.json").write_text(json.dumps({"auto_update_airport_experience": True}), encoding="utf-8")
    (config / "airport_experience.json").write_text('{"protected":true}', encoding="utf-8")
    protected = tmp_path / "flight_preparation"
    protected.mkdir()
    names = ["latest.txt", "latest_en.txt", "latest_meta.json", "2026-10-26_航前准备.txt", ".success"]
    for name in names:
        (protected / name).write_text("LAST_GOOD", encoding="utf-8")
    args = SimpleNamespace(repo=str(tmp_path), target_date="2026-10-26", days_ahead=1, mode=mode,
                           flight_number="", departure="", arrival="", generate_english="no")
    monkeypatch.setattr(agent, "parse_args", lambda: args)
    event = replace(flight(), start=flight().start.replace(year=2026, month=10, day=26))
    monkeypatch.setattr(agent, "parse_ics", lambda *a: [event])
    monkeypatch.setattr(agent, "select_continuous_flight_group", lambda *a, **k: [event])
    monkeypatch.setattr(agent, "extract_airport_mapping", lambda *a: {})
    monkeypatch.setattr(agent, "resolve_icao", lambda *a: "AAAA")
    monkeypatch.setattr(agent, "airport_risks", lambda *a, **k: ({}, {x: ["source"] for x in event.route}, {}, [], "manual.pdf", "test", "PDF"))
    zh, en = facts()
    typical = {x: [] for x in event.route}
    core = {x: [replace(zh, airport=x)] for x in event.route}
    en_core = {x: [replace(en, airport=x)] for x in event.route}
    monkeypatch.setattr(agent, "briefing_fact_sets", lambda *a, **k: (typical, core, [zh]))
    monkeypatch.setattr(agent, "english_briefing_fact_sets", lambda *a, **k: (typical, en_core, [en]))
    monkeypatch.setattr(agent, "render_chinese_briefing", lambda *a, **k: "完整中文。")
    monkeypatch.setattr(agent, "render_english_briefing", lambda *a, **k: "Complete English.")
    monkeypatch.setattr(agent, "validate_content", lambda *a, **k: [])
    monkeypatch.setattr(agent, "validate_airport_fact_bindings", lambda *a: [])
    monkeypatch.setattr(agent, "validate_bilingual_facts", lambda *a: [])
    monkeypatch.setattr(agent, "validate_english_source_facts", lambda *a: [])
    monkeypatch.setattr(agent, "validate_cross_language_conflicts", lambda *a, **k: ["UNRESOLVED"] if blocked else [])
    monkeypatch.setattr(agent, "english_generation_decision", lambda *a: (True, False, []))
    monkeypatch.setattr(agent, "append_github_summary", lambda *a: None)
    if mode == "preview":
        monkeypatch.setattr(agent, "update_airport_experience", lambda *a, **k: pytest.fail("preview must not update experience"))
    else:
        monkeypatch.setattr(agent, "update_airport_experience", lambda *a, **k: ({}, []))
    result = agent.main()
    assert (tmp_path / "agent_output/flight_prep/previews/2026-10-26/preview_meta.json").is_file()
    if mode == "preview":
        assert result == 3  # cannot pass a production success()-gated commit step
        assert all((protected / name).read_text(encoding="utf-8") == "LAST_GOOD" for name in names)
        assert (config / "airport_experience.json").read_text(encoding="utf-8") == '{"protected":true}'
        out = tmp_path / "agent_output/flight_prep/previews/2026-10-26"
        meta = json.loads((out / "preview_meta.json").read_text(encoding="utf-8"))
        assert meta["release_eligible"] != blocked and not meta["publishable"]
        assert "完整中文" in (out / "preview_zh.txt").read_text(encoding="utf-8")
        assert "Complete English" in (out / "preview_en.txt").read_text(encoding="utf-8")
        assert not (tmp_path / "agent_output/flight_prep/status.json").exists()
    elif blocked:
        assert result == 2 and not (protected / ".success").exists()
        assert (protected / "latest.txt").read_text(encoding="utf-8") == "LAST_GOOD"
    else:
        assert result == 0 and (protected / ".success").read_text(encoding="utf-8") == "SUCCESS\n"


def test_render_keeps_every_route_fact_once_and_fixed_template(monkeypatch):
    monkeypatch.setattr(agent, "group_personal_intro", lambda *a: "我是测试。")
    monkeypatch.setattr(agent, "english_personal_intro", lambda *a: "I am Test.")
    monkeypatch.setattr(agent, "feedback_text", lambda *a: "PF/PM评价")
    monkeypatch.setattr(agent, "feedback_text_en", lambda *a: "Latest PF/PM feedback:")
    zh, en = facts()
    typical = {x: [] for x in flight().route}
    cn = {x: [replace(zh, airport=x, text_zh=x + "原始地面要求。"),
               replace(zh, airport=x, text_zh=x + "原始航路要求。", operational_phase="enroute")]
          for x in flight().route}
    eng = {x: [replace(en, airport=x, text_en=x + " ground restriction."),
                replace(en, airport=x, text_en=x + " route restriction.", operational_phase="enroute")]
           for x in flight().route}
    for renderer, core, language in ((agent.render_chinese_briefing, cn, "zh"), (agent.render_english_briefing, eng, "en")):
        body = renderer(flight(), date(2026, 10, 26), {}, [], typical, core)
        for items in core.values():
            for fact in items:
                text = agent.chinese_fact_output(fact) if language == "zh" else agent.english_fact_output(fact)
                assert body.count(text) == 1
        assert ("本次航班整体风险：" if language == "zh" else "Overall flight risks:") in body
        assert ("航路和通用风险：" if language == "zh" else "En-route and general risks:") in body


def test_reviewed_data_keeps_every_operating_guard():
    root = Path(__file__).resolve().parents[1]
    for review in agent.load_chinese_translation_reviews(root):
        fact = agent.BilingualFact(review["english_source_record_id"],
            agent.SOURCE_HEADING_RE.sub("", review["source_text_zh"]), review["text_en"],
            source_version=review["manual_version"], source_page=review["source_page_zh"],
            english_source_page=review["source_page_en"], source_text_zh=review["source_text_zh"],
            source_text_en=review["original_text_en"],
            source_record_ids=tuple([review["source_record_id"], *(item["source_record_id"] for item in review.get("additional_chinese_sources", []))]),
            source_original_texts=tuple([review["source_text_zh"], *(item["text"] for item in review.get("additional_chinese_sources", []))]),
            english_source_record_id=review["english_source_record_id"],
            english_source="translated_from_chinese", translation_provenance=review)
        assert not agent.validate_chinese_translation(fact), review["english_source_record_id"]


def test_runway_procedure_comparison_preserves_the_designator_across_languages():
    assert agent.manual_pairing_tokens("使用RNP13进近，只有LNAV。") == agent.manual_pairing_tokens("Use RNP13 approach, LNAV only.")
    assert agent.manual_pairing_tokens("使用RNP13进近，只有LNAV。") != agent.manual_pairing_tokens("Use RNP31 approach, LNAV only.")
    assert agent.manual_pairing_tokens("通过一万尺。") == agent.manual_pairing_tokens("Passing 10,000ft.")
    assert agent.manual_pairing_tokens("通过一万尺。") != agent.manual_pairing_tokens("Passing 9000ft.")
    assert "terrain" not in agent.bilingual_semantic_mismatches("从舟山方向进场。", "Approach from the Zhoushan direction.")
    assert "terrain" in agent.bilingual_semantic_mismatches("本场西侧有山。", "Approach from the west.")


def test_multi_record_translation_requires_every_current_original():
    from test_flight_prep_chinese_primary_english import sources, translate
    records, chinese, review = sources()
    extra = dict(source_record_id="zh:second", text="必须保持3000ft。", page="11",
                 hash=agent.source_text_hash("必须保持3000ft。"))
    review["additional_chinese_sources"] = [extra]
    review["text_en"] += " You must maintain 3000ft."
    english = records["AAAA"][1]
    english.pop("chinese_translation_review")
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [review])
    assert "chinese_translation_review" not in english
    second = {**records["AAAA"][0], "source_record_id": extra["source_record_id"],
              "fact_id": extra["source_record_id"], "source_page": "11",
              "source_original_text": extra["text"], "text_zh": extra["text"]}
    records["AAAA"].append(second)
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [review])
    fact = translate(records, chinese)[0]
    assert fact.english_source == "translated_from_chinese"
    assert extra["source_record_id"] in fact.source_record_ids
    assert not agent.validate_chinese_translation(fact)
    assert agent.validate_chinese_translation(replace(fact, text_en=fact.en.replace("3000ft", "3500ft")))
    assert agent.validate_chinese_translation(replace(fact, source_original_texts=(review["source_text_zh"],)))


@pytest.mark.parametrize("number,runway", [("1", "26"), ("2", "08"), ("12", "31")])
def test_source_item_number_is_not_a_decimal_runway(number, runway):
    raw = f"{number}.{runway}号跑道进近时注意速度。"
    fact = agent.BilingualFact("source", raw, "", source_verbatim=True, source_text_zh=raw, category="core")
    assert agent.chinese_fact_output(fact) == f"{runway}号跑道进近时注意速度"
    assert agent.manual_pairing_tokens(raw) == agent.manual_pairing_tokens(agent.chinese_fact_output(fact))
    assert fact.source_text_zh == raw
    other = replace(fact, text_zh="跑道坡度1.26%，注意性能限制。")
    assert "1.26%" in agent.chinese_fact_output(other)


def test_enroute_scope_accepts_double_dash_and_phase_prefix_without_city_guessing():
    registry = {"AAAA": {"canonical_zh": "甲地机场"}, "BBBB": {"canonical_zh": "乙地机场"}}
    routes = agent.record_route_scope({"category": "core", "operational_phase": "enroute"},
                                     "航路：甲地——乙地，使用指定航路。", registry)
    assert routes == (("甲地机场", "乙地机场"),)
    assert not agent.record_route_scope({"category": "typical"}, "甲地——乙地曾发生事件。", registry)
    assert agent.record_route_scope({"category": "core", "operational_phase": "arrival"},
        "进场：甲地-乙地：保持指定高度。", registry) == (("甲地机场", "乙地机场"),)


def test_named_english_route_prefixes_share_the_same_approved_aliases():
    aliases = agent.english_route_aliases([{"icao": "AAAA", "name": "Alpha/Field"},
                                          {"icao": "BBBB", "name": "Bravo/Field"}])
    for text in ("For the Alpha-Bravo route, use W19.", "At the Alpha-Bravo section, maintain 3000ft.",
                 "Alpha-Bravo: contact ATC."):
        assert agent.english_source_route_scope({"text_en": text, "category": "core"}, aliases) == (("AAAA", "BBBB"),)
    assert not agent.english_source_route_scope({"text_en": "Alpha-Bravo once had an event.", "category": "typical"}, aliases)
    assert agent.english_source_route_scope({"text_en": "Operations in the AAAA-BBBB sector require W19.", "category": "core"}, aliases) == (("AAAA", "BBBB"),)
    assert agent.english_source_route_scope({"text_en": "For northern inbound flights such as Alpha-Bravo, maintain 3000ft.",
        "category": "core"}, aliases) == (("AAAA", "BBBB"),)


def test_parenthesized_event_heading_and_wrapped_frequency_are_not_lost():
    raw = """IV. Entry
(6) Alpha-Bravo: Contact approach
125.45 minutes in advance before descent.
(7) Maintain the cleared altitude.
(6) Detailed description of typical unsafe incidents:
1. A high landing load event occurred.
"""
    facts = agent.extract_english_manual_facts(raw)
    assert any("125.45 minutes" in fact.text and "Alpha-Bravo" in fact.text for fact in facts)
    assert not any(fact.text.startswith("minutes") for fact in facts)
    assert any(fact.category == "typical" and "landing load" in fact.text for fact in facts)


@pytest.mark.parametrize("text", ["上述情况若未主动向海关说明，将承担法律后果。", "廊桥内侧有专用电话号码，可远程开门。"])
def test_staff_administration_does_not_enter_operating_material(text):
    assert agent.source_operational_value_issue(text)
    assert not agent.source_operational_value_issue("滑行道有障碍，必须按ATC指令滑行。")
    mixed = agent.filter_source_administrative_sentences("滑行时必须避让障碍。上述情况未向海关说明将承担法律后果。")
    assert "必须避让障碍" in mixed and "法律后果" not in mixed


def test_unresolved_named_route_remains_visible_but_cannot_release():
    text = "For the Alpha-Bravo route, maintain 3000ft."
    fact = agent.BilingualFact("en:route", "", text, airport="AAAA", language="en",
        category="core", source="PDF", source_verbatim=True, source_text_en=text,
        source_page="12", source_file="manual.pdf", english_source="source_backed",
        english_source_record_id="en:route", source_authority="latest_airport_manual", source_version="test")
    assert any("适用性未核实" in error for error in agent.validate_english_source_facts("AAAA", [fact]))
    assert fact.en == text  # never silently discard an unverified source condition
    scoped = replace(fact, route_scope=(("AAAA", "BBBB"),))
    assert not any("适用性未核实" in error for error in agent.validate_english_source_facts("AAAA", [scoped]))
    history = replace(fact, category="typical")
    assert not any("适用性未核实" in error for error in agent.validate_english_source_facts("AAAA", [history]))
