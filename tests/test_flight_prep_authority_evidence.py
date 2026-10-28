"""Dated authority corroboration cannot bypass source/data/ATC-condition guards."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import json

import pytest

from crew_agents import flight_prep_agent as agent
from test_flight_prep_chinese_primary_english import ROOT, sources, translate
from test_flight_prep_independent_languages import flight


def authority_sources():
    records, chinese, review = sources(
        "离地后联系管制119.25。", "Automatic wave separation 119.25.",
        "Immediately after take-off, contact Departure on 119.25 MHz before transfer, unless ATC instructs otherwise.")
    review["authority_evidence"] = dict(
        source_type="state_aip", publisher="TEST_AUTHORITY", document="Test AIRAC", icao="AAAA",
        section="AAAA AD 2.22 section 6.1", url="https://authority.example/aip/AAAA",
        effective_from="2026-10-01", effective_until_exclusive="2026-10-29", verified_on="2026-10-28",
        summary_zh="离地后立即联系Departure，频率119.25MHz；移交之前完成，ATC另有指令时除外。",
        supported_text_hash=agent.source_text_hash(review["text_en"]))
    records["AAAA"][1]["chinese_translation_review"] = review
    return records, chinese, review


@pytest.mark.parametrize("day,active", [("2026-09-30", False), ("2026-10-01", True),
    ("2026-10-26", True), ("2026-10-28", True), ("2026-10-29", False)])
def test_authority_window_uses_task_date_and_is_bounded(day, active):
    records, chinese, review = authority_sources()
    facts = agent.english_briefing_fact_sets(flight(), date.fromisoformat(day), records, chinese_facts=[chinese])[2]
    assert (facts[0].english_source == "translated_from_chinese") == active
    assert bool(agent.validate_english_source_facts("AAAA", facts)) != active
    if active:
        assert facts[0].source_text_zh == review["source_text_zh"]
        assert agent.fact_source_metadata(facts[0])["translation_provenance"]["authority_evidence"] == review["authority_evidence"]


@pytest.mark.parametrize("key,value", [
    ("icao", "BBBB"), ("url", "http://authority.example/aip/AAAA"),
    ("section", ""), ("publisher", ""), ("source_type", "blog"),
    ("effective_until_exclusive", "2026-09-01"), ("supported_text_hash", "0" * 64),
])
def test_authority_requires_complete_reviewed_identity_and_body(key, value):
    _, _, review = authority_sources()
    review["authority_evidence"][key] = value
    with pytest.raises(ValueError):
        agent.translation_authority_source(review)


@pytest.mark.parametrize("change", ["frequency", "exception", "before_transfer", "auto_tuning"])
def test_authority_correction_preserves_frequency_atc_exception_and_action(change):
    records, chinese, review = authority_sources()
    fact = translate(records, chinese)[0]
    changed = fact.en
    if change == "frequency":
        changed = changed.replace("119.25", "119.2")
    elif change == "exception":
        changed = changed.replace(", unless ATC instructs otherwise", "")
    elif change == "before_transfer":
        changed = changed.replace("before transfer", "after transfer")
    else:
        changed = "The aircraft automatically tunes the Departure frequency 119.25 MHz."
    assert agent.validate_chinese_translation(replace(fact, text_en=changed))
    # Even editing the review text alone cannot change the authority-supported body.
    forged = deepcopy(review)
    forged["text_en"] = changed
    assert agent.validate_chinese_translation(replace(fact, text_en=changed, translation_provenance=forged))


def test_real_caat_correction_matches_current_company_originals_and_section():
    reviews = agent.load_chinese_translation_reviews(ROOT)
    review = next(r for r in reviews if r.get("authority_evidence", {}).get("publisher") == "CAAT")
    assert review["source_text_zh"] == "离场：离地自动脱波119.25。"
    assert review["original_text_en"] == "Automatic wave separation from the ground 119.25."
    assert review["authority_evidence"]["section"] == "VTBS AD 2.22 section 6.1"
    assert "119.25 MHz" in review["text_en"] and "unless" in review["text_en"] and "ATC" in review["text_en"]
    assert "automati" not in review["text_en"].lower()
    count = 0
    for day in ("20261026", "20261028"):
        report = json.loads((ROOT / f"docs/diagnostics/independent-language-{day}-audit.json").read_text(encoding="utf-8"))
        for group in report["offline"]["groups"]:
            for raw in group["english_facts"]:
                if raw["fact_id"] == review["english_source_record_id"]:
                    count += 1
                    fact = agent.BilingualFact(**raw)
                    assert fact.en == review["text_en"]
                    assert fact.translation_provenance == review
                    assert not agent.validate_chinese_translation(fact)
    assert count == 2
