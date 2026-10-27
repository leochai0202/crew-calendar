from dataclasses import asdict, replace
from datetime import date, datetime
import json
import sys

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent
from test_flight_prep_foreign_crew import _event, _prepare_stub_repo, _stub_airport_risks


def flight():
    return CalendarEvent(uid="test", summary="9C0001 AAAA→BBBB", start=datetime(2026, 10, 26, 12),
        end=datetime(2026, 10, 26, 14), description="", location="", properties={})


def record(text, *, airport="AAAA", category="core", phase="operations", identity="en:one"):
    return {"language": "en", "airport": airport, "fact_id": identity, "category": category,
        "operational_phase": phase, "text_en": text, "source_original_text_en": text,
        "source_file": "knowledge/pdf/fixture.pdf", "source_page": "20", "source_version": "20990101",
        "source_heading": airport + " / English", "source_section": "core / operations",
        "source_sequence": 1, "english_airport_name": "Test"}


def selected(records, event=None):
    return agent.english_briefing_fact_sets(event or flight(), date(2026, 10, 26), {"AAAA": records, "BBBB": []})


def test_english_has_its_own_ids_counts_order_and_source_not_chinese_pairing():
    records = [record("Maintain 3000ft when cleared by ATC.", identity="en:alt"),
               record("Runway 08 has an uphill gradient.", identity="en:runway"),
               record("A taxiway collision occurred.", category="typical", phase="incident", identity="en:event")]
    before = [dict(value) for value in records]
    typical, core, english = selected(records)
    chinese = [agent.BilingualFact("zh:unrelated", "机场地形较高。", "", airport="AAAA", category="core",
        english_source="manual_coverage_gap")]
    assert [f.fact_id for f in core["AAAA"]] == ["en:alt", "en:runway"]
    assert len(typical["AAAA"]) == 1 and all(f.language == "en" and not f.zh for f in english)
    assert agent.validate_english_source_facts("AAAA", english) == []
    assert agent.validate_cross_language_conflicts(chinese, english) == []
    assert agent.validate_bilingual_facts(chinese)  # diagnostics retained, not a publication gate
    assert records == before
    assert all(f.source_page == "20" and f.source_text_en for f in english)


def test_english_filters_roles_route_season_expiry_and_keeps_unknown_runway_conditions():
    records = [record("For Runway 08 departure, maintain 3000ft.", phase="departure", identity="dep"),
        record("STAR arrivals require advance planning.", phase="arrival", identity="arr"),
        record("From CCCC to DDDD: maintain 5000ft.", phase="navigation", identity="other-route"),
        record("Winter: obtain deicing clearance before taxi.", identity="winter"),
        record("Runway 26 is closed until 1 JAN 2026.", identity="expired"),
        record("The jet bridge password is 1234.", identity="admin"),
        record("At night, monitor runway lights.", identity="night"),
        record("160KT", identity="fragment")]
    exclusions = []
    _, core, _ = agent.english_briefing_fact_sets(flight(), date(2026, 10, 26), {"AAAA": records, "BBBB": []}, exclusions)
    assert [f.fact_id for f in core["AAAA"]] == ["dep"]
    assert "For Runway 08" in core["AAAA"][0].en  # no guessed actual runway
    reverse = replace(flight(), summary="9C0002 BBBB→AAAA")
    assert [f.fact_id for f in selected(records, reverse)[1]["AAAA"]] == ["arr"]
    assert len(exclusions) == 7


def test_english_own_source_guard_detects_data_conditions_and_invented_text():
    fact = selected([record("When cleared by ATC, maintain 3000ft.")])[2][0]
    for text in ("Maintain 3000ft.", "When cleared by ATC, maintain 3500ft.", fact.en + " Use an unpublished SID."):
        assert agent.validate_english_source_facts("AAAA", [replace(fact, text_en=text)])
    assert agent.validate_english_source_facts("AAAA", [replace(fact, english_source="concept_fallback")])
    assert not agent.validate_english_source_facts("AAAA", [fact])
    interval = selected([record("Maintain 3000-5000ft when cleared.")])[2][0]
    assert agent.validate_english_source_facts("AAAA", [replace(interval, text_en=interval.en.replace("-", ""))])
    assert agent.validate_english_source_facts("AAAA", [replace(fact, source="CURATED")])
    assert agent.validate_english_source_facts("AAAA", [replace(fact, source_page="N/A")])


@pytest.mark.parametrize("zh,en", [
    ("直到收到进入跑道指令才打开TCAS。", "TCAS should remain activated until receiving runway clearance."),
    ("收到起飞许可后立即开始起飞滑跑。", "Begin taxiing immediately after receiving takeoff clearance."),
    ("沿W19经ALPHA、OLPAB和NOMAR。", "Follow W19 via ALPHA, OBLAP and NOMAR."),
    ("ATC要求保持3000ft。", "ATC requires maintaining altitude 3500ft."),
    ("ATC要求保持FL200。", "ATC requires maintaining FL220."),
    ("速度180保持到8海里。", "Maintain a speed of 180 to 8 knots."),
])
def test_explicit_source_conflicts_still_block_even_with_independent_ids(zh, en):
    english = selected([record(en)])[2]
    chinese = [agent.BilingualFact("zh:one", zh, en, airport="AAAA", category="core",
        english_source_record_id=english[0].english_source_record_id, manual_english_counterpart=True,
        source_page="10", english_source_page="20")]
    assert agent.validate_cross_language_conflicts(chinese, english)


