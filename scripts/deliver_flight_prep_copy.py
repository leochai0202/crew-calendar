"""Deliver private source copies to the configured recipient; publish no plaintext."""
import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import json
import re
import os
from pathlib import Path
import smtplib
import ssl
import subprocess
import sys
from datetime import date
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents.flight_prep_fingerprint import task_fingerprint_from_events
from crew_agents.ics_utils import parse_ics
from crew_agents.flight_prep_inputs import generation_inputs
from crew_agents.common import atomic_write_json
from crew_agents.flight_prep_preview import source_copy_errors


def validate_copy(folder):
    class Payloads(HTMLParser):
        def __init__(self):
            super().__init__();self.bodies={};self.active=None
        def handle_starttag(self,tag,attrs):
            if tag=='textarea':
                self.active=dict(attrs).get('id')
                if self.active in self.bodies:raise ValueError('DUPLICATE_PAYLOAD')
                self.bodies[self.active]=''
        def handle_data(self,data):
            if self.active:self.bodies[self.active]+=data
        def handle_endtag(self,tag):
            if tag=='textarea':self.active=None
    parser=Payloads();parser.feed((folder/'copy.html').read_text(encoding='utf-8'))
    meta = json.loads((folder/'preview_meta.json').read_text(encoding='utf-8'))
    groups = meta['groups']
    for group in groups:
        for lang in ('zh', 'en'):
            group['_source_copy_'+lang] = parser.bodies.get(f"g{group['group_index']}-{lang}",'')
    errors = source_copy_errors(folder, groups)
    if errors:
        raise ValueError('SOURCE_COPY_INTEGRITY_FAILED')
    return meta


def send(folder, day, *, smtp=smtplib.SMTP_SSL, formal_root=None, cancelled=False):
    if os.environ.get('FLIGHT_PREP_PRIVATE_MAIL_APPROVED') != 'true':
        raise ValueError('CONTROLLED_DELIVERY_NOT_AUTHORIZED')
    # Only the existing configured recipient, no CLI recipient overrides.
    sender, password, recipient = (os.environ.get(key, '') for key in
        ('GMAIL_SMTP_USER','GMAIL_SMTP_APP_PASSWORD','CREW_NOTIFY_EMAIL'))
    if not all((sender,password,recipient)) or any('\n' in value or '\r' in value for value in (sender,recipient)):
        raise ValueError('CONTROLLED_DELIVERY_UNCONFIGURED')
    msg = EmailMessage()
    msg['From'],msg['To'],msg['Subject'] = sender,recipient,f'航前原文复制稿 {day} — '+('已失效：当前无任务' if cancelled else '非正式运行批准')
    digest=hashlib.sha256(b'NO_TASK' if cancelled else (folder/'copy.html').read_bytes()).hexdigest()
    msg['Message-ID']=f'<crew-copy-{day}-{digest}@crew-calendar.invalid>'
    msg.set_content('当前已无有效正式航班任务；此前该日期的航前复制稿已失效，请勿作为当前准备稿使用。' if cancelled else
        '原文按各语言独立提供，不代表正式运行批准。请在下方或附件查看完整正文；冲突审计见附件。\n\n'+
        '\n\n'.join(path.read_text(encoding='utf-8') for path in sorted(folder.glob('SOURCE_COPY_group_*_zh.txt'))))
    if not cancelled:msg.add_alternative((folder/'copy.html').read_text(encoding='utf-8'),subtype='html')
    for path in ([] if cancelled else sorted(folder.iterdir())):
        if path.name in {'copy.html','preview_meta.json','review.md'} or path.name.startswith('SOURCE_COPY_group_'):
            msg.add_attachment(path.read_bytes(),maintype='application',subtype='octet-stream',filename=path.name)
    if formal_root and (formal_root/'.success').is_file():
        formal=json.loads((formal_root/f'{day}_meta.json').read_text(encoding='utf-8'))
        for group in formal.get('prep_groups',[]):
            if group.get('status')=='SUCCESS' and group.get('release_eligible'):
                for key in ('output','english_output'):
                    name=group.get(key)
                    if name and Path(name).name==name and name.startswith(day+'_'):
                        msg.add_attachment((formal_root/name).read_bytes(),maintype='application',
                            subtype='octet-stream',filename='RELEASE_'+name)
    with smtp('smtp.gmail.com',465,context=ssl.create_default_context(),timeout=60) as client:
        client.login(sender,password)
        refused=client.send_message(msg)
        if refused:
            raise RuntimeError('CONTROLLED_DELIVERY_REJECTED')
    return {'status':'SMTP_ACCEPTED','content_sha256':digest,
            'accepted_at':datetime.now(timezone.utc).isoformat(),
            'recipient_read_confirmed':False}


def public_state(meta, source_status, delivery):
    # Deliberate allowlist: no names, flights, source text, errors, addresses,
    # headings, page excerpts or complete private metadata in the public repo.
    return {'schema':2,'target_date':meta['target_date'],'status':meta['status'],
            'release_status':meta.get('release_status',meta['status']),
            'task_fingerprint':meta['task_fingerprint'],
            'generation_inputs':{'sha256':meta['generation_inputs']['sha256']},
            'source_copy_status':source_status,'controlled_delivery':delivery}


