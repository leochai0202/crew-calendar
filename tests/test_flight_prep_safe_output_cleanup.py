"""General output fixes must not hide manual conflicts or remove real risks."""
from copy import deepcopy
from datetime import date

import pytest

from crew_agents import flight_prep_agent as agent
from test_flight_prep_independent_languages import flight, record, selected


def chinese_record(text, identity="zh:one", **extra):
    return {"airport": "AAAA", "category": "core", "source_verbatim": True,
            "text_zh": text, "source_original_text": text, "source": "PDF",
            "source_authority": "latest_airport_manual", "source_file": "knowledge/pdf/source.pdf",
            "source_version": "test", "source_page": "10", "fact_id": identity,
            "source_record_id": identity, "source_heading": "AAAA", **extra}


@pytest.mark.parametrize("text,bare", [
    ("机场标高：13ft。", True), ("地面：机场标高：8ft。", True),
    ("Airportelevation: 13 ft.", True), ("Airport elevation: 1500m (4921ft).", True),
    ("机场标高较高，起飞性能需要复核。", False),
    ("机场标高7358ft，跑道坡度16.8m，注意性能限制。", False),
    ("Airport elevation: 13ft; runway gradient affects takeoff performance.", False),
    ("Terrain rises to 7358ft near the departure route.", False),
])
def test_only_bare_elevation_catalogue_fields_are_filtered(text, bare):
    assert agent.standalone_airport_elevation(text) == bare


@pytest.mark.parametrize("classification,allowed", [
    ("高原机场。", True), ("运行特点：一般高原机场。", True),
    ("高原机场：一般高原机场。", True), ("High-elevation airport YES", True),
    ("该机场属于一般高原机场。", True), ("是否为高原机场 是", True),
    ("High-altitude airport YES", True), ("高原机场：否。", False),
    ("High-elevation airport NO", False), ("地形复杂，机场标高7358ft。", False),
    ("若运行高原机场，注意性能。", False),
])
def test_highland_is_an_explicit_source_classification_not_an_inferred_height(classification, allowed):
    item = chinese_record(classification)
    if classification.startswith("High-"):
        item.update(language="en", text_en=classification)
    assert agent.has_sourced_highland_classification([item]) == allowed
    assert not agent.has_sourced_highland_classification([{**item, "category": "typical"}])
    assert not agent.has_sourced_highland_classification([{**item, "source_authority": "unknown"}])


def test_conflicting_classifications_do_not_authorize_a_bare_elevation_field():
    records = [chinese_record("高原机场。"),
               {**chinese_record(""), "language": "en", "text_en": "High-elevation airport NO"}]
    assert not agent.has_sourced_highland_classification(records)
    assert not agent.has_sourced_highland_classification(list(reversed(records)))


def test_another_airports_classification_cannot_authorize_elevation():
    records = [chinese_record("机场标高：13ft。"),
               chinese_record("高原机场。", "other:class", airport="BBBB")]
    assert not agent.source_record_facts("AAAA", records, category="core")
    assert not agent.has_sourced_highland_classification(records, "AAAA")


@pytest.mark.parametrize("highland", [False, True])
def test_both_languages_filter_ordinary_elevation_without_losing_terrain_or_performance(highland):
    cn = [chinese_record("机场标高：7358ft。", "zh:height"),
          chinese_record("机场标高7358ft，跑道坡度16.8m，注意性能限制。", "zh:risk")]
    en = [record("Airport elevation: 7358ft.", identity="en:height"),
          record("Terrain rises near Runway 08; verify takeoff performance.", identity="en:risk")]
    records = cn + en + ([chinese_record("高原机场。", "zh:classification")] if highland else [])
    before = deepcopy(records)
    exclusions = []
    zh = agent.source_record_facts("AAAA", records, category="core", exclusion_log=exclusions)
    english = selected(records)[2]
    assert ("zh:height" in {f.fact_id for f in zh}) == highland
    assert ("en:height" in {f.fact_id for f in english}) == highland
    assert "zh:risk" in {f.fact_id for f in zh} and "en:risk" in {f.fact_id for f in english}
    assert records == before
    if not highland:
        assert any("高原" in item["reason"] for item in exclusions)


@pytest.mark.parametrize("text,expected", [
    ("Flight crews are reminded to:", "Flight crews are reminded to:"),
    ("Flight crews are reminded to:.", "Flight crews are reminded to:"),
    ("Observe the following; .", "Observe the following;"),
    ("If ATC clears Runway 08, observe the following:", "If ATC clears Runway 08, observe the following:"),
    ("Maintain 3000ft.", "Maintain 3000ft."),
    ("Report established!", "Report established!"),
    ("Read back the clearance?", "Read back the clearance?"),
    ("Maintain 3000ft;", "Maintain 3000ft;"),
    ("Contact ATC on 121.950 MHz", "Contact ATC on 121.950 MHz."),
])
def test_paragraph_terminal_punctuation_does_not_change_operating_text(text, expected):
    fact = agent.BilingualFact("source", "", text)
    assert agent.english_paragraph_output(fact) == expected
    assert fact.en == text
    assert agent.manual_pairing_tokens(expected) == agent.manual_pairing_tokens(text)


def test_full_english_render_preserves_intro_and_independent_list_paragraphs(monkeypatch):
    raw = [record("When operating northbound, use Taxiway A. Flight crews are reminded to:", identity="parent"),
           record("Observe the revised taxiway directions.", identity="child1"),
           record("When cleared by ATC, maintain 3000ft.", identity="child2")]
    for number, item in enumerate(raw):
        item["source_sequence"] = number
    before = deepcopy(raw)
    typical, core, facts = selected(raw)
    monkeypatch.setattr(agent, "english_personal_intro", lambda *args: "Personal information")
    monkeypatch.setattr(agent, "feedback_text_en", lambda *args: "PF/PM feedback")
    content = agent.render_english_briefing(flight(), date(2026, 10, 26), {}, [], typical, core)
    assert "reminded to:\n\nObserve" in content
    assert ":." not in content and "3000ft." in content
    assert [f.fact_id for f in facts] == ["parent", "child1", "child2"]
    assert agent.validate_english_source_facts("AAAA", facts) == []
    assert raw == before


def test_chinese_table_prose_separator_does_not_modify_ecam_or_numbers():
    text = "受地面温度影响+ 易发生进近剖面低+ 着陆距离远，NAV ADS-B RPTG 1+2 FAULT。"
    fact = agent.BilingualFact("source", text, "", source_verbatim=True, category="typical", source_text_zh=text)
    content = agent.chinese_fact_output(fact)
    assert "影响，易发生进近剖面低，着陆距离远" in content
    assert "NAV ADS-B RPTG 1+2 FAULT" in content
    assert fact.zh == fact.source_text_zh == text


def test_joined_ordinary_words_are_layout_only_not_aviation_term_replacements():
    text = "After thissection, contact ATC. NAV ADS-B RPTG 1+2 FAULT."
    output = agent.english_layout_text(text)
    assert "this section" in output
    assert "".join(output.split()) == "".join(text.split())
