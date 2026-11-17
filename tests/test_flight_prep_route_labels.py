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