def safe_public_payload(state):
    allowed={'schema','target_date','status','release_status','task_fingerprint','generation_inputs',
             'source_copy_status','controlled_delivery','generation_attempt'}
    if set(state)-allowed or state.get('schema')!=2:
        raise ValueError('UNSAFE_PUBLIC_STATE')
    date.fromisoformat(state['target_date'])
    for status in (state['status'],state['release_status']):
        if status not in {'SUCCESS','PARTIAL_RELEASE','FAILED_SAFE','NO_TASK','NEEDS_SELECTION'}:
            raise ValueError('UNSAFE_PUBLIC_STATE')
    if state['source_copy_status'] not in {'SOURCE_COPY_READY','SOURCE_COPY_FAILED'}:
        raise ValueError('UNSAFE_PUBLIC_STATE')
    for digest in (state['task_fingerprint'],state['generation_inputs']['sha256']):
        if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('UNSAFE_PUBLIC_STATE')
    if set(state['generation_inputs'])!={'sha256'}:raise ValueError('UNSAFE_PUBLIC_STATE')
    delivery=state['controlled_delivery']
    if set(delivery)-{'status','content_sha256','accepted_at','recipient_read_confirmed'} or delivery['status'] not in {'SMTP_ACCEPTED','NOT_SENT','DELIVERY_UNCONFIRMED'}:
        raise ValueError('UNSAFE_PUBLIC_STATE')
    if 'content_sha256' in delivery and not re.fullmatch('[0-9a-f]{64}',delivery['content_sha256']):raise ValueError('UNSAFE_PUBLIC_STATE')
    if 'accepted_at' in delivery:datetime.fromisoformat(delivery['accepted_at'])
    if 'recipient_read_confirmed' in delivery and type(delivery['recipient_read_confirmed']) is not bool:
        raise ValueError('UNSAFE_PUBLIC_STATE')
    attempt=state.get('generation_attempt',{})
    if set(attempt)-{'input_sha256','task_fingerprint','attempt_count','dispatched_at_beijing','state'}:
        raise ValueError('UNSAFE_PUBLIC_STATE')
    if attempt:
        if attempt['input_sha256']!=state['generation_inputs']['sha256'] or attempt['task_fingerprint']!=state['task_fingerprint']:
            raise ValueError('UNSAFE_PUBLIC_STATE')
        datetime.fromisoformat(attempt['dispatched_at_beijing'])
        if attempt.get('state') not in {'DELIVERED','AWAITING_PUBLICATION','DELIVERY_UNCONFIRMED'} or type(attempt.get('attempt_count',1)) is not int:
            raise ValueError('UNSAFE_PUBLIC_STATE')
    return state


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target-date',required=True)
    parser.add_argument('--days-ahead',default='1');args=parser.parse_args()
    root=Path.cwd();day=args.target_date
    date.fromisoformat(day)
    old_path=root/'flight_preparation'/f'{day}_meta.json'
    old=json.loads(old_path.read_text(encoding='utf-8')) if old_path.is_file() else {}
    env=dict(os.environ);env.pop('GITHUB_STEP_SUMMARY',None)
    # The generator's source-rich review summary/log never goes to public Actions.
    result=subprocess.run([sys.executable,'-B','crew_agents/flight_prep_agent.py','--repo','.',
        '--target-date',day,'--days-ahead',args.days_ahead],env=env,capture_output=True)
    path=root/'flight_preparation'/f'{day}_meta.json'
    meta=json.loads(path.read_text(encoding='utf-8'))
    current,_=task_fingerprint_from_events(parse_ics(root/'flight.ics'),date.fromisoformat(day))
    inputs=generation_inputs(root)
    if meta.get('target_date')!=day or meta.get('task_fingerprint')!=current or meta.get('generation_inputs')!=inputs:
        meta={'target_date':day,'task_fingerprint':current,'generation_inputs':inputs,'status':'FAILED_SAFE'}
        stale=True
    else:stale=False
    folder=root/'agent_output/flight_prep/previews'/day
    source_status='SOURCE_COPY_FAILED';delivery={'status':'NOT_SENT'}
    try:
        if stale:
            raise ValueError('STALE_GENERATION')
        if meta['status']=='NO_TASK':
            delivery=send(folder,day,cancelled=True)
        else:
            validate_copy(folder);source_status='SOURCE_COPY_READY'
            delivery=send(folder,day,formal_root=root/'flight_preparation')
    except Exception:
        delivery={'status':'DELIVERY_UNCONFIRMED'}  # no exception content/SMTP credentials
    state=public_state(meta,source_status,delivery)
    attempt=old.get('generation_attempt',{})
    same=(attempt.get('input_sha256')==state['generation_inputs']['sha256'] and
          attempt.get('task_fingerprint')==state['task_fingerprint'])
    state['generation_attempt']={key:attempt[key] for key in ('input_sha256','task_fingerprint','attempt_count','dispatched_at_beijing','state') if key in attempt} if same else {'input_sha256':state['generation_inputs']['sha256'],
        'task_fingerprint':state['task_fingerprint'],'attempt_count':1,
        'dispatched_at_beijing':datetime.now(timezone.utc).isoformat(),'state':'DELIVERY_UNCONFIRMED'}
    state['generation_attempt'].setdefault('attempt_count',1)
    state['generation_attempt']['state']='DELIVERED' if delivery['status']=='SMTP_ACCEPTED' else 'DELIVERY_UNCONFIRMED'
    atomic_write_json(root/'agent_output/flight_prep/public_delivery_state.json',state)
    print('SOURCE_COPY_STATUS='+source_status)
    print('RELEASE_STATUS='+str(meta['status']))
    print('CONTROLLED_DELIVERY='+delivery['status'])
    # State publication must still run after failed extraction/delivery.
    return 0


if __name__=='__main__':
    raise SystemExit(main())
