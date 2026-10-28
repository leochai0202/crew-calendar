"""Chinese-primary translation is source-bound, reviewed data, not fallback prose."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
import json
from pathlib import Path

import pytest

from crew_agents import flight_prep_agent as agent
from test_flight_prep_independent_languages import flight, record


ROOT = Path(__file__).resolve().parents[1]


def sources(zh="收到起飞许可后立即开始起飞滑跑。", original="Begin taxiing immediately after takeoff clearance.",
            translated="Begin the takeoff roll immediately after takeoff clearance."):
    en = record(original, phase="departure", identity="en:source")
    en["source_record_id"] = en["fact_id"]
    review = dict(manual_version=en["source_version"], icao="AAAA", source_record_id="zh:record",
                  source_text_zh=zh, original_text_en=original, text_en=translated,
                  source_text_hash=agent.source_text_hash(zh), original_english_hash=agent.source_text_hash(original),
                  source_page_zh="10", source_page_en=en["source_page"], english_source_record_id=en["fact_id"],
                  reviewed_by="TEST_SOURCE_REVIEW", reviewed_date="2026-10-28", review_note="Checked complete source condition/action.")
    chinese = agent.BilingualFact("zh:fact", zh, original, airport="AAAA", category="core",
        source="PDF", source_file=en["source_file"], source_authority="latest_airport_manual",
        source_version=en["source_version"], source_page="10", source_text_zh=zh,
        source_heading="AAAA airport operating characteristics", source_section="Departure",
        source_clauses=(zh,), source_original_texts=(zh,), source_record_ids=("zh:record",),
        english_source_record_id=en["fact_id"], english_source_page=en["source_page"],
        operational_phase="departure", role_scope=("departure",))
    raw = dict(asdict(chinese), source_record_id="zh:record", source_original_text=zh, source_verbatim=True)
    records = {"AAAA": [raw, en], "BBBB": []}
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [review])
    return records, chinese, review


def translate(records, chinese, event=None):
    return agent.english_briefing_fact_sets(event or flight(), date(2026, 10, 26), records,
                                          chinese_facts=[chinese])[2]


def test_reviewed_translation_keeps_both_originals_and_pages():
    records, chinese, review = sources()
    original = deepcopy(records)
    fact = translate(records, chinese)[0]
    assert fact.english_source == "translated_from_chinese"
    assert fact.source_text_zh == review["source_text_zh"] and fact.source_text_en == review["original_text_en"]
    assert fact.en == review["text_en"] and fact.english_source_record_id == review["english_source_record_id"]
    assert fact.source_page == "10" and fact.english_source_page == "20"
    assert agent.fact_source_metadata(fact)["translation_provenance"] == review
    assert not agent.validate_english_source_facts("AAAA", [fact])
    assert not agent.validate_cross_language_conflicts([chinese], [fact], records)
    assert records == original  # selection/rendering cannot overwrite raw manual data


@pytest.mark.parametrize("field,value", [
    ("icao", "CCCC"), ("manual_version", "other"), ("source_page_zh", "11"),
    ("source_page_en", "21"), ("source_record_id", "another"),
    ("english_source_record_id", "other-en"), ("source_text_hash", "0" * 64),
    ("original_english_hash", "0" * 64),
])
def test_stale_or_different_sources_do_not_authorize_translation(field, value):
    records, chinese, review = sources()
    records["AAAA"][1].pop("chinese_translation_review")
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [{**review, field: value}])
    fact = translate(records, chinese)[0]
    assert fact.english_source == "source_backed" and fact.en == review["original_text_en"]
    assert agent.validate_cross_language_conflicts([chinese], [fact], records)


@pytest.mark.parametrize("zh,original,translated", [
    ("直到收到进入跑道指令才打开TCAS。", "TCAS should remain activated until receiving runway clearance.",
     "TCAS should remain activated until receiving runway clearance."),
    ("收到起飞许可后立即开始起飞滑跑。", "Begin taxiing after takeoff clearance.", "Begin taxiing after takeoff clearance."),
    ("ATC要求保持3000ft。", "ATC requires maintaining 3000ft.", "ATC requires maintaining 3500ft."),
    ("ATC要求保持3000ft。", "ATC requires maintaining 3000ft.", "ATC requires maintaining 3000m."),
    ("如果获准，保持3000ft。", "If cleared, maintain 3000ft.", "Maintain 3000ft."),
    ("必须保持3000ft。", "You must maintain 3000ft.", "You should maintain 3000ft."),
    ("收到许可后保持3000ft。", "Maintain 3000ft after clearance.", "Maintain 3000ft."),
])
def test_translation_still_requires_action_timing_and_critical_data(zh, original, translated):
    records, chinese, _ = sources(zh, original, translated)
    fact = translate(records, chinese)[0]
    assert agent.validate_english_source_facts("AAAA", [fact])


@pytest.mark.parametrize("changed", ["Remove the condition.", "Begin the takeoff roll and use an unpublished SID."])
def test_generated_text_cannot_differ_from_reviewed_complete_translation(changed):
    records, chinese, _ = sources()
    fact = translate(records, chinese)[0]
    assert agent.validate_english_source_facts("AAAA", [replace(fact, text_en=changed)])
    assert agent.validate_english_source_facts("AAAA", [replace(fact, translation_provenance={})])


def test_numeric_source_conflict_cannot_be_cleared_by_translating_to_chinese_numbers():
    records, chinese, _ = sources("ATC要求保持3000ft。", "ATC requires maintaining 3500ft.", "ATC requires maintaining 3000ft.")
    fact = translate(records, chinese)[0]
    assert any("未确认运行数据" in e for e in agent.validate_chinese_translation(fact))
    assert agent.validate_cross_language_conflicts([chinese], [fact], records)


@pytest.mark.parametrize("zh,original,translated", [
    ("沿W19经MASGU、ATKAV、OLPAB和NOMAR。", "Follow W19 via MASGU, ATKAV, OBLAP and NOMAR.",
     "Follow W19 via MASGU, ATKAV, OLPAB and NOMAR."),
    ("08号跑道只能用于起飞。", "Runway 26 is only permitted for takeoff.", "Runway 08 is only permitted for takeoff."),
    ("PAPI信息：08：入口内452米，3°，MEHT21.4m；26：入口内452米，3°，MEHT21.0m。",
     "PAPI Information: RWY 26: 452m, 3°, MEHT21.4m; RWY 08: 452m, 3°, MEHT21.0m.",
     "PAPI Information: RWY 08: 452m, 3°, MEHT21.4m; RWY 26: 452m, 3°, MEHT21.0m."),
])
def test_review_permission_cannot_resolve_waypoint_runway_or_table_data(zh, original, translated):
    records, chinese, _ = sources(zh, original, translated)
    event = replace(flight(), summary="9C0002 BBBB→AAAA") if agent.manual_basic_field(zh) == "papi" else None
    fact = translate(records, chinese, event)[0]
    assert any("未确认运行数据" in e for e in agent.validate_chinese_translation(fact))
    assert agent.validate_cross_language_conflicts([chinese], [fact], records)


def test_opposite_role_and_partial_chinese_selection_cannot_authorize_full_translation():
    records, chinese, _ = sources()
    reverse = replace(flight(), summary="9C0002 BBBB→AAAA")
    assert not translate(records, chinese, reverse)
    selected = agent.english_briefing_fact_sets(flight(), date(2026, 10, 26), records, chinese_facts=[])[2]
    assert selected[0].english_source == "translated_from_chinese"
    fact = translate(records, replace(chinese, text_zh="起飞滑跑。"))[0]
    assert fact.english_source == "source_backed"


def test_accurate_original_english_is_not_retranslated():
    records, chinese, _ = sources()
    records["AAAA"][1].pop("chinese_translation_review")
    records["AAAA"][1]["text_en"] = "Maintain the published SID restrictions."
    records["AAAA"][1]["source_original_text_en"] = records["AAAA"][1]["text_en"]
    fact = translate(records, chinese)[0]
    assert fact.english_source == "source_backed" and fact.en == "Maintain the published SID restrictions."


def test_translation_does_not_force_the_other_languages_selected_ids_or_role():
    records, chinese, _ = sources(
        "离港飞机直到收到进入跑道指令才打开TCAS；进港飞机脱离跑道后关闭TCAS。",
        "TCAS should remain activated until runway clearance for departing aircraft and until runway exit for arriving aircraft.",
        "For departing aircraft, activate TCAS only after runway-entry clearance. For arriving aircraft, deactivate TCAS after vacating the runway.")
    records["AAAA"][0].update(operational_phase="ground", role_scope=["arrival"])
    records["AAAA"][1].update(operational_phase="ground", role_scope=[])
    for event in (flight(), replace(flight(), summary="9C0002 BBBB→AAAA")):
        en = agent.english_briefing_fact_sets(event, date(2026, 10, 26), records, chinese_facts=[])[2]
        assert len(en) == 1 and en[0].english_source == "translated_from_chinese"
        assert not agent.validate_chinese_translation(en[0])


@pytest.mark.parametrize("mutation", ["hash", "missing_review", "duplicate"])
def test_translation_config_rejects_untraceable_reviews(tmp_path, mutation):
    _, _, review = sources()
    entries = [review]
    if mutation == "hash":
        review["source_text_hash"] = "0" * 64
    elif mutation == "missing_review":
        review.pop("review_note")
    else:
        entries.append(dict(review))
    (tmp_path / "config").mkdir()
    (tmp_path / agent.CHINESE_TRANSLATIONS_FILE).write_text(json.dumps(dict(schema_version=1, translations=entries)), encoding="utf-8")
    with pytest.raises(ValueError):
        agent.load_chinese_translation_reviews(tmp_path)


def test_real_reviewed_translations_pass_without_changing_original_data():
    reviews = agent.load_chinese_translation_reviews(ROOT)
    count = 0
    for day in ("20261026", "20261028"):
        report = json.loads((ROOT / f"docs/diagnostics/independent-language-{day}-audit.json").read_text(encoding="utf-8"))
        for group in report["offline"]["groups"]:
            for raw in group["english_facts"]:
                fact = agent.BilingualFact(**raw)
                if fact.english_source == "translated_from_chinese":
                    count += 1
                    assert fact.translation_provenance in reviews
                    assert not agent.validate_chinese_translation(fact)
    assert count > 0
