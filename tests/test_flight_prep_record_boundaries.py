from crew_agents import flight_prep_agent as agent


def test_joined_airport_title_and_next_line_codes_bound_the_previous_chapter():
    text = """页码：100
Alpha Airport (AAAA/AAA)
Updated on 2026.10.19
VI. Departure Procedures
1. Depart via FIXAA.
页码：104
BetaFieldAirport
(BBBB/BBB)
Responsible
Squadron
4th Squadron
1. Overview
(2) ICAO / IATA Identifier: BBBB / BBB
2. Departure Phase
1. Depart via FIXBB.
页码：108
Gamma Airport (CCC/CCCC)
Updated on 2026.10.19
I. Core Threats
1. Terrain is high.
"""
    chapters = agent.build_english_manual_index(text)
    assert [(c["icao"], c["start_page"], c["end_page"]) for c in chapters] == [
        ("AAAA", 100, 103), ("BBBB", 104, 107), ("CCCC", 108, 108),
    ]
    assert agent.match_english_manual_chapter(chapters, "BBBB")["start_page"] == 104


def test_departure_and_miscellaneous_headings_end_a_conditional_taxi_parent():
    facts = agent.extract_english_manual_facts("""II. Core Threats
Departure Taxi (RWY 08):
Taxi via T1; hold short of T2.
VI. Departure Procedures
      RWY 08 departure: ALPHA 2A.
      ATC will request the estimate for FIXAA.
VII. Miscellaneous
      No communication failure procedure is published.
""")
    assert len(facts) == 4
    assert facts[0].phase == "departure" and "ALPHA" not in facts[0].text
    assert facts[1].phase == "departure" and "ALPHA 2A" in facts[1].text
    assert facts[-1].phase == "operations"
    assert "FIXAA" not in facts[-1].text


def test_enumeration_comma_before_runway_or_altitude_is_not_a_decimal():
    _, facts = agent.scan_chapter_source_records([
        "六.离场", "1、08号跑道使用ALPHA离场。", "2、26号跑道保持3000ft。",
        "七、离场后滑行", "1、沿T1滑行，在T2前等待。",
    ])
    assert facts == ["离场：08号跑道使用ALPHA离场。", "离场：26号跑道保持3000ft。", "离场：沿T1滑行，在T2前等待。"]
    assert agent.strip_manual_ordinal_prefix("1、08号跑道") == "08号跑道"
    assert agent.strip_manual_ordinal_prefix("2、3000ft限制") == "3000ft限制"
    assert agent.strip_manual_ordinal_prefix("0.59%跑道坡度") == "0.59%跑道坡度"
    assert agent.strip_manual_ordinal_prefix("3.2度下滑角") == "3.2度下滑角"


def test_adjacent_source_paragraphs_can_form_one_complete_counterpart():
    zh = "运行特点：未载通信失效程序，搜索救援按ICAO文件。管制经常不纠错，需证实。呼号会用TST代替AirAlpha。"
    texts = [
        "No communication failure procedure is published; SAR follows ICAO documents.",
        "Controllers often omit corrections; crews must verify clearances.",
        'Winter Airlines callsign may use “TST” in lieu of “AIR ALPHA”.',
    ]
    english = [agent.ManualEnglishFact(text, "core", "operations", i) for i, text in enumerate(texts)]
    paired = agent.pair_manual_english_items([zh], english, "core")
    assert paired == [" ".join(texts)]
    assert agent.english_source_parents(paired[0], english) == tuple(texts)
    fact = agent.verbatim_manual_fact("甲机场", {
        "text_zh": zh, "text_en": paired[0], "category": "core", "source_record_id": "original:one",
        "source_original_text_en": paired[0], "english_source_parent_texts": tuple(texts),
    }, 1)
    assert len(fact.english_source_record_id.split("|")) == 3
    assert fact.source_text_en == paired[0]
    assert agent.validate_bilingual_facts([fact]) == []
    assert agent.validate_selected_fact_id_parity([fact]) == []


def test_bundle_cannot_cross_phase_borrow_a_parent_or_add_an_unrelated_fact():
    zh = "运行特点：ATC可改SID，RNP程序以航图为准。"
    first = agent.ManualEnglishFact("ATC may amend the SID.", "core", "operations", 0)
    second = agent.ManualEnglishFact("Use the chart for RNP procedures.", "core", "operations", 1)
    assert agent.bundle_adjacent_english_records([zh], [first, second], "core", [""]) == [first.text + " " + second.text]
    assert agent.bundle_adjacent_english_records([zh, zh], [first, second], "core", ["", ""]).count("") == 1
    wrong_phase = agent.ManualEnglishFact(second.text, "core", "arrival", 1)
    assert agent.bundle_adjacent_english_records([zh], [first, wrong_phase], "core", [""]) == [""]
    extra = agent.ManualEnglishFact("Maintain FL200.", "core", "operations", 1)
    last = agent.ManualEnglishFact(second.text, "core", "operations", 2)
    assert agent.bundle_adjacent_english_records([zh], [first, extra, last], "core", [""]) == [""]
    condition = agent.ManualEnglishFact("When using Runway 08, use the chart for RNP procedures.", "core", "operations", 1)
    assert agent.bundle_adjacent_english_records([zh], [first, condition], "core", [""]) == [""]


def test_callsign_reference_direction_and_company_name_are_not_seasons():
    zh = "呼号会用ABC代替AirBeta。"
    en = 'Spring Airlines callsign may use “ABC” in lieu of “AIR BETA”.'
    assert agent.manual_pairing_tokens(zh) == agent.manual_pairing_tokens(en)
    assert agent.manual_pairing_tokens(zh) != agent.manual_pairing_tokens(en.replace('“ABC” in lieu of “AIR BETA”', '“AIR BETA” in lieu of “ABC”'))
    assert "season_spring" not in agent.manual_pairing_concepts(en)
    assert "season_winter" in agent.manual_pairing_concepts("Winter Airlines operates in winter when icing is common.")
    assert agent.source_projection_controls_match("需要证实ATC指令。", "ATC instructions must be confirmed.")
    assert not agent.source_projection_controls_match("无需证实ATC指令。", "ATC instructions must be confirmed.")


def test_complete_source_date_is_not_a_runway_or_an_ignorable_number():
    zh = "跑道信息：26号盲降停用至202611月27号（通告中有信息）。"
    en = "Runway Information: ILS Runway 26 is unserviceable until 27 NOV 2026 (refer to NOTAM)."
    assert agent.manual_pairing_tokens(zh) == agent.manual_pairing_tokens(en)
    assert "DATE:2026-11-27" in agent.manual_pairing_tokens(zh)
    assert "RWY27" not in agent.manual_pairing_tokens(zh)
    assert agent.manual_pairing_tokens(zh) != agent.manual_pairing_tokens(en.replace("27 NOV", "28 NOV"))
    assert agent.manual_pairing_tokens(zh) != agent.manual_pairing_tokens(en.replace("Runway 26", "Runway 27"))
    assert "RWY27" in agent.manual_pairing_tokens("27号跑道ILS进近。")
    assert agent.source_date_comparison("2026年11月27日")[1] == agent.source_date_comparison("November 27, 2026")[1]
    assert agent.source_date_comparison("2026年2月30日")[0] == "2026年2月30日"
