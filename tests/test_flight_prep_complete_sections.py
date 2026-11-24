"""All-airport source completeness, without changing release safeguards."""
from dataclasses import replace
from datetime import date

import pytest

from crew_agents import flight_prep_agent as a
from test_flight_prep_briefing_selection import fact, choose
from test_flight_prep_independent_languages import flight, record
from test_flight_prep_safe_output_cleanup import chinese_record


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


@pytest.mark.parametrize('month', range(1, 13))
def test_all_months_retain_original_season_conditions_values_and_controls(month):
    zh = '5至9月进场时注意雷雨；保持3000ft，未经ATC许可不得转弯。冬季运行：先取得除冰许可，再滑行。'
    en = 'From May to September, watch for thunderstorms on arrival; maintain 3000ft and do not turn without ATC clearance. Winter operations: obtain deicing clearance before taxi.'
    raw = chinese_record(zh, text_en=en)
    source = a.source_record_facts('AAAA', [raw], category='core')[0]
    logs = []
    kept = a.filter_fact_for_duty(source, flight(), date(2026, month, 15), logs)
    assert kept is not None and kept.zh == zh and kept.en == en
    assert kept.source_text_zh == zh and kept.source_page == '10'
    assert not logs and not kept.excluded_source_clauses
    assert a.validate_source_semantic_preservation(kept) == []
    english = a.english_briefing_fact_sets(
        replace(flight(), summary='9C0002 BBBB→AAAA'), date(2026, month, 15),
        {'AAAA': [record(en)], 'BBBB': []})[2]
    assert len(english) == 1 and english[0].en == en
    assert english[0].source_text_en == en and english[0].source_page == '20'
    assert a.validate_english_source_facts('AAAA', english) == []


def test_season_retention_does_not_override_other_route_or_explicit_expiry():
    source = a.source_record_facts('AAAA', [chinese_record('冬季注意结冰。')], category='core')[0]
    assert a.filter_fact_for_duty(replace(source, route_scope=(('CCCC', 'DDDD'),)), flight(), date(2026, 8, 1)) is None
    expired = a.source_record_facts('AAAA', [chinese_record('冬季运行：2025年1月1日至2025年2月1日跑道关闭。')], category='core')[0]
    assert a.filter_fact_for_duty(expired, flight(), date(2026, 8, 1)) is None


def test_static_elevation_papi_and_administration_are_background_only():
    records = [chinese_record('机场标高：13ft。', 'zh:height'),
               chinese_record('PAPI信息：08：3°，MEHT20m。', 'zh:papi'),
               chinese_record('廊桥密码：1234。', 'zh:admin')]
    facts = a.source_record_facts('AAAA', records, category='core')
    exclusions = []
    output = a.select_source_briefing_content(facts, 'departure', category='core', exclusion_log=exclusions)
    assert output == []
    assert sum(e['reason'] == 'static_airport_catalogue_background_only' for e in exclusions) == 2
    english = a.english_briefing_fact_sets(flight(), date(2026, 11, 15), {'AAAA': [
        record('Airport elevation: 13 ft.', identity='en:height'),
        record('PAPI Information: RWY 08: 3 degrees, MEHT20m.', identity='en:papi'),
        record('The jet bridge password is 1234.', identity='en:admin')], 'BBBB': []})[2]
    assert english == []


def test_retained_month_range_is_not_a_route_but_unknown_named_routes_still_block():
    for text in ('From May to September, thunderstorms occur.', 'From November to February, icing occurs.'):
        english = a.english_briefing_fact_sets(flight(), date(2026, 4, 15), {'AAAA': [record(text)], 'BBBB': []})[2]
        assert len(english) == 1 and english[0].en == text
        assert a.validate_english_source_facts('AAAA', english) == []
    for text in ('From Rome to Oslo, maintain 3000ft.',
                 'From May to Oslo, maintain 3000ft.',
                 'From May to September, thunderstorms occur. From Rome to Oslo, maintain 3000ft.'):
        english = a.english_briefing_fact_sets(flight(), date(2026, 4, 15), {'AAAA': [record(text)], 'BBBB': []})[2]
        assert a.validate_english_source_facts('AAAA', english)


def test_truncated_chapter_heading_with_codes_cannot_leak_the_next_airport_elevation():
    text = '\n'.join([
        '页码：10', '甲地机场运行特点 ALPHA(AAA/AAAA)', '一、运行特点', '机场标高：7000ft。',
        '页码：11', '乙地机场运行特BRAVO(BBB/BBBB)', '一、运行特点', '机场标高：3000ft。',
        '页码：12', '丙地机场运行特点 CHARLIE(CCC/CCCC)', '机场标高：13ft。',
    ])
    chapters = a.build_manual_index(text)
    assert [chapter['icao'] for chapter in chapters] == ['AAAA', 'BBBB', 'CCCC']
    assert [chapter['name_key'] for chapter in chapters] == ['甲地', '乙地', '丙地']
    assert '3000ft' not in '\n'.join(chapters[0]['lines'])
    assert '3000ft' in '\n'.join(chapters[1]['lines'])
    assert '13ft' not in '\n'.join(chapters[1]['lines'])
    assert not a.is_manual_airport_header('乙地机场运行特BRAVO')
    assert not a.is_manual_airport_header('乙地机场运行特，参考BRAVO(BBB/BBBB)。')


@pytest.mark.parametrize('language', ['zh', 'en'])
def test_basic_source_without_incidents_still_has_fixed_empty_event_heading(language):
    duty = flight()
    empty = {airport: [] for airport in duty.route}
    core = {airport: [a.BilingualFact('height-' + airport, '机场标高：13ft。',
        'Airport elevation: 13 ft.', airport=airport, category='core', source_verbatim=True)]
        for airport in duty.route}
    render = a.render_chinese_briefing if language == 'zh' else a.render_english_briefing
    body = render(duty, date(2026, 11, 15), {}, [], empty, core)
    headings = ('典型不安全事件：', '核心威胁：') if language == 'zh' else ('Typical unsafe events:', 'Core threats:')
    assert headings[0] + '\n\n' + headings[1] in body
    assert body.count(headings[0]) == 1
    assert '暂无' not in body and 'No incidents' not in body
