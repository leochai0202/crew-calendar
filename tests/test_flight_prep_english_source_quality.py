from copy import deepcopy
from dataclasses import replace
from datetime import date
import re

import pytest

from crew_agents import flight_prep_agent as agent
from test_flight_prep_independent_languages import flight, record, selected


@pytest.mark.parametrize("source,expected", [
    ("Radar isnot available.", "Radar is not available."),
    ("Airportelevation:13 ft.", "Airport elevation: 13 ft."),
    ("The interval is5nm inBKKTMA.", "The interval is 5nm in BKKTMA."),
    ("Ifthe SID isNOT available, contact ATC.", "If the SID is NOT available, contact ATC."),
    ("Ifboarding is necessary, notify the airport.", "If boarding is necessary, notify the airport."),
    ("At the airport, itwill resume the startcommand.", "At the airport, it will resume the start command."),
    ("Fly toFIXAA and contact ATC at01L.", "Fly to FIXAA and contact ATC at 01L."),
    ("Follow the airchart; maintain airtraffic separation.", "Follow the air chart; maintain air traffic separation."),
    ("If stable-approach criteriacannot be met,execute a missed approach.", "If stable-approach criteria cannot be met, execute a missed approach."),
    ("Proceed toF/W; the lattershall be used.", "Proceed to F/W; the latter shall be used."),
])
def test_evidenced_english_word_boundaries_only_change_whitespace(source, expected):
    result = agent.english_layout_text(source)
    assert result == expected
    assert re.sub(r"\s", "", result) == re.sub(r"\s", "", source)
    assert agent.english_layout_text(result) == result


def test_english_layout_keeps_identifiers_ecam_frequencies_and_operating_data():
    source = ("When cleared by ATC, use RNP13 or ILS Y/Z via PORAP-1N; "
              "FPA3.26 GP3.2, 7200m, 121.950 MHz, 150m, 5.7%, 12:30 UTC. "
              "NAV ADS-B RPTG 1+2 FAULT; NAV BKUP SPD FAULT; GPS PRIMARYLOST. "
              "An island and an airway are not word-boundary errors.")
    assert agent.english_layout_text(source) == source
    assert agent.manual_pairing_tokens(agent.english_layout_text(source)) == agent.manual_pairing_tokens(source)


def test_layout_and_crew_subject_elision_preserve_source_and_instruction_strength():
    source = "When authorized by ATC, the crew must not enter Runway 08.Ifboarding is necessary, notify ATC."
    item = record(source)
    before = deepcopy(item)
    facts = selected([item])[2]
    output = agent.english_fact_output(facts[0])
    assert "it is mandatory not to enter Runway 08" in output
    assert ". If boarding is necessary" in output
    assert facts[0].source_text_en == source and item == before
    assert agent.validate_english_source_facts("AAAA", facts) == []
    for modal in ("should", "must", "shall", "may"):
        raw = f"ATC {modal} issue the clearance."
        assert agent.english_fact_output(replace(facts[0], text_en=raw)) == raw


def test_uncertain_operating_terms_are_not_rewritten_as_layout_corrections():
    source = "Automatic wave separation. RNP five sides. Begin taxiing after takeoff clearance. OLPAB OBLAP."
    assert agent.english_layout_text(source) == source
    facts = selected([record(source)])[2]
    assert agent.validate_english_source_facts("AAAA", facts)


