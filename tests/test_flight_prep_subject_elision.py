from datetime import date, datetime
from dataclasses import asdict

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


@pytest.mark.parametrize("original,expected", [
    ("机组应提前做好下降计划。", "应提前做好下降计划。"),
    ("机组必须遵守速度限制。", "必须遵守速度限制。"),
    ("机组不得擅自转向五边。", "不得擅自转向五边。"),
    ("使用08号跑道时，机组必须保持3000ft。", "使用08号跑道时，必须保持3000ft。"),
    ("机组可以申请取消限制，否则机组应遵守限制。", "可以申请取消限制，否则机组应遵守限制。"),
    ("请机组注意风切变；飞行机组需证实ATC指令。", "请注意风切变；需证实ATC指令。"),
    ("机组在发现引导有疑问时，应当停止滑行，保持发动机运转。", "在发现引导有疑问时，应当停止滑行，保持发动机运转。"),
    ("机组如未收到ATC许可，不得进入08号跑道。", "如未收到ATC许可，不得进入08号跑道。"),
    ("机组不要盲目刹车。", "不要盲目刹车。"),
])
def test_chinese_instruction_subject_elision_preserves_modality_conditions_and_data(original, expected):
    result = agent.omit_operating_crew_subject(original, "zh", "core")
    assert result == expected
    assert agent.manual_pairing_tokens(result) == agent.manual_pairing_tokens(original)
    rendered = agent.BilingualFact("rendered", result, "", source_verbatim=True,
        source_text_zh=original, source_clauses=(original,))
    assert agent.validate_source_semantic_preservation(rendered) == []


@pytest.mark.parametrize("original", [
    "ATC必须给出明确许可。", "机务应检查发动机。", "机场方应提供引导。",
    "机组的职责包括监控。", "通知机组应注意滑行限制。", "ATC要求机组保持3000ft。",
    "机组曾未遵守限制，导致事件发生。", "机组可能遇到颠簸。", "如果机组未收到许可，不得起飞。",
    "机组在该事件中应当承担责任。",
])
def test_chinese_other_actors_objects_conditions_and_history_are_not_deleted(original):
    assert agent.omit_operating_crew_subject(original, "zh", "core") == original
    assert agent.omit_operating_crew_subject("机组必须保持高度，但未遵守。", "zh", "typical") == "机组必须保持高度，但未遵守。"


@pytest.mark.parametrize("original,expected", [
    ("The crew should monitor terrain.", "It is recommended to monitor terrain."),
    ("Flight crew must maintain 3000ft.", "It is mandatory to maintain 3000ft."),
    ("Crews shall follow ATC instructions.", "It is required to follow ATC instructions."),
    ("The flight crew must not cross Runway 08.", "It is mandatory not to cross Runway 08."),
    ("Crews should not accept an unstable approach.", "It is recommended not to accept an unstable approach."),
    ("When authorized by ATC, crews may use T1.", "When authorized by ATC, it is permitted to use T1."),
    ("After landing, the crew must stop. Crews should notify ATC.", "After landing, it is mandatory to stop. It is recommended to notify ATC."),
    ("The crew should be aware of terrain.", "It is recommended to be aware of terrain."),
    ("Crew members are advised to remain vigilant.", "It is advised to remain vigilant."),
    ("Flight crews are required to verify the clearance.", "It is required to verify the clearance."),
    ("Crews are permitted to use T1 when authorized by ATC.", "It is permitted to use T1 when authorized by ATC."),
    ("The crew is advised not to cross the holding line.", "It is advised not to cross the holding line."),
    ("The crew must carefully heed the instructions.", "It is mandatory to carefully heed the instructions."),
    ("Crews are advised to carefully review the chart.", "It is advised to carefully review the chart."),
    ("The crew should be thoroughly familiar with the notice.", "It is recommended to be thoroughly familiar with the notice."),
    ("Crews must stay vigilant.", "It is mandatory to stay vigilant."),
])
def test_english_impersonal_sentences_keep_each_modals_force(original, expected):
    result = agent.omit_operating_crew_subject(original, "en", "core")
    assert result == expected
    assert agent.manual_pairing_tokens(result) == agent.manual_pairing_tokens(original)


@pytest.mark.parametrize("original", [
    "ATC must issue clearance.", "Maintenance crews must check the engine.",
    "The airport must provide guidance.", "ATC requires the crew to maintain 3000ft.",
    "The crew's clearance is conditional.", "Crews may encounter turbulence.",
    "Crews may use a different callsign.", "The crew may not see the runway.",
    "The crew must have missed the instruction.", "Crews should monitor their altitude.",
    "The crew must stop. They must notify ATC.",
])
def test_english_preserves_other_actors_possibility_epistemic_and_pronoun_antecedents(original):
    assert agent.omit_operating_crew_subject(original, "en", "core") == original
    assert agent.omit_operating_crew_subject("The crew must stop but continued taxiing.", "en", "typical") == "The crew must stop but continued taxiing."


