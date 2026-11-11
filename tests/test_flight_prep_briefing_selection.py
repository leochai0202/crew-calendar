"""Briefing content, not just presence/counts: decision value and source safety."""
from dataclasses import replace
from datetime import date, datetime
import re

import pytest

from crew_agents import flight_prep_agent as a
from crew_agents.ics_utils import CalendarEvent


def fact(identity, text, *, language="zh", category="core", **kwargs):
    return a.BilingualFact(identity, text if language == "zh" else "", text if language == "en" else "",
        language=language, category=category, airport="甲机场", source_verbatim=True,
        source_text_zh=text if language == "zh" else "", source_text_en=text if language == "en" else "",
        source_file="knowledge/pdf/manual.pdf", source_page="12", source_heading="甲机场",
        source_section=category, source_version="test", source_record_ids=(identity,), **kwargs)


def choose(facts, category="core", role="transit", log=None):
    return a.select_source_briefing_content(facts, role, category=category, exclusion_log=log)


@pytest.mark.parametrize("language,inventory,restriction,reference", [
    ("zh", "跑道信息：08/26（3000m×45m）。", "使用08号跑道时，入口内移150m；湿跑道禁止顺风起飞。", "无线电失效程序：参阅细则2.22.5。"),
    ("en", "Runway Information: 08/26 (3000m x 45m).", "When using Runway 08, the threshold is displaced 150m; tailwind takeoff is prohibited on a wet runway.", "Radio failure procedure: Refer to Rule 2.22.5."),
])
def test_source_verbatim_is_not_a_pass_for_catalogues_or_empty_references(language, inventory, restriction, reference):
    sources = [fact("table", inventory, language=language), fact("limit", restriction, language=language),
               fact("pointer", reference, language=language)]
    if language == "zh":
        sources[0] = replace(sources[0], text_en="Runway Information: 08/26 (3000m x 45m).")
    before = list(sources)
    log = []
    selected = choose(sources, log=log)
    assert [item.fact_id for item in selected] == ["limit"]
    assert (selected[0].en if language == "en" else selected[0].zh) == restriction
    assert sources == before
    assert {entry["fact_id"] for entry in log} == {"table", "pointer"}
    assert all(entry["original_text"] and entry["source_page"] == "12" and entry["reason"] for entry in log)


def test_distinct_controls_are_not_evicted_to_meet_a_paragraph_count():
    restrictions = [fact(str(i), f"使用滑行道T{i}时，翼展不得超过{30+i}米。") for i in range(1, 18)]
    selected = choose(restrictions)
    assert selected == restrictions
    assert [x.source_text_zh for x in selected] == [x.zh for x in restrictions]


def test_reference_with_a_condition_or_limit_is_not_an_empty_pointer():
    sources = [fact("limit", "起飞程序：参阅EFB，仅允许08号跑道。"),
               fact("en-limit", "Departure procedure: Refer to EFB only below 3000ft.", language="en")]
    assert choose(sources) == sources


def test_unknown_runway_translation_cannot_hide_a_potential_source_conflict():
    source = fact("unbound", "跑道信息：08/26（3000m×45m）。")
    assert choose([source]) == [source]


def test_papi_conflict_and_special_runway_data_are_never_removed_as_catalogue():
    sources = [fact("papi", "PAPI信息：08：3°，MEHT 20m；26：3.2°，MEHT 21m。"),
               fact("slope", "跑道信息：08/26（3000m×45m），08号跑道坡度1.2%，注意起飞性能。"),
               fact("eosid", "单发离场程序：参阅EOSID图。")]
    assert choose(sources) == sources
    conflict = fact("dimensions", "跑道信息：08/26（3000m×45m）。")
    conflict = replace(conflict, text_en="Runway Information: 08/26 (3100m x 45m).", english_source_record_id="en-table")
    assert a.validate_cross_language_conflicts([conflict], [replace(conflict, language="en")])
    assert choose([conflict]) == [conflict]


def test_literal_duplicate_keeps_provenance_but_shared_topic_never_drops_unique_condition():
    base = fact("a", "当能见度不足时不得进入滑行道。", role_scope=("departure",))
    duplicate = replace(base, fact_id="b")
    different = fact("c", "当能见度不足时不得进入跑道。", role_scope=("departure",))
    log = []
    assert choose([base, duplicate, different], log=log) == [base, different]
    assert log[0]["original_text"] == duplicate.zh
    assert log[0]["reason"].startswith("exact_duplicate_of:")


@pytest.mark.parametrize("texts", [
    ["Runway slope is 0.5%.", "Runway slope is 05%."],
    ["Maintain 3000ft.", "Do not maintain 3000ft."],
    ["Maintain 3000ft.", "When cleared, maintain 3000ft."],
    ["保持3000ft。", "未经许可不得保持3000ft。"],
    ["13: PAPI 3 degrees, MEHT 20m.", "31: PAPI 3 degrees, MEHT 20m."],
])
def test_deduplication_never_erases_decimal_negation_or_condition(texts):
    rows = [fact(str(i), text, language="en" if text[0].isascii() else "zh") for i, text in enumerate(texts)]
    assert choose(rows) == rows


