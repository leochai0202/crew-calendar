"""Bounded local operator control of this run's already authenticated reader.

No remote debug port, arbitrary Python/JS evaluation, URL navigation or auth IO.
Only fixed visible-page operations; local mailbox data is never an artifact.
"""
import json
import os
from pathlib import Path
import re
import time
import uuid
from urllib.parse import urlsplit

from page_capture import PAGE_STATE, FRAME_VISIBLE, check_restrictions, image_evidence, duplicate, assemble_pdf, require_permission
from pdf_validation import validate_pdf
from private_delivery import encrypt_pdf

CONTROL_BASE = Path(r'D:\GGITHUB\crew-calendar\training_downloader\.runtime')
SESSION_PATTERN = re.compile(r'^[0-9a-f]{32}$')
INSPECT = """e => {
 const b=e.getBoundingClientRect(),s=getComputedStyle(e);
 if(!b.width||!b.height||s.visibility==='hidden')return null;
 const interesting=['IMG','CANVAS','IFRAME','EMBED','OBJECT','BUTTON','A','INPUT','SELECT'].includes(e.tagName)
     || e.getAttribute('role')==='button' || !!e.getAttribute('title') || !!e.getAttribute('aria-label');
 const scroll=e.scrollHeight>e.clientHeight+20 && /auto|scroll/.test(s.overflowY);
 const visual=e.querySelector('canvas,img,iframe,embed,object');
 if(!interesting&&!scroll&&!visual)return null;
 return {tag:e.tagName,id:e.id,classes:typeof e.className==='string'?e.className:'',
   text:interesting && !['INPUT','IFRAME','EMBED','OBJECT'].includes(e.tagName)?(e.innerText||e.getAttribute('title')||e.getAttribute('aria-label')||'').slice(0,100):'',
   x:Math.round(b.x),y:Math.round(b.y),width:Math.round(b.width),height:Math.round(b.height),
   scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,scrollTop:Math.round(e.scrollTop),
   naturalWidth:e.naturalWidth||e.width||0,naturalHeight:e.naturalHeight||e.height||0,
   options:e.tagName==='SELECT'?[...e.options].map(o=>({value:o.value,text:o.text})):[],type:e.getAttribute('type'),
   form:!!e.closest('form')};
}"""


def control_directory():
    session = os.environ.get('TRAINING_LIVE_SESSION', '')
    if not SESSION_PATTERN.fullmatch(session):
        raise RuntimeError('LIVE_SESSION_INVALID')
    directory = CONTROL_BASE / ('live-control-' + session)
    for p in [directory, *directory.parents]:
        if p.is_symlink():
            raise RuntimeError('LIVE_CONTROL_PATH_INVALID')
    if not directory.is_dir():
        raise RuntimeError('LIVE_CONTROL_NOT_PREPARED')
    # The Actions runner may use a different Windows identity. Verify the
    # round trip before the original login is ever allowed to request an OTP.
    probe = directory / ('access-probe-' + uuid.uuid4().hex)
    try:
        with probe.open('x', encoding='ascii') as stream:
            stream.write('NON_AUTH_ACCESS_CHECK')
        if probe.read_text(encoding='ascii') != 'NON_AUTH_ACCESS_CHECK':
            raise OSError()
        probe.unlink()
    except OSError:
        raise RuntimeError('LIVE_CONTROL_WRITE_UNAVAILABLE') from None
    return directory


def write_response(directory, value):
    temporary = directory / 'response.tmp'
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(directory / 'response.json')


