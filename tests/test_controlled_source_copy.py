from pathlib import Path
import json
import pytest
from crew_agents import flight_prep_agent as agent
from scripts.deliver_flight_prep_copy import public_state, send
from scripts import check_flight_prep_schedule as checker
from tests.test_flight_prep_schedule import _repo_with_event, _write_success_state, TARGET

@pytest.mark.parametrize('text', ['机场标高：706ft。','跑道信息：06/24（3200m×45m）。','PAPI信息：3.0°。','机场坐标：N31 E121。'])
def test_only_static_catalogue_is_excluded(text):
    assert agent.static_airport_catalogue_only(text)

@pytest.mark.parametrize('text', ['机场标高：7358ft，地形复杂，起飞性能受限制。','PAPI信息：偏差较大，必须使用仪表监控。','跑道信息：入口内移，注意着陆距离限制。'])
def test_compound_operating_requirement_is_not_deleted_by_keyword(text):
    assert not agent.static_airport_catalogue_only(text)

def test_public_state_has_no_private_source_or_personal_values():
    meta={'target_date':'2026-11-26','status':'FAILED_SAFE','task_fingerprint':'task',
          'generation_inputs':{'sha256':'inputs'},'matched_people':['PRIVATE_PERSON'],
          'errors':['PRIVATE_SOURCE']}
    state=public_state(meta,'SOURCE_COPY_READY',{'status':'SMTP_ACCEPTED'})
    assert 'PRIVATE' not in json.dumps(state)
    assert state['status']=='FAILED_SAFE' and state['source_copy_status']=='SOURCE_COPY_READY'

def test_delivered_copy_suppresses_regeneration_without_releasing_failed_group(tmp_path):
    repo=_repo_with_event(tmp_path);_write_success_state(repo)
    path=repo/f'flight_preparation/{TARGET}_meta.json'
    state=json.loads(path.read_text(encoding='utf-8'))
    state.update(schema=2,status='FAILED_SAFE',source_copy_status='SOURCE_COPY_READY',controlled_delivery={'status':'SMTP_ACCEPTED'})
    path.write_text(json.dumps(state))
    result=checker.evaluate_preparation(repo,TARGET)
    assert not result.should_dispatch and result.reason=='source_copy_delivered_for_current_inputs'
    assert json.loads(path.read_text(encoding='utf-8'))['status']=='FAILED_SAFE'
    (repo/'config').mkdir();(repo/'config/prep_settings.json').write_text('{}')
    assert checker.evaluate_preparation(repo,TARGET).should_dispatch

def test_mail_fails_closed_without_existing_recipient(monkeypatch,tmp_path):
    monkeypatch.delenv('CREW_NOTIFY_EMAIL',raising=False)
    with pytest.raises(ValueError,match='UNCONFIGURED'):send(tmp_path,'2026-11-26')

def test_workflow_uploads_only_nonsensitive_state_and_does_not_generate_public_summary():
    root=Path(__file__).parents[1]
    text=(root/'.github/workflows/flight-prep-free-v5-20260616.yml').read_text(encoding='utf-8')
    upload=text.split('- name: Upload preparation artifact')[1].split('- name: Commit successful preparation')[0]
    assert 'path: agent_output/flight_prep/public_delivery_state.json' in upload
    assert 'flight_preparation/' not in upload
    assert 'deliver_flight_prep_copy.py' in text


def test_validated_mail_preserves_copy_bytes_and_requires_tls_and_fixed_recipient(tmp_path,monkeypatch):
    from test_flight_prep_source_copy_status import ready_group
    from crew_agents.flight_prep_preview import write_preview
    from scripts.deliver_flight_prep_copy import validate_copy
    group,errors=ready_group();write_preview(tmp_path,'2026-11-26',[group],errors,'manual.pdf','test')
    validate_copy(tmp_path)
    for key,value in {'GMAIL_SMTP_USER':'sender@example.invalid','GMAIL_SMTP_APP_PASSWORD':'synthetic-secret','CREW_NOTIFY_EMAIL':'recipient@example.invalid'}.items():
        monkeypatch.setenv(key,value)
    messages=[]
    class SMTP:
        def __init__(self,host,port,**kwargs):
            assert host=='smtp.gmail.com' and port==465 and kwargs['timeout']==60 and kwargs['context'].check_hostname
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def login(self,*args):pass
        def send_message(self,message):messages.append(message);return {}
    result=send(tmp_path,'2026-11-26',smtp=SMTP)
    assert result['status']=='SMTP_ACCEPTED' and not result['recipient_read_confirmed']
    assert messages[0]['To']=='recipient@example.invalid'
    attachments={p.get_filename():p.get_payload(decode=True) for p in messages[0].iter_attachments()}
    assert attachments['copy.html']==(tmp_path/'copy.html').read_bytes()
    assert 'synthetic-secret' not in messages[0].as_string()
    (tmp_path/'SOURCE_COPY_group_01_zh.txt').write_text('DAMAGED')
    with pytest.raises(ValueError,match='INTEGRITY'):validate_copy(tmp_path)