def test_whole_unchanged_sentence_can_be_subsumed_with_an_audit_reason():
    short = fact("short", "无ATIS。")
    detailed = fact("detail", "无ATIS。需联系塔台获取天气。")
    log = []
    assert choose([short, detailed], log=log) == [detailed]
    assert log[0]["reason"] == "complete_source_text_retained_in:detail"


def test_instruction_after_event_omits_request_subject_without_erasing_historical_actor():
    value = "曾发生机组未复诵事件，请机组注意复诵。"
    assert a.omit_operating_crew_subject(value, "zh", "core") == "曾发生机组未复诵事件，请注意复诵。"
    assert a.omit_operating_crew_subject(value, "zh", "typical") == value
    assert a.omit_operating_crew_subject("机组须核实气压基准。", "zh", "core") == "须核实气压基准。"


@pytest.mark.parametrize("language,texts", [
    ("zh", ["曾发生滑行偏差。", "曾发生滑错路线。", "曾发生1000ft未建立着陆形态。", "曾发生偏离指令高度。"]),
    ("en", ["A taxi deviation occurred.", "A taxi routing error occurred.", "Landing configuration was not established at 1000ft.", "A deviation from assigned altitude occurred."]),
])
def test_typical_selection_represents_different_events_not_first_three_rows(language, texts):
    rows = [fact(str(i), text, language=language, category="typical", source_sequence=i) for i, text in enumerate(texts)]
    log = []
    selected = choose(rows, category="typical", log=log)
    assert [x.fact_id for x in selected] == ["0", "2", "3"]
    assert (selected[1].en if language == "en" else selected[1].zh) == texts[2]
    assert log[0]["original_text"] == texts[1] and log[0]["reason"].startswith("typical_representative_selection")


@pytest.mark.parametrize("text,expected", [
    ("1. 当ATC许可后，保持3000ft。", "当ATC许可后，保持3000ft。"),
    ("1、不得提前转弯。", "不得提前转弯。"),
    ("• When cleared, maintain 3000ft.", "When cleared, maintain 3000ft."),
    ("0.59%为跑道坡度。", "0.59%为跑道坡度。"),
    ("13号跑道使用ILS Y。", "13号跑道使用ILS Y。"),
    ("AD2.20 3.2.4 requires monitoring 119.25 MHz.", "AD2.20 3.2.4 requires monitoring 119.25 MHz."),
    ("依次执行：1. 先取得许可。2. 再转弯。", "依次执行：\n\n先取得许可。\n\n再转弯。"),
    ("1. Obtain clearance. 2. Then turn.", "Obtain clearance.\n\nThen turn."),
    ("1.1. 使用08号跑道时保持3000ft。", "使用08号跑道时保持3000ft。"),
])
def test_rendering_removes_list_decoration_not_operating_numbers(text, expected):
    assert a.briefing_prose_without_ordinals(text) == expected


def test_both_language_rendered_payloads_preserve_template_conditions_and_blank_paragraphs():
    duty = CalendarEvent(uid="test", summary="9C0001 甲机场→乙机场", start=datetime(2026, 11, 13, 10),
        end=datetime(2026, 11, 13, 12), description="", location="", properties={})
    profile = {"stage_hours": 93, "stage_landings": 21, "landings_90_days": 8, "landings_30_days": 8}
    core = {airport: [replace(fact("c", "1、使用08号跑道时，必须保持3000ft。"), airport=airport,
                         text_en="1. When using Runway 08, maintain 3000ft.")] for airport in duty.route}
    typical = {airport: [replace(fact("t", "1. 曾发生滑错路线。", category="typical"), airport=airport,
                            text_en="1. A taxi routing error occurred.")] for airport in duty.route}
    zh = a.render_chinese_briefing(duty, date(2026, 11, 13), profile, [], typical, core)
    en = a.render_english_briefing(duty, date(2026, 11, 13), profile, [], typical, core)
    for body in (zh, en):
        assert not re.search(r"(?m)^\s*(?:\d+[.、)]\s|[•●▪])", body)
        assert "3000ft" in body
        assert "\n\n" in body
        assert "整体风险" not in body and "航路及通用风险" not in body
    assert "近30天起落8个" in zh and "8 landings in the last 30 days" in en
    assert "使用08号跑道时，必须保持3000ft" in zh
    assert "When using Runway 08, maintain 3000ft." in en
    assert "机场：\n\n曾发生滑错路线。\n\n" in zh
    assert "Airport:\n\nA taxi routing error occurred.\n\n" in en


