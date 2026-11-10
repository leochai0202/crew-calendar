"""Approvals are source- and duty-bound; pending evidence cannot authorize release."""
from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.flight_prep_preview import source_review_queue
from test_flight_prep_chinese_primary_english import sources
from test_flight_prep_independent_languages import flight
from test_flight_prep_preview import group


def scoped_sources():
    records, chinese, review = sources()
    review["review_scope"] = dict(effective_from="2026-10-01", effective_until_exclusive="2026-12-01",
                                  roles=["departure"], routes=[["AAAA", "BBBB"]], runways=[])
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [review])
    return records, chinese, review


@pytest.mark.parametrize("day,valid", [("2026-10-26", True), ("2026-11-13", True),
    ("2026-11-14", True), ("2026-09-30", False), ("2026-12-01", False)])
def test_new_duty_reuses_only_current_approval(day, valid):
    records, chinese, _ = scoped_sources()
    facts = agent.english_briefing_fact_sets(flight(), date.fromisoformat(day), records, chinese_facts=[chinese])[2]
    assert len(facts) == 1
    assert (facts[0].english_source == "translated_from_chinese") == valid
    assert bool(agent.validate_english_source_facts("AAAA", facts)) != valid
    if not valid:
        assert facts[0].source_text_en == facts[0].en  # retain, never drop, unapproved source
        assert "REVIEW_OUTSIDE_VALIDITY" in facts[0].english_source_note


@pytest.mark.parametrize("change", ["version", "original", "withdrawn"])
def test_rebinding_cannot_reuse_stale_in_memory_approval(change):
    records, chinese, review = scoped_sources()
    assert records["AAAA"][1].get("chinese_translation_review")
    if change == "version":
        records["AAAA"][1]["source_version"] = "new-manual"
    elif change == "original":
        records["AAAA"][1]["source_original_text_en"] += " Changed."
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [] if change == "withdrawn" else [review])
    assert "chinese_translation_review" not in records["AAAA"][1]


@pytest.mark.parametrize("key,value,reason", [
    ("roles", ["arrival"], "ROLE"), ("routes", [["BBBB", "AAAA"]], "ROUTE"),
    ("runways", ["08"], "RUNWAY")])
def test_scope_mismatch_keeps_fact_and_blocks_instead_of_removing_it(key, value, reason):
    records, chinese, review = scoped_sources()
    review["review_scope"][key] = value
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [review])
    facts = agent.english_briefing_fact_sets(flight(), date(2026, 11, 14), records, chinese_facts=[chinese])[2]
    assert len(facts) == 1 and facts[0].english_source == "unavailable"
    assert reason in facts[0].english_source_note
    assert agent.validate_english_source_facts("AAAA", facts)


def test_scope_cannot_assert_unknown_runway_or_override_operating_numbers():
    _, chinese, review = scoped_sources()
    review["review_scope"]["runways"] = ["08"]
    review["source_text_zh"] = "08号跑道收到许可后起飞。"
    assert not agent.translation_review_unavailable_reason(review, chinese, flight(), date(2026, 11, 14))
    review["review_scope"]["runways"] = ["26"]
    assert agent.translation_review_unavailable_reason(review, chinese, flight(), date(2026, 11, 14)) == "REVIEW_RUNWAY_NOT_COVERED"
    records, chinese, review = sources("保持3000ft。", "Maintain 3500ft.", "Maintain 3000ft.")
    review["review_scope"] = dict(effective_from="2026-10-01", effective_until_exclusive="2026-12-01",
                                 roles=["departure", "arrival"], routes=[], runways=[])
    agent.bind_chinese_translation_reviews(records["AAAA"], "AAAA", [review])
    facts = agent.english_briefing_fact_sets(flight(), date(2026, 11, 14), records, chinese_facts=[chinese])[2]
    assert agent.validate_chinese_translation(facts[0])


@pytest.mark.parametrize("key,value", [("roles", []), ("routes", [["AAAA", "AAAA"]]),
    ("runways", ["99"]), ("effective_until_exclusive", "2026-01-01")])
def test_invalid_approval_scope_fails_closed(key, value):
    _, _, review = scoped_sources()
    review["review_scope"][key] = value
    with pytest.raises(ValueError):
        agent.validate_translation_review_scope(review)


def test_pending_conflict_key_is_stable_across_groups_and_dates_but_not_source_changes():
    data, errors = group()
    issue = dict(data["conflict_evidence"][0], group=1)
    first = source_review_queue([], [issue], "20261019")
    repeated = source_review_queue([], [issue, {**issue, "group": 2}], "20261019")
    assert len(repeated) == 1 and repeated[0]["groups"] == [1, 2]
    assert first[0]["review_id"] == repeated[0]["review_id"]
    assert first[0]["review_id"] != source_review_queue([], [issue], "20261119")[0]["review_id"]
    assert first[0]["review_id"] != source_review_queue([], [{**issue, "chinese_original": "changed"}], "20261019")[0]["review_id"]
    assert first[0]["status"] == "PENDING_AUTHORITY_REVIEW" and errors


def test_missing_english_generates_review_task_not_fabricated_content():
    data, _ = group()
    data.update(group_index=1, english_fact_sources={})
    before = deepcopy(data)
    queue = source_review_queue([data], [], "20261019")
    assert len(queue) == 1 and queue[0]["issue_type"] == "MISSING_RELIABLE_ENGLISH"
    assert queue[0]["icao"] == "AAAA" and data == before
    changed = deepcopy(data)
    changed["airport_fact_sources"]["AAAA"][0]["source_text_zh"] = "Other applicable source"
    assert source_review_queue([changed], [], "20261019")[0]["review_id"] == queue[0]["review_id"]