def test_known_action_conflict_is_not_hidden_by_missing_pairing():
    english = selected([record("Begin taxiing immediately upon receiving takeoff clearance.")])[2]
    zh = agent.BilingualFact("zh:one", "收到起飞许可后立即开始起飞滑跑。", "", airport="AAAA", category="core")
    assert agent.validate_cross_language_conflicts([zh], english)


def test_named_procedure_suffix_conflict_survives_missing_ordinal_pairing():
    en = selected([record("Runway 08 arrival uses FIXAA 2M procedure.", phase="arrival")],
                  replace(flight(), summary="9C0002 BBBB→AAAA"))[2]
    zh = agent.BilingualFact("zh:one", "08号跑道进场使用FIXAA 2F程序。", "", airport="AAAA", category="core")
    assert any("named_procedure_designator" in error for error in agent.validate_cross_language_conflicts([zh], en))
    assert agent.validate_cross_language_conflicts([replace(zh, text_zh=zh.zh.replace("2F", "2M"))], en) == []


def test_source_conflict_is_not_hidden_by_one_languages_role_selection():
    text = "TCAS should remain activated until receiving runway clearance."
    source = record(text, phase="arrival")
    source["source_record_id"] = source["fact_id"]
    assert not selected([source])[2]
    chinese = [agent.BilingualFact("zh:tcas", "直到收到进入跑道指令才打开TCAS。", "", airport="AAAA", category="core")]
    assert agent.validate_cross_language_conflicts(chinese, [], {"AAAA": [source]})


def test_extra_sourced_information_and_missing_effective_date_are_not_contradictions():
    en = selected([record("PBN single-engine departure procedures for Runways 01L/R and 02L/R are applicable.")])[2][0]
    zh = agent.BilingualFact("zh:one", "已开始执行单发程序，请注意。", en.en,
        airport="AAAA", category="core", english_source_record_id=en.fact_id)
    assert agent.validate_cross_language_conflicts([zh], [en]) == []


def test_season_projection_keeps_complete_english_sentences_and_source():
    text = "Spring thunderstorms bring wind shear. Summer and autumn typhoons bring heavy rain."
    _, core, _ = selected([record(text)])
    assert core["AAAA"][0].en == "Summer and autumn typhoons bring heavy rain."
    assert core["AAAA"][0].source_text_en == text
    assert agent.validate_english_source_facts("AAAA", core["AAAA"]) == []
    assert agent.english_season_scope("From November to February, icing may occur.") == (1, 2, 11, 12)
    assert agent.english_season_scope("During July, thunderstorms are frequent.") == (7,)
    assert agent.english_season_scope("Crews may use the cleared route.") == ()
    assert agent.filter_english_source_seasons("From May to September, thunderstorms are frequent.", 10)[0] == ""


def test_named_endpoint_is_not_guessed_as_a_four_letter_icao():
    assert agent.english_source_route_scope(record("From Rome to Oslo: maintain terrain clearance.")) == ()
    assert agent.english_source_route_scope(record("CCCC-DDDD: maintain terrain clearance.", phase="navigation"))
    assert not selected([record("For CCCC-DDDD, update the cleared route.", phase="navigation")])[2]
    assert selected([record("For AAAA-BBBB, update the cleared route.", phase="navigation")])[2]
    assert not selected([record("For BBBB-AAAA, update the cleared route.", phase="navigation")])[2]


def test_staff_administration_and_frequency_fragments_are_not_operational_facts():
    for text in (
        "Crew members must sign the meal order form for breakfast and dinner.",
        "The terminal staff will advise the aircraft parking position and customs clearance checkpoint. The crew list is available there.",
        "For the return trip, wait at the drop-off point.",
        "Upon arrival, turn at the VATREFUND sign and proceed to security screening.",
        "When you go downstairs, take the subway to the satellite terminal.",
        "You have reached the SAT-9 building and cannot return to the main building.",
        "Departure is on the third floor. There are two customs offices. An alternate airport map for an emergency landing is shown below.",
        "Ground/Apron and dispatch frequencies: Field frequency 130.5 MHz or.",
        "MHz; Airline dispatch frequency 130.5 MHz.",
    ):
        assert agent.source_operational_value_issue(text), text
        assert agent.filter_source_administrative_sentences(text, english=True) == "", text
        assert not selected([record(text)])[2]
    for text in (
        "During refueling, boarding is prohibited unless fire truck cover is provided.",
        "Contact ground on 121.9 MHz before entering the taxiway.",
        "If radio contact is lost, follow the communication failure procedure.",
    ):
        assert not agent.source_operational_value_issue(text)
        assert selected([record(text)])[2]


