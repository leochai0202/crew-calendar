"""Source-conflict regressions, not approval to rewrite the printed manual."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from crew_agents import flight_prep_agent as agent


ROOT = Path(__file__).resolve().parents[1]


def conflict(zh: str, en: str) -> list[str]:
    english = agent.BilingualFact(
        "en:source", "", en, airport="测试机场", category="core", language="en",
        english_source_record_id="en:source", source_page="20",
    )
    chinese = agent.BilingualFact(
        "zh:source", zh, en, airport="测试机场", category="core",
        english_source_record_id="en:source", source_page="10", english_source_page="20",
    )
    return agent.validate_cross_language_conflicts([chinese], [english])


@pytest.mark.parametrize("en,blocked", [
    ("TCAS should remain activated until receiving runway-entry clearance.", True),
    ("TCAS should only be activated after receiving runway-entry clearance.", False),
])
def test_activation_until_is_not_activation_only_after(en: str, blocked: bool) -> None:
    errors = conflict("直到收到进入跑道指令才打开TCAS。", en)
    assert any("system_activation_temporal_polarity" in error for error in errors) == blocked


@pytest.mark.parametrize("action,blocked", [
    ("begin taxiing", True), ("commence the takeoff roll", False),
])
def test_takeoff_clearance_does_not_make_taxiing_a_takeoff_roll(action: str, blocked: bool) -> None:
    errors = conflict("收到起飞许可后立即开始起飞滑跑。",
                      f"Pilots must {action} immediately upon receiving takeoff clearance.")
    assert any("takeoff_roll" in error for error in errors) == blocked


@pytest.mark.parametrize("unit,blocked", [("knots", True), ("nautical miles", False)])
def test_speed_and_distance_cannot_be_interchanged(unit: str, blocked: bool) -> None:
    errors = conflict("速度180保持到8海里。", f"Maintain a speed of 180 to 8 {unit}.")
    assert any("operating_quantity_or_unit_conflict" in error for error in errors) == blocked


@pytest.mark.parametrize("waypoint,blocked", [("OLPAB", False), ("OBLAP", True)])
def test_waypoint_spelling_is_not_inferred_from_other_anchors(waypoint: str, blocked: bool) -> None:
    errors = conflict("沿W19经MASGU、ATKAV、OLPAB和NOMAR。",
                      f"Follow W19 via MASGU, ATKAV, {waypoint} and NOMAR.")
    assert any("procedure_or_waypoint_conflict" in error for error in errors) == blocked


@pytest.mark.parametrize("change", ["none", "swapped", "duplicate_label", "wrong_unit"])
def test_papi_associations_require_more_than_matching_number_sets(change: str) -> None:
    zh = "PAPI信息：08：入口内452米，3°，MEHT21.4m；26：入口内452米，3°，MEHT21.0m。"
    en = "PAPI Information: RWY 08: 452m, 3°, MEHT21.4m; RWY 26: 452m, 3°, MEHT21.0m."
    if change == "swapped":
        en = en.replace("RWY 08:", "RWY 26:").replace("RWY 26: 452m, 3°, MEHT21.0m", "RWY 08: 452m, 3°, MEHT21.0m")
    elif change == "duplicate_label":
        en = en.replace("RWY 08:", "RWY 08: 26:")
    elif change == "wrong_unit":
        en = en.replace("452m", "452ft", 1)
    assert bool(agent.bilingual_keyed_table_mismatches(zh, en)) == (change != "none")


@pytest.mark.parametrize("target", ["20261026", "20261028"])
def test_real_source_blockers_remain_blocking_and_last_good_is_preserved(target: str) -> None:
    report = json.loads((ROOT / "docs/diagnostics" / f"independent-language-{target}-audit.json").read_text(encoding="utf-8"))
    records = {airport: result["source_records"] for airport, result in report["airports"].items()}
    reproduced = []
    for group in report["offline"]["groups"]:
        zh = [agent.BilingualFact(**fact) for fact in group["facts"]]
        en = [agent.BilingualFact(**fact) for fact in group["english_facts"]]
        prefix = "/".join(group["flights"])
        reproduced.extend(prefix + "：" + error for error in agent.validate_cross_language_conflicts(zh, en, records))
        for airport in group["routes"][0]:
            reproduced.extend(prefix + "英文版：" + error
                              for error in agent.validate_english_source_facts(airport, [fact for fact in en if fact.airport == airport]))
    assert reproduced == report["offline"]["errors"]
    assert len(reproduced) == 8  # real-date regression only, not production selection logic
    assert report["offline"]["status"] == "FAILED_SAFE"
    assert not report["offline"]["success_marker"]
    assert report["offline"]["last_good_preserved_on_failure"]
    assert report["offline"]["generated_files"] == []


@pytest.mark.parametrize("identity,printed_phrase", [
    ("曼谷素旺那普:en:762728438175820a", "five-way turns"),
    ("曼谷素旺那普:en:b6c12b97473d3ea3", "RNP five sides"),
    ("曼谷素旺那普:en:730e7517374f441e", "Automatic wave separation"),
    ("广州白云:en:86382f3678c87672", "disengages from the wave contact"),
])
def test_unreliable_printed_english_is_not_silently_rewritten(identity: str, printed_phrase: str) -> None:
    facts = []
    for target in ("20261026", "20261028"):
        report = json.loads((ROOT / "docs/diagnostics" / f"independent-language-{target}-audit.json").read_text(encoding="utf-8"))
        facts.extend(fact for group in report["offline"]["groups"] for fact in group["english_facts"])
    fact = agent.BilingualFact(**next(fact for fact in facts if fact["fact_id"] == identity))
    original = fact.en
    rendered = agent.english_fact_output(fact)
    assert fact.en == original and fact.source_text_en == original
    assert "".join(agent.english_layout_text(original).split()) == "".join(original.split())
    assert printed_phrase.casefold() in rendered.casefold()
    assert any("英文关键运行表达无法可靠确认" in error
               for error in agent.validate_english_source_facts(fact.airport, [fact]))
    assert agent.validate_english_source_facts(fact.airport, [replace(fact, text_en=rendered)])
