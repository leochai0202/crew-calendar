import json

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.flight_prep_preview import source_copy_errors, write_preview
from test_flight_prep_preview import group, test_real_entry_gates_preview_and_preserves_formal_last_good as exercise_entry


def ready_group():
    data, errors = group()
    for lang, key, prefix, headings in (
        ('zh', 'airport_fact_sources', '我是来自飞行十五中队的副驾驶测试。',
         ['上一次飞行中机长/教员对我优缺点的评价（作为PF/PM各取最近一次）：', '上一次作为PF教员评价：测试。', '作为PM机长评价：测试。', '典型不安全事件：', '核心威胁：']),
        ('en', 'english_fact_sources', 'I am Test.',
         ['Latest PF/PM feedback:', 'As PF, test.', 'As PM, test.', 'Typical unsafe events:', 'Core threats:']),
    ):
        facts = data[key]['AAAA']
        data.setdefault('source_copy_fact_sources', {})[lang] = facts
        text = facts[0]['text_zh' if lang == 'zh' else 'text_en']
        data['_source_copy_' + lang] = '\n\n'.join([prefix, *headings, text]) + '\n'
    return data, errors


@pytest.mark.parametrize('missing_english', [False, True])
def test_copy_ready_despite_conflicting_languages_or_missing_english(tmp_path, missing_english):
    data, errors = ready_group()
    if missing_english:
        data['_source_copy_en'] = ''
        data['source_copy_fact_sources']['en'] = []
    write_preview(tmp_path, '2026-01-01', [data], errors, 'manual.pdf', 'test')
    assert errors and not source_copy_errors(tmp_path, [data])
    assert not (tmp_path / '.success').exists()


@pytest.mark.parametrize('damage', ['format', 'source', 'file', 'button', 'body'])
def test_invalid_copy_never_reports_ready(tmp_path, damage):
    data, errors = ready_group()
    if damage == 'format':
        data['_source_copy_zh'] = '1. ' + data['_source_copy_zh']
    if damage == 'source':
        data['source_copy_fact_sources']['zh'][0]['source_page'] = 'N/A'
    write_preview(tmp_path, '2026-01-01', [data], errors, 'manual.pdf', 'test')
    if damage == 'file':
        (tmp_path / 'SOURCE_COPY_group_01_zh.txt').unlink()
    if damage in ('button', 'body'):
        path = tmp_path / 'copy.html'
        text = path.read_text(encoding='utf-8')
        text = text.replace('data-copy="g1-zh"', 'disabled') if damage == 'button' else text.replace('OLPAB', 'CHANGED')
        path.write_text(text, encoding='utf-8')
    assert source_copy_errors(tmp_path, [data])


def test_ready_artifact_exit_zero_does_not_authorize_release(tmp_path, monkeypatch):
    exercise_entry(tmp_path, monkeypatch, 'release', True)  # invalid mocked copy stays exit 2
    monkeypatch.setattr('crew_agents.flight_prep_preview.source_copy_errors', lambda *a: [])
    assert agent.main() == 0
    formal = tmp_path / 'flight_preparation'
    assert not (formal / '.success').exists()
    assert (formal / 'latest.txt').read_text() == 'LAST_GOOD'
    status = json.loads((tmp_path / 'agent_output/flight_prep/status.json').read_text())
    assert status['source_copy_status'] == 'SOURCE_COPY_READY'
    assert status['status'] == status['release_status'] == 'FAILED_SAFE'
    assert status['errors']
