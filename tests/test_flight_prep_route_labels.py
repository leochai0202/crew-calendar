from datetime import date
import pytest
from crew_agents import flight_prep_agent as agent
from tests.test_flight_prep_applicability_english_quality import _event


REGISTRY = {code: {'canonical_zh': name} for code, name in (
    ('AAAA', '甲地机场'), ('BBBB', '乙地机场'), ('CCCC', '丙地机场'), ('DDDD', '丁地机场'))}


@pytest.mark.parametrize('text,expected', [
    ('甲地乙地航路：有活动时使用A123，提前核对。', [('甲地机场', '乙地机场')]),
    ('航路：甲地-乙地、丙地可以申请直飞FIXA。', [('甲地机场', '乙地机场'), ('甲地机场', '丙地机场')]),
    ('释压程序：：甲地到乙地涉及释压程序，详见受控资料。', [('甲地机场', '乙地机场')]),
    ('甲地飞往乙地涉及特殊程序。', [('甲地机场', '乙地机场')]),
    ('甲地至乙地涉及特殊程序。', [('甲地机场', '乙地机场')]),
])
def test_evidenced_route_labels_are_generic_and_directional(text, expected):
    scopes = agent.record_route_scope({'category': 'core'}, text, REGISTRY)
    assert set(scopes) == set(expected)
    fact = agent.BilingualFact('scoped', text, '', airport='甲地机场', category='core',
        route_scope=scopes, source_verbatim=True, source_file='manual.pdf', source_page='1')
    audit = []
    assert agent.filter_fact_for_duty(fact, _event('other', '丁地机场', '甲地机场'), date(2026, 11, 18), audit) is None
    assert audit[0]['fact_id'] == 'scoped' and audit[0]['source_page'] == '1'
    assert agent.filter_fact_for_duty(fact, _event('match', *expected[-1]), date(2026, 11, 18)) is not None
    assert agent.record_route_scope({'category': 'typical'}, text, REGISTRY) == ()


@pytest.mark.parametrize('text', [
    '甲地与乙地之间天气变化较大，注意绕飞。',
    '历史上甲地到乙地的航班曾遇乱流。',
    '例如甲地到乙地涉及其他情况，本机场均需注意地形。',
    '甲地-乙地、未知地点可以申请直飞FIXA。',
    '甲地未知地点航路：注意核对。',
])
def test_names_or_unresolved_lists_do_not_prove_route_scope(text):
    assert agent.record_route_scope({'category': 'core'}, text, REGISTRY) == ()


def test_joined_label_keeps_explicit_reverse_controls_but_never_infers_symmetry():
    text = '甲地乙地航路：甲地飞乙地有活动时使用A123；乙地飞甲地有活动时使用B456。'
    scope = agent.record_route_scope({'category': 'core'}, text, REGISTRY)
    assert set(scope) == {('甲地机场', '乙地机场'), ('乙地机场', '甲地机场')}
    fact = agent.BilingualFact('both', text, '', category='core', source_verbatim=True, route_scope=scope)
    retained = agent.filter_fact_for_duty(fact, _event('reverse', '乙地机场', '甲地机场'), date(2026, 11, 18))
    assert retained is not None and retained.zh == text
    one_way = agent.record_route_scope({'category': 'core'}, '甲地乙地航路：有活动时使用A123。', REGISTRY)
    assert one_way == (('甲地机场', '乙地机场'),)


def test_english_flattened_routes_keep_parent_conditions_and_audit_removed_blocks():
    from test_flight_prep_independent_languages import flight, record
    text = ('Maintain 3000ft when cleared. For AAAA-CCCC flights: use FIXC after clearance. '
            'Do not turn before 5000ft. For AAAA-BBBB flights: use FIXB after clearance. '
            'Maintain 6000ft until instructed. 4. DDDD-AAAA Route: use FIXD; '
            'for the approach, use the FIXD-1A arrival route.')
    exclusions = []
    facts = agent.english_briefing_fact_sets(flight(), date(2026, 11, 18),
        {'AAAA': [record(text, phase='navigation')], 'BBBB': []}, exclusions)[2]
    assert len(facts) == 1
    fact = facts[0]
    assert fact.en == ('Maintain 3000ft when cleared. For AAAA-BBBB flights: use FIXB after clearance. '
                       'Maintain 6000ft until instructed.')
    assert fact.source_text_en == text and fact.source_page == '20'
    assert len(exclusions) == 2
    assert 'Do not turn before 5000ft.' in exclusions[0]['clause']
    assert 'for the approach, use the FIXD-1A arrival route.' in exclusions[1]['clause']
    assert all(row['original_text'] == text and row['source_page'] == '20' for row in exclusions)
    assert not agent.validate_english_source_facts('AAAA', facts)


@pytest.mark.parametrize('category', ['typical', 'history'])
def test_english_historical_route_blocks_are_not_filtered(category):
    text = 'An incident occurred. For AAAA-CCCC flights: the clearance was misunderstood.'
    fact = agent.BilingualFact('history', '', text, category=category, language='en')
    assert agent.filter_english_route_fragments(fact, {('AAAA', 'BBBB')}) == fact


def test_english_unknown_heading_stops_scope_inheritance_without_guessing():
    text = ('Monitor terrain. For AAAA-CCCC flights: use FIXC. '
            'For northern departures: retain 3000ft until cleared.')
    fact = agent.BilingualFact('mixed', '', text, category='core', language='en')
    selected = agent.filter_english_route_fragments(fact, {('AAAA', 'BBBB')})
    assert selected.en == 'Monitor terrain. For northern departures: retain 3000ft until cleared.'


def test_english_explicit_arrival_endpoint_and_return_direction_are_not_departure_scope():
    text = ('Monitor terrain. For the flight back to AAAA, use FIXA. '
            'For CCCC (Example) arrivals: use FIXC. For BBBB arrivals: use FIXB.')
    fact = agent.BilingualFact('mixed', '', text, category='core', language='en')
    selected = agent.filter_english_route_fragments(fact, {('AAAA', 'BBBB')})
    assert selected.en == 'Monitor terrain. For BBBB arrivals: use FIXB.'
    reverse = agent.filter_english_route_fragments(fact, {('BBBB', 'AAAA')})
    assert reverse.en == 'Monitor terrain. For the flight back to AAAA, use FIXA.'


def test_english_multiple_actual_segments_keep_either_matching_route_block():
    text = 'Monitor terrain. For AAAA-BBBB flights: use FIXB. For BBBB-CCCC flights: use FIXC.'
    fact = agent.BilingualFact('mixed', '', text, category='core', language='en')
    assert agent.filter_english_route_fragments(fact, {('AAAA', 'BBBB'), ('BBBB', 'CCCC')}) == fact