def test_papi_source_field_is_arrival_only_without_changing_its_runway_values():
    text = "PAPI Information: Runway 08, 3 degrees, MEHT 15m."
    assert not selected([record(text)])[2]
    arrival = replace(flight(), summary="9C0002 BBBB→AAAA")
    assert selected([record(text)], arrival)[2][0].en == text


def test_runway_dimensions_remain_applicable_to_departure_when_field_also_lists_approaches():
    text = "Runway Information: RWY 08/26 is 3000m long. ILS approaches are available."
    _, core, _ = selected([record(text)])
    assert core["AAAA"][0].en == text


def test_unit_spellings_and_thousands_grouping_are_not_source_conflicts():
    english = selected([record("ATC requires maintaining 3,000 feet.")])[2][0]
    chinese = agent.BilingualFact("zh:one", "ATC要求保持3000英尺。", english.en, airport="AAAA",
        category="core", english_source_record_id=english.fact_id)
    assert agent.validate_cross_language_conflicts([chinese], [english]) == []


@pytest.mark.parametrize("foreign,missing_english,critical_conflict", [(False, True, False), (True, False, False), (True, True, False), (True, False, True)])
def test_main_independent_publication_and_failure_rollback(monkeypatch, tmp_path, foreign, missing_english, critical_conflict):
    people = ["段洋硕", "TEST FOREIGN PILOT(R)"] if foreign else ["段洋硕", "测试机长(R)"]
    event = _event(uid="test", number="9C0001", departure="甲地机场", arrival="乙地机场", people=people)
    _prepare_stub_repo(tmp_path, [event])
    output = tmp_path / "flight_preparation"
    output.mkdir()
    protected = ["2026-07-23_航前准备.txt", "2026-07-23_航前准备_EN.txt", "latest.txt", "latest_en.txt"]
    for filename in protected:
        (output / filename).write_text("LAST_GOOD", encoding="utf-8")

    def sources(repo, airports, mapping, max_items):
        risks, threats, records, *tail = _stub_airport_risks(repo, airports, mapping, max_items)
        for airport in airports:
            if missing_english:
                records[airport] = [r for r in records[airport] if r.get("language") != "en"]
            for item in records[airport]:
                if item.get("language") != "en":
                    item.update(text_en="", source_verbatim=True, source_version="test")
                if critical_conflict and item["category"] == "core":
                    if item.get("language") == "en":
                        text = "TCAS should remain activated until receiving runway clearance."
                        item.update(text_en=text, source_original_text_en=text)
                    else:
                        item["text_zh"] = "直到收到进入跑道指令才打开TCAS。"
        return risks, threats, records, *tail

    monkeypatch.setattr(agent, "airport_risks", sources)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(sys, "argv", ["flight_prep_agent.py", "--repo", str(tmp_path), "--target-date", "2026-07-23"])
    result = agent.main()
    failed = foreign and (missing_english or critical_conflict)
    assert result == (2 if failed else 0)
    meta = json.loads((output / "2026-07-23_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == ("FAILED_SAFE" if failed else "SUCCESS")
    assert (output / ".success").exists() != failed
    if failed:
        assert all((output / name).read_text(encoding="utf-8") == "LAST_GOOD" for name in protected)
    elif foreign:
        assert "Core threats:" in (output / "latest_en.txt").read_text(encoding="utf-8")
        detailed = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))
        assert detailed["prep_groups"][0]["language_fact_sets_independent"]
        assert detailed["prep_groups"][0]["bilingual_pairing_diagnostics"]


@pytest.mark.parametrize("numbers,expected_groups", [(("9C7605", "9C7606"), 1), (("9C7289", "9C7420"), 2)])
def test_independent_versions_preserve_flight_number_groups_and_complete_files(monkeypatch, tmp_path, numbers, expected_groups):
    people = ["段洋硕", "TEST FOREIGN PILOT(R)"]
    events = [_event(uid="a", number=numbers[0], departure="甲地机场", arrival="乙地机场", people=people),
              _event(uid="b", number=numbers[1], departure="乙地机场", arrival="甲地机场", people=people)]
    _prepare_stub_repo(tmp_path, events)
    monkeypatch.setattr(agent, "airport_risks", _stub_airport_risks)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(sys, "argv", ["flight_prep_agent.py", "--repo", str(tmp_path), "--target-date", "2026-07-23"])
    assert agent.main() == 0
    output = tmp_path / "flight_preparation"
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))
    assert len(meta["prep_groups"]) == expected_groups
    for group in meta["prep_groups"]:
        assert group["english_generated"] and group["language_fact_sets_independent"]
        assert (output / group["output"]).is_file() and (output / group["english_output"]).is_file()
        assert group["airport_fact_ids"] != group["english_fact_ids"]
    assert (output / ".success").is_file()
