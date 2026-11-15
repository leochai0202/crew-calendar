"""All-airport source completeness, without changing release safeguards."""
from dataclasses import replace

import pytest

from crew_agents import flight_prep_agent as a
from test_flight_prep_briefing_selection import fact, choose


@pytest.mark.parametrize('text', [
    '着陆后地面：飞机接地后应及时地使用减速装置（刹车、反推、扰流板等）。',
    '跑道信息：08/26（3000m×45m）。',
    '减噪程序：详见细则2.21.2。',
    '释压程序：详见EFB。',
    '无线电失效程序：参阅细则2.22.5。',
    '注意施工区域（2C-1-SUP）。',
    '保持安全高度。（如：需要偏航时，提前向ATC申请，且必须遵守最低高度。）。',
])
def test_complete_operating_parentheses_and_references_are_not_fragments(text):
    assert a.manual_source_quality_issue(text) == ''


def test_source_record_keeps_parenthetical_condition_after_complete_sentence(tmp_path, monkeypatch):
    raw = '进场：严格按照进、离场程序飞行；在等待中遵守安全高度。（如：进近遇恶劣天气需偏航时，提前向ATC申请，且必须遵守最低高度。）。'
    data = {'甲机场': dict(source_verbatim=True, core_threats=[raw], source_page='12', matched_header='甲机场运行特点')}
    monkeypatch.setattr(a, 'manual_airport_data', lambda *args, **kwargs: (data, 'manual.pdf', 20990101, 'PDF', []))
    records = a.airport_risks(tmp_path, ['甲机场'], {'甲机场':'AAAA'}, 1)[2]['甲机场']
    facts = a.source_record_facts('甲机场', records, category='core')
    assert len(facts) == 1
    assert '提前向ATC申请，且必须遵守最低高度' in a.chinese_fact_output(facts[0])
    assert '（如：' in facts[0].source_text_zh


@pytest.mark.parametrize('text', ['滑行时保持净距（至少5m。', '速度160节。', '高度3000米。'])
def test_real_incomplete_or_detached_fragments_still_rejected(text):
    assert a.manual_source_quality_issue(text)


def test_affirmative_attribute_row_preserves_wrapped_remark_and_exception():
    typical, core = a.scan_chapter_source_records([
        '1. 概述', '1.2. 固有属性', '固有属性 是/否 备注',
        '是否为多跑道运行 是 通常08用于起飞，', '26用于着陆（低能见度运行除外）',
        '是否为复杂机场 否', '是否存在EOSID 是 两端均存在EOSID',
        '版本：20990101 页码：12', '是否为繁忙机场 是 低高度爬升飞机较多',
        '2. 离场阶段', '2.1. 通过5000ft后转弯。',
    ])
    assert not typical
    assert '通常08用于起飞，26用于着陆（低能见度运行除外）。' in core
    assert '两端均存在EOSID。' in core
    assert '低高度爬升飞机较多。' in core
    assert not any('固有属性' in row or '是否' in row for row in core)


def test_english_attribute_columns_recover_remark_above_centred_yes():
    lines = [
        f"{'Inherent Attributes':35}{'Yes/No':10}Remarks",
        f"{'Short runway':35}{'NO':10}",
        ' ' * 45 + 'Normally Runway 08 for departures;',
        f"{'Multiple runway operations':35}{'YES':10}Runway 26 for arrivals",
        ' ' * 45 + '(except low-visibility operations).',
        f"{'Complex airport':35}{'NO':10}",
        f"{'EOSID required':35}{'YES':10}Follow the published EOSID.",
        '2. Pre-Departure Ground Operations Phase',
        '2.1. Obtain clearance before pushback.',
    ]
    text = '\n'.join(lines)
    result = a.english_attribute_remarks(text)
    assert result == ['Normally Runway 08 for departures; Runway 26 for arrivals (except low-visibility operations).',
                      'Follow the published EOSID.']
    extracted = a.extract_english_manual_facts(text)
    assert all(any(f.text == item for f in extracted) for item in result)
    assert all(f.category == 'core' for f in extracted)
    assert not a.english_attribute_remarks('Multiple runway operations YES perhaps 08')


def test_threat_table_rows_keep_individual_phase_and_controls_without_budget():
    rows = [dict(phase=phase, category='飞行程序', threat=f'{phase}存在障碍物{i}',
                 mitigation=f'按程序保持{3000+i}ft')
            for i, phase in enumerate(['离场', '进场'] * 8)]
    output = a.table_core_items(rows, max_items=1)
    assert len(output) == len(rows)
    for row, text in zip(rows, output):
        assert text.startswith(row['phase'] + '：')
        assert row['threat'] in text and row['mitigation'] in text
        assert a._chinese_manual_fact_phase(text, 'core') == ('departure' if row['phase']=='离场' else 'arrival')


@pytest.mark.parametrize('language', ['zh', 'en'])
def test_more_than_one_hundred_distinct_events_and_controls_are_not_truncated(language):
    for category in ('typical', 'core'):
        rows = [fact(str(i), f'曾发生滑行道T{i}偏差。' if language=='zh' else f'A deviation occurred on taxiway T{i}.',
                     category=category, language=language) for i in range(125)]
        assert choose(rows, category=category) == rows


def test_source_incidents_of_same_type_do_not_drop_longer_conditions_or_controls():
    rows = [fact('short', '曾发生鸟击导致雷达罩损伤超标。', category='typical'),
            fact('detail', '2025年曾发生鸟击导致雷达罩损伤超标；返航后检查。', category='typical')]
    selected = a.deduplicate_typical_incidents(rows)
    assert [(f.fact_id, f.zh) for f in selected] == [(f.fact_id, f.zh) for f in rows]
    assert not any(f.excluded_source_clauses for f in selected)


def test_papi_mention_is_not_a_license_to_remove_other_operating_instructions():
    rows = [fact('control', '进近时综合使用ILS和PAPI，无法满足稳定标准时复飞。'),
            fact('control-en', 'Use ILS and PAPI on approach; go around if unstable.', language='en')]
    assert choose(rows) == rows
    # The keyed-table conflict guard remains unchanged for background review.
    zh = fact('data', 'PAPI信息：08：3°，MEHT20m；26：3.2°，MEHT21m。',
              english_source_record_id='en-data')
    en = replace(zh, text_en='PAPI Information: RWY 08: 3.2 degrees, MEHT21m; RWY 26: 3 degrees, MEHT20m.', language='en')
    assert a.validate_cross_language_conflicts([zh], [en])