def test_rendering_only_never_changes_source_identity_or_raw_record(monkeypatch):
    fact = agent.BilingualFact("source:one", "机组必须保持3000ft。", "The crew must maintain 3000ft.",
        airport="甲机场", category="core", source_verbatim=True,
        source_text_zh="机组必须保持3000ft。", source_text_en="The crew must maintain 3000ft.",
        english_source_record_id="english:one", source_record_ids=("parent:one",),
        english_source="source_backed", manual_english_counterpart=True)
    before = asdict(fact)
    monkeypatch.setattr(agent, "group_personal_intro", lambda *_: "我是测试。")
    monkeypatch.setattr(agent, "english_personal_intro", lambda *_: "I am Test.")
    monkeypatch.setattr(agent, "feedback_text", lambda *_: "")
    monkeypatch.setattr(agent, "feedback_text_en", lambda *_: "")
    duty = CalendarEvent(uid="test", summary="9C0001 甲机场→乙机场", start=datetime(2026, 1, 1, 9),
        end=datetime(2026, 1, 1, 10), description="", location="", properties={})
    core = {"甲机场": [fact], "乙机场": []}
    zh = agent.render_chinese_briefing(duty, date(2026, 1, 1), {}, [], {}, core)
    en = agent.render_english_briefing(duty, date(2026, 1, 1), {}, [], {}, core)
    assert "必须保持3000ft。" in zh and "机组必须" not in zh
    assert "It is mandatory to maintain 3000ft." in en and "The crew" not in en
    assert asdict(fact) == before
    assert agent.validate_bilingual_facts([fact]) == []
    assert agent.validate_selected_fact_id_parity([fact]) == []


@pytest.mark.parametrize("english", [
    "Begin the takeoff roll immediately after receiving takeoff clearance.",
    "Commence the take-off run after receiving takeoff clearance.",
    "Start takeoff after receiving takeoff clearance.",
])
def test_takeoff_roll_accepts_equivalent_operating_actions_not_only_identical_words(english):
    assert "takeoff_roll" not in agent.bilingual_semantic_mismatches("收到起飞许可后开始起飞滑跑。", english)


@pytest.mark.parametrize("english", [
    "Begin taxiing immediately upon receiving takeoff clearance.",
    "Begin the takeoff briefing after clearance.", "Start takeoff preparation after clearance.",
])
def test_takeoff_clearance_or_briefing_is_not_evidence_of_takeoff_roll(english):
    fact = agent.BilingualFact("roll", "收到起飞许可后开始起飞滑跑。", english,
        category="core", english_source="source_backed", manual_english_counterpart=True)
    assert "takeoff_roll" in agent.bilingual_semantic_mismatches(fact.zh, fact.en)
    assert any("takeoff_roll" in error for error in agent.validate_bilingual_facts([fact]))


def test_landing_roll_is_not_interchangeable_with_taxi():
    assert "landing_roll" in agent.bilingual_semantic_mismatches("着陆滑跑时保持方向。", "Maintain direction while taxiing.")
    assert "landing_roll" not in agent.bilingual_semantic_mismatches("着陆滑跑时保持方向。", "Maintain direction during the landing roll.")


def test_reordered_whole_records_require_unique_full_operating_evidence():
    zh = ["离场：08号跑道使用RNP，地形较高，保持3000ft。", "离场：26号跑道使用盲降，地形较高，保持4000ft。"]
    texts = ["Runway 26 uses ILS; terrain is high, maintain 4000ft.", "Runway 08 uses RNP; terrain is high, maintain 3000ft."]
    facts = [agent.ManualEnglishFact(text, "core", "departure", i) for i, text in enumerate(texts)]
    assert agent.recover_reordered_english_records(zh, facts, "core", ["", ""]) == texts[::-1]
    assert agent.english_source_parents(texts[1], facts) == (texts[1],)
    assert agent.recover_reordered_english_records([zh[0], zh[0]], facts, "core", ["", ""]) == ["", ""]
    assert agent.recover_reordered_english_records(zh, facts, "core", [texts[1], ""]) == texts[::-1]
    occupied = agent.recover_reordered_english_records(zh, facts, "core", ["", texts[1]])
    assert occupied == ["", texts[1]]  # do not replace a printed conflict or reuse its paragraph
    wrong = [agent.replace(fact, phase="arrival") for fact in facts]
    assert agent.recover_reordered_english_records(zh, wrong, "core", ["", ""]) == ["", ""]
    changed = [agent.replace(fact, text=fact.text.replace("3000", "3500")) for fact in facts]
    assert agent.recover_reordered_english_records(zh, changed, "core", ["", ""])[0] == ""
    shared = [agent.ManualEnglishFact("ATC instructions apply.", "core", "departure", 0)]
    assert agent.recover_reordered_english_records(["离场：遵守ATC。"], shared, "core", [""]) == [""]