def test_english_spacing_repair_changes_only_whitespace_not_identifiers_or_values():
    raw = "After DOTMI, itflies directly to ALLEY on 121.3."
    fixed = a.english_layout_text(raw)
    assert "it flies" in fixed
    assert re.sub(r"\s", "", raw) == re.sub(r"\s", "", fixed)


@pytest.mark.parametrize("language,raw", [
    ("zh", "保持航向；2. 获得许可后转弯；4. 核实3000ft。"),
    ("en", "Maintain heading; 2. Turn when cleared; 4. Verify 3000ft."),
])
def test_unresolved_inline_item_structure_still_blocks_after_rendering(language, raw):
    duty = CalendarEvent(uid="test", summary="9C0001 甲机场→乙机场", start=datetime(2026, 11, 13, 10),
        end=datetime(2026, 11, 13, 12), description="", location="", properties={})
    renderer = a.render_chinese_briefing if language == "zh" else a.render_english_briefing
    rows = {airport: [replace(fact("unresolved", raw, language=language), airport=airport)]
            for airport in duty.route}
    body = renderer(duty, date(2026, 11, 13), {}, [], {}, rows)
    assert "3000ft" in body and "2." in body and "4." in body
    assert "典型事件和核心威胁不得使用数字编号或项目符号" in a.validate_content(
        body, duty, {}, list(duty.route), language=language, typical_facts={}, core_facts=rows)


@pytest.mark.parametrize("language,text", [
    ("zh", "跑道坡度：0.59%；按AD2.20 3.2.4执行。"),
    ("en", "Runway slope: 0.59%; follow AD2.20 3.2.4."),
])
def test_inline_number_guard_does_not_reject_operating_data(language, text):
    duty = CalendarEvent(uid="test", summary="9C0001 甲机场→乙机场", start=datetime(2026, 11, 13, 10),
        end=datetime(2026, 11, 13, 12), description="", location="", properties={})
    renderer = a.render_chinese_briefing if language == "zh" else a.render_english_briefing
    rows = {airport: [replace(fact("data", text, language=language), airport=airport)]
            for airport in duty.route}
    body = renderer(duty, date(2026, 11, 13), {}, [], {}, rows)
    assert not any("数字编号" in error for error in a.validate_content(
        body, duty, {}, list(duty.route), language=language, typical_facts={}, core_facts=rows))


@pytest.mark.parametrize("language", ["zh", "en"])
def test_locked_feedback_heading_and_each_role_are_separate_complete_paragraphs(language):
    profile = {"recent_feedback": {"PF": "Maintain the cleared altitude", "PM": "Read back the clearance"}}
    feedback = a.feedback_text(profile) if language == "zh" else a.feedback_text_en(profile)
    heading, pf, pm = feedback.split("\n\n")
    assert heading == ("上一次飞行中机长/教员对我优缺点的评价（作为PF/PM各取最近一次）："
                       if language == "zh" else "Latest PF/PM feedback:")
    assert "PF" in pf and "PM" not in pf and "Maintain the cleared altitude" in pf
    assert "PM" in pm and "PF" not in pm and "Read back the clearance" in pm
    duty = CalendarEvent(uid="test", summary="9C0001 甲机场→乙机场", start=datetime(2026, 11, 13, 10),
        end=datetime(2026, 11, 13, 12), description="", location="", properties={})
    prefix = "我是测试。" if language == "zh" else "I am Test."
    headings = ("典型不安全事件：", "核心威胁：") if language == "zh" else ("Typical unsafe events:", "Core threats:")
    body = "\n\n".join([prefix, feedback, *headings])
    assert not any("讲评" in error for error in a.validate_content(body, duty, profile, [], language=language))
    # An operational source paragraph can mention a pilot role; it is not a
    # second personal-feedback paragraph and must not fail this format check.
    with_source_role = body + "\n\n" + pf
    assert not any("讲评" in error for error in a.validate_content(with_source_role, duty, profile, [], language=language))
    combined = body.replace(pf + "\n\n" + pm, pf + " " + pm)
    assert "PF和PM讲评必须分别独立成段并空行" in a.validate_content(combined, duty, profile, [], language=language)
    no_blank = body.replace(heading + "\n\n", heading + "\n")
    assert "PF/PM讲评标题必须独立成段并空行" in a.validate_content(no_blank, duty, profile, [], language=language)


@pytest.mark.parametrize("language", ["zh", "en"])
@pytest.mark.parametrize("role", ["PF", "PM"])
def test_feedback_format_does_not_invent_an_unavailable_role(language, role):
    profile = {"recent_feedback": {role: "Keep the cleared altitude"}}
    feedback = a.feedback_text(profile) if language == "zh" else a.feedback_text_en(profile)
    assert len(feedback.split("\n\n")) == 2
    paragraph = feedback.split("\n\n")[1]
    assert role in paragraph and ("PM" if role == "PF" else "PF") not in paragraph
    assert "Keep the cleared altitude" in paragraph
