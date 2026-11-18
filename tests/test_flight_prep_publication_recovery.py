from datetime import datetime, timedelta
import json
import subprocess
from pathlib import Path

import pytest
from scripts import publish_flight_preparation as publisher
from scripts import check_flight_prep_schedule as checker
from tests.test_flight_prep_schedule import _repo_with_event, _write_success_state, TARGET


def test_grace_then_bounded_recovery_without_success_or_last_good_changes(tmp_path):
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    path = repo / f'flight_preparation/{TARGET}_meta.json'
    path.write_text(json.dumps({'target_date': str(TARGET)}))
    first = checker.evaluate_preparation(repo, TARGET)
    checker.record_dispatched_generation(repo, TARGET, first)
    assert checker.evaluate_preparation(repo, TARGET).status == 'AWAITING_PUBLICATION'
    for count in (1, 2, 3):
        state = json.loads(path.read_text())
        state['generation_attempt']['dispatched_at_beijing'] = (datetime.now(checker.BEIJING)-timedelta(hours=3)).isoformat()
        path.write_text(json.dumps(state))
        result = checker.evaluate_preparation(repo, TARGET)
        assert result.should_dispatch == (count < 3)
        if count < 3:
            assert result.status == 'RECOVERY_DISPATCH'
            checker.record_dispatched_generation(repo, TARGET, result)
        else:
            assert result.status == 'RECOVERY_EXHAUSTED'
    assert not (path.parent/'.success').exists()
    assert 'status' not in json.loads(path.read_text())


def run(repo, *args):
    return subprocess.check_output(['git','-C',str(repo),*args]).decode().strip()


def setup_remote(tmp_path):
    remote, repo = tmp_path/'remote.git', tmp_path/'repo'
    subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
    subprocess.run(['git','clone',str(remote),str(repo)],check=True,capture_output=True)
    run(repo,'config','user.name','Test');run(repo,'config','user.email','test@example.invalid')
    run(repo,'switch','-c','main')
    (repo/'flight_preparation').mkdir()
    (repo/'flight_preparation/latest.txt').write_text('LAST_GOOD')
    (repo/'seed').write_text('base')
    run(repo,'add','.');run(repo,'commit','-m','base');run(repo,'push','origin','main')
    return repo,run(repo,'rev-parse','HEAD')


def test_add_add_receipt_is_safe_but_changed_formal_output_is_not(tmp_path):
    repo,base=setup_remote(tmp_path)
    name='flight_preparation/2026-11-20_meta.json'
    (repo/name).write_text(json.dumps({'target_date':'2026-11-20','generation_attempt':{'state':'AWAITING_PUBLICATION'}}))
    run(repo,'add',name);run(repo,'commit','-m','scheduler receipt');run(repo,'push','origin','main')
    content=b'{"status":"SUCCESS","target_date":"2026-11-20"}'
    body='flight_preparation/2026-11-20_航前准备.txt'
    sha=publisher.publish(repo,base,{name:content,body:b'VALIDATED'},'2026-11-20')
    assert publisher.blob(repo,sha,name)==content
    assert publisher.blob(repo,sha,body)==b'VALIDATED'
    assert publisher.blob(repo,sha,'flight_preparation/latest.txt')==b'LAST_GOOD'
    assert publisher.publish(repo,base,{name:content,body:b'VALIDATED'},'2026-11-20')==sha
    with pytest.raises(RuntimeError,match='OUTPUT_MOVED'):
        publisher.publish(repo,base,{body:b'OTHER'},'2026-11-20')


def test_intervening_input_change_blocks_stale_artifact(tmp_path):
    repo,base=setup_remote(tmp_path)
    (repo/'flight.ics').write_text('new tasks')
    run(repo,'add','.');run(repo,'commit','-m','calendar');run(repo,'push','origin','main')
    with pytest.raises(RuntimeError,match='GENERATION_INPUTS_MOVED'):
        publisher.publish(repo,base,{'flight_preparation/2026-11-20_航前准备.txt':b'OLD'},'2026-11-20')


@pytest.mark.parametrize('response_lost', [False, True])
def test_non_fast_forward_or_lost_response_recovers_without_duplicate_update(tmp_path, monkeypatch, response_lost):
    repo,base=setup_remote(tmp_path)
    original=publisher.git
    pushes=[]
    def intercepted(root,*args,**kwargs):
        if args[0]=='push':
            pushes.append(args)
            if len(pushes)==1:
                if response_lost:
                    original(root,*args,**kwargs)
                else:
                    (repo/'seed').write_text('concurrent unrelated change')
                    run(repo,'add','seed');run(repo,'commit','-m','unrelated');run(repo,'push','origin','main')
                return subprocess.CompletedProcess(args,1,b'',b'')
        return original(root,*args,**kwargs)
    monkeypatch.setattr(publisher,'git',intercepted)
    name='flight_preparation/2026-11-20_航前准备.txt'
    sha=publisher.publish(repo,base,{name:b'VALIDATED'},'2026-11-20')
    assert publisher.blob(repo,sha,name)==b'VALIDATED'
    assert len(pushes)==(1 if response_lost else 2)
    assert publisher.blob(repo,sha,'flight_preparation/latest.txt')==b'LAST_GOOD'


def test_receipt_change_does_not_allow_success_or_source_failure_overwrite():
    assert publisher.receipt_only_change(None,b'{"target_date":"2026-11-20","generation_attempt":{}}')
    assert not publisher.receipt_only_change(None,b'{"status":"SUCCESS"}')
    assert not publisher.receipt_only_change(b'{"status":"FAILED_SAFE"}',b'{"status":"SUCCESS"}')


def test_workflows_serialize_with_queue_without_cancelling_or_rebasing():
    root=Path(__file__).parents[1]
    for name in ('schedule.yml','flight-prep-free-v5-20260616.yml'):
        text=(root/'.github/workflows'/name).read_text(encoding='utf-8')
        assert 'group: crew-calendar\n  cancel-in-progress: false\n  queue: max' in text
    text=(root/'.github/workflows/flight-prep-free-v5-20260616.yml').read_text(encoding='utf-8')
    assert 'git rebase' not in text and 'publish_flight_preparation.py' in text