def test_exact_manual_heading_aliases_resolve_routes_without_city_guessing():
    aliases = agent.english_route_aliases([
        {"icao": "AAAA", "iata": "AAA", "name": "Alpha East"},
        {"icao": "CCCC", "iata": "CCC", "name": "Alpha West"},
        {"icao": "BBBB", "iata": "BBB", "name": "Bravo Field"},
        {"icao": "DDDD", "iata": "DDD", "name": "Delta International"},
    ])
    assert "ALPHA" not in aliases and aliases["BRAVO"] == "BBBB"
    assert aliases["AAA"] == "AAAA"
    for text, expected in (
        ("The flight from Alpha East to Bravo will join W19.", (("AAAA", "BBBB"),)),
        ("The Alpha East-Bravo border crossing is FIXAA.", (("AAAA", "BBBB"),)),
        ("From AAA to BBB: maintain the cleared altitude.", (("AAAA", "BBBB"),)),
        ("The flight from Alpha to Bravo will join W19.", ()),
        ("On a flight from Alpha East to Bravo, a bird strike occurred.", ()),
    ):
        assert agent.english_source_route_scope(record(text), aliases) == expected
    assert agent.english_source_route_scope(record("The flight from Alpha East to Bravo will join W19.", category="typical"), aliases) == ()
    other = record("The flight from Alpha East to Delta will join W19.")
    other["route_scope"] = agent.english_source_route_scope(other, aliases)
    assert not selected([other])[2]
    forward = record("The flight from Alpha East to Bravo will join W19.")
    forward["route_scope"] = agent.english_source_route_scope(forward, aliases)
    assert selected([forward])[2]
    assert not selected([forward], replace(flight(), summary="9C0002 BBBB→AAAA"))[2]


def test_ground_vehicle_approach_is_not_aircraft_arrival_applicability():
    text = "When the lead vehicle approaches, control speed and follow its guidance."
    item = record(text, phase="ground")
    assert agent.english_source_role_scope(text, "ground") == ("departure", "arrival")
    assert selected([item])[2]
    assert selected([item], replace(flight(), summary="9C0002 BBBB→AAAA"))[2]
    assert agent.english_source_role_scope("After landing, follow the taxi route.", "ground") == ("arrival",)
    assert agent.english_source_role_scope("Before takeoff, check the SID.", "ground") == ("departure",)


@pytest.mark.parametrize("text,target,expected", [
    ("Effective from 1 NOV 2026, Runway 08 is unavailable.", date(2026, 10, 26), False),
    ("Effective from 1 NOV 2026, Runway 08 is unavailable.", date(2026, 11, 1), True),
    ("Taxiway A is closed from 25 OCT 2026 through 23 DEC 2026.", date(2026, 10, 26), True),
    ("Taxiway A is closed from 25 OCT 2026 through 23 DEC 2026.", date(2026, 12, 24), False),
    ("Taxiway A is closed until 2026-10-26.", date(2026, 10, 26), True),
    ("Taxiway A is closed until 2026-10-26.", date(2026, 10, 27), False),
    ("Taxiway A is closed from 25 October to 23 December.", date(2026, 10, 26), True),
    ("A runway event occurred on 1 JAN 2020.", date(2026, 10, 26), True),
])
def test_explicit_operating_date_windows_not_history_or_guessed_years(text, target, expected):
    assert agent.english_source_date_matches(text, target) == expected


def test_all_applicable_english_records_survive_without_summary_or_count_cap():
    records = [record(f"When cleared, maintain {3000 + number}ft.", identity=f"en:{number}") for number in range(130)]
    records += [record("Maintain 3000-5000ft when cleared.", identity="range"),
                record("Maintain 30005000ft when cleared.", identity="different-source-number")]
    facts = selected(records)[2]
    assert len(facts) == len(records)
    assert {fact.fact_id for fact in facts} == {item["fact_id"] for item in records}
    assert all(agent.validate_english_source_facts("AAAA", [fact]) == [] for fact in facts)


def test_source_chinese_typical_events_are_not_limited_by_legacy_max_items():
    records = [{"airport": "AAAA", "category": "typical", "source_verbatim": True,
        "text_zh": f"曾在08号跑道发生鸟击事件，造成损伤{number}处。", "source": "PDF",
        "source_file": "knowledge/pdf/fixture.pdf", "source_page": "10", "source_version": "test",
        "source_heading": "AAAA机场", "source_section": "典型不安全事件",
        "source_record_id": f"zh:{number}", "operational_phase": "incident"} for number in range(3)]
    facts = agent.bilingual_typical_facts("AAAA", [], [], 10, 1, records, flight(), date(2026, 10, 26))
    assert len(facts) == 3