def run_live_save(page, context, output_dir, downloads, key, report):
    require_permission()
    control = control_directory()
    raw = output_dir / 'target.pdf'
    encrypted = output_dir / 'training-pdf.enc'
    handles, frames, captures, signatures = {}, [], {}, {}
    deadline = time.monotonic() + 1500
    last_id = 0
    write_response(control, {'id': 0, 'status': 'LIVE_READER_READY', 'output_dir': str(output_dir)})

    def safe_frames():
        pages = [p for p in context.pages if not p.is_closed() and (
            p == page or urlsplit(p.url).hostname in {'spring.yidianzhishi.com', 'm.yidianzhishi.com'} or p.opener() == page)]
        for p in pages:
            for f in p.frames:
                auth = f.locator("input[type=password],input[autocomplete=one-time-code]")
                if any(auth.nth(i).is_visible() for i in range(auth.count())):
                    raise RuntimeError('SESSION_REAUTH_REQUIRED')
        check_restrictions(pages, 1)
        return pages

    try:
        while time.monotonic() < deadline:
            request_path = control / 'request.json'
            if not request_path.is_file():
                page.wait_for_timeout(250)
                continue
            request = json.loads(request_path.read_text(encoding='utf-8'))
            request_path.unlink()
            identifier = request.get('id')
            if type(identifier) is not int or identifier <= last_id:
                raise RuntimeError('LIVE_REQUEST_SEQUENCE_INVALID')
            last_id = identifier
            response = {'id': identifier}
            try:
                pages = safe_frames()
                operation = request['operation']
                if operation == 'inspect':
                    handles.clear()
                    frames.clear()
                    observations = []
                    for p in pages:
                        for f in p.frames:
                            frame_index = len(frames)
                            frames.append(f)
                            nodes = []
                            all_nodes = f.locator('body *')
                            for i in range(min(all_nodes.count(), 5000)):
                                e = all_nodes.nth(i)
                                state = e.evaluate(INSPECT)
                                if state:
                                    index = len(handles)
                                    handles[index] = e
                                    state['node'] = index
                                    nodes.append(state)
                            text = f.locator('body').inner_text(timeout=5000) if f.locator('body').count() else ''
                            text = re.sub(r'https?://\S+', '[URL]', text)[:6000]
                            observations.append({'frame': frame_index, 'domain': urlsplit(f.url).hostname,
                                                 'text': text, 'nodes': nodes})
                    response.update(status='OBSERVED', frames=observations, download_count=len(downloads))
                elif operation == 'preview':
                    f = frames[int(request['frame'])]
                    preview = output_dir / ('preview-' + str(identifier) + '.png')
                    f.page.screenshot(path=str(preview), full_page=False)
                    response.update(status='PREVIEW_READY', path=str(preview))
                elif operation == 'resize':
                    width, height = int(request['width']), int(request['height'])
                    if not (800 <= width <= 3000 and 600 <= height <= 4000):
                        raise RuntimeError('VIEWPORT_OUT_OF_RANGE')
                    frames[int(request['frame'])].page.set_viewport_size({'width': width, 'height': height})
                    response['status'] = 'VIEWPORT_SET'
                elif operation == 'click_point':
                    p = frames[int(request['frame'])].page
                    x, y = int(request['x']), int(request['y'])
                    allowed = p.evaluate("""([x,y])=>{const e=document.elementFromPoint(x,y);
                        return !!e && !e.closest('form') && !/登录|验证码|认证|log.?in|sign.?in/i.test(e.innerText||'');}""", [x, y])
                    if not allowed:
                        raise RuntimeError('CONTROL_NOT_ALLOWED')
                    p.mouse.click(x, y)
                    page.wait_for_timeout(750)
                    response['status'] = 'VISIBLE_ACTION_DONE'
                elif operation in {'click', 'fill_page', 'select', 'scroll'}:
                    e = handles[int(request['node'])]
                    state = e.evaluate(INSPECT)
                    if not state or state['form']:
                        raise RuntimeError('VISIBLE_CONTROL_REQUIRED')
                    if operation == 'click':
                        if state['tag'] not in {'BUTTON', 'A', 'IMG', 'CANVAS', 'SPAN', 'DIV'} or re.search(r'登录|验证码|认证|log.?in|sign.?in', state['text'], re.I):
                            raise RuntimeError('CONTROL_NOT_ALLOWED')
                        e.click(timeout=5000)
                    elif operation == 'fill_page':
                        value = str(request['number'])
                        if state['tag'] != 'INPUT' or state['type'] not in {'text', 'number'} or not value.isdigit() or not 1 <= int(value) <= 29:
                            raise RuntimeError('PAGE_INPUT_INVALID')
                        e.fill(value)
                        e.press('Enter')
                    elif operation == 'select':
                        if state['tag'] != 'SELECT' or request['value'] not in [o['value'] for o in state['options']]:
                            raise RuntimeError('VISIBLE_OPTION_REQUIRED')
                        e.select_option(request['value'])
                    else:
                        e.hover(timeout=5000)
                        e.page.mouse.wheel(0, max(-3000, min(3000, int(request['delta']))))
                    page.wait_for_timeout(750)
                    response['status'] = 'VISIBLE_ACTION_DONE'
                elif operation == 'download':
                    if len(downloads) != 1 or downloads[0].failure() is not None:
                        raise RuntimeError('NORMAL_DOWNLOAD_NOT_AVAILABLE')
                    downloads[0].save_as(str(raw))
                    response.update(validate_pdf(raw), status='PDF_READY_FOR_REVIEW', path=str(raw))
                elif operation == 'print':
                    if raw.exists():
                        raw.unlink()
                    frames[int(request['frame'])].page.pdf(path=str(raw), print_background=True,
                        prefer_css_page_size=True, display_header_footer=False)
                    response.update(validate_pdf(raw), status='PDF_READY_FOR_REVIEW', path=str(raw))
                elif operation == 'capture':
                    number = int(request['number'])
                    if not 1 <= number <= 29 or number in captures:
                        raise RuntimeError('PAGE_SEQUENCE_INVALID')
                    e = handles[int(request['node'])]
                    e.scroll_into_view_if_needed(timeout=5000)
                    previous, stable = None, 0
                    png = None
                    for _ in range(40):
                        safe_frames()
                        before = e.evaluate(PAGE_STATE)
                        if not before['full'] or not before['unobstructed'] or not before['contentFits']:
                            raise RuntimeError('PAGE_CLIPPED_OR_OBSCURED')
                        f = e.element_handle().owner_frame()
                        while f.parent_frame:
                            if not f.frame_element().evaluate(FRAME_VISIBLE):
                                raise RuntimeError('READER_FRAME_CLIPPED')
                            f = f.parent_frame
                        if before['ready'] or e.evaluate("e=>e.tagName==='IMG'&&e.complete&&e.naturalWidth>0 || e.tagName==='CANVAS'&&e.width>0&&e.height>0"):
                            png = e.screenshot(type='png', scale='css', timeout=5000)
                            size, digest, signature = image_evidence(png, number)
                            if abs(size[0]-before['width'])>2 or abs(size[1]-before['height'])>2:
                                raise RuntimeError('CAPTURE_DIMENSIONS_MISMATCH')
                            stable = stable+1 if digest == previous and e.evaluate(PAGE_STATE) == before else 1
                            previous = digest
                            if stable >= 3:
                                break
                        page.wait_for_timeout(300)
                    if stable < 3 or png is None:
                        raise RuntimeError('PAGE_NOT_STABLE')
                    if any(duplicate(signature, prior) for prior in signatures.values()):
                        raise RuntimeError('DUPLICATE_PAGE_CAPTURE')
                    path = output_dir / f'page-{number:02d}.png'
                    with path.open('xb') as stream:
                        stream.write(png)
                    captures[number], signatures[number] = path, signature
                    response.update(status='PAGE_CAPTURED', number=number, path=str(path), dimensions=size)
                elif operation == 'assemble':
                    if raw.exists():
                        raw.unlink()
                    response.update(assemble_pdf(sorted(captures.items()), raw), status='PDF_READY_FOR_REVIEW', path=str(raw))
                elif operation == 'deliver':
                    report.update(validate_pdf(raw))
                    report.update(encrypt_pdf(raw, encrypted, key))
                    raw.unlink()
                    for path in captures.values():
                        path.unlink()
                    report.update(status='PDF_CAPTURED_ENCRYPTED', pdf_29_pages_confirmed=True,
                                  download_channel='REVIEWED_VISIBLE_SITE_SAVE')
                    write_response(control, {'id': identifier, 'status': 'ENCRYPTED_DELIVERY_READY'})
                    return report
                elif operation == 'abort':
                    report['status'] = 'LIVE_SAVE_STOPPED'
                    write_response(control, {'id': identifier, 'status': 'STOPPED'})
                    return report
                else:
                    raise RuntimeError('OPERATION_NOT_SUPPORTED')
            except Exception as exc:
                reason = str(exc)
                # Never persist raw exceptions containing addresses or tokens.
                response.update(status='OPERATION_FAILED', reason=reason if re.fullmatch(r'[A-Z_]{3,80}', reason) else 'VISIBLE_OPERATION_FAILED')
                if reason in {'SITE_CAPTURE_OR_COPY_PROHIBITED', 'SESSION_REAUTH_REQUIRED'}:
                    report['status'] = reason
                    write_response(control, response)
                    return report
            write_response(control, response)
        report['status'] = 'LIVE_SAVE_TIME_LIMIT'
        return report
    finally:
        for path in output_dir.glob('*.png'):
            if path.is_file() and not path.is_symlink():
                path.unlink()
