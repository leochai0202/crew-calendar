"""Capture only normally displayed document pages; never extract PDF internals."""
import hashlib
import io
import os
from pathlib import Path
import re
import sys

from PIL import Image, ImageStat
import pymupdf

from pdf_validation import validate_pdf

PAGE_SELECTOR = '.page[data-page-number], .react-pdf__Page[data-page-number]'
RESTRICTIONS = re.compile(
    r'禁止截[屏图]|不允许截[屏图]|不可截[屏图]|截[屏图](?:已禁用|保护)|禁止复制|不允许复制|'
    r'禁止保存|不允许保存|禁止下载|不允许下载|仅限在线阅读|仅供在线阅读|'
    r'screen(?:shot| capture).*(?:prohibited|disabled|not allowed)|copy(?:ing)? (?:is )?not allowed|DRM', re.I)

# Geometry/readiness only. No canvas pixels, app state, styles or watermark edits.
PAGE_STATE = """element => {
    const r = element.getBoundingClientRect();
    let left=0, top=0, right=innerWidth, bottom=innerHeight;
    for (let p=element.parentElement; p; p=p.parentElement) {
        const s=getComputedStyle(p), b=p.getBoundingClientRect();
        if (/(hidden|clip|auto|scroll)/.test(s.overflowX)) {
            left=Math.max(left,b.left+p.clientLeft); right=Math.min(right,b.left+p.clientLeft+p.clientWidth);
        }
        if (/(hidden|clip|auto|scroll)/.test(s.overflowY)) {
            top=Math.max(top,b.top+p.clientTop); bottom=Math.min(bottom,b.top+p.clientTop+p.clientHeight);
        }
    }
    const assets=[...element.querySelectorAll('canvas,img')];
    const loading=[...element.querySelectorAll('.loadingIcon,[aria-busy="true"],.react-pdf__message')]
        .some(n=>n.getBoundingClientRect().width>0 && getComputedStyle(n).visibility!=='hidden');
    const visibleAssets=assets.filter(n=>n.getBoundingClientRect().width>0 && getComputedStyle(n).visibility!=='hidden');
    const ready=visibleAssets.length>0 && !loading && visibleAssets.every(n=>
        n.tagName==='IMG' ? n.complete && n.naturalWidth>0 : n.width>0 && n.height>0);
    const contentFits=visibleAssets.every(n=>{const b=n.getBoundingClientRect();
        return b.left>=r.left-1 && b.top>=r.top-1 && b.right<=r.right+1 && b.bottom<=r.bottom+1;});
    const points=[[r.left+2,r.top+2],[r.right-2,r.top+2],[r.left+2,r.bottom-2],
                  [r.right-2,r.bottom-2],[(r.left+r.right)/2,(r.top+r.bottom)/2]];
    const unobstructed=points.every(([x,y])=>{const n=document.elementFromPoint(x,y); return n && (n===element || element.contains(n));});
    return {number:element.getAttribute('data-page-number'), width:r.width,height:r.height,
            full:r.left>=left-1 && r.top>=top-1 && r.right<=right+1 && r.bottom<=bottom+1,
            ready, unobstructed, contentFits};
}"""
FRAME_VISIBLE = """element => {
    const r=element.getBoundingClientRect();
    let left=0,top=0,right=innerWidth,bottom=innerHeight;
    for(let p=element.parentElement;p;p=p.parentElement){
        const s=getComputedStyle(p),b=p.getBoundingClientRect();
        if(/(hidden|clip|auto|scroll)/.test(s.overflowX)){left=Math.max(left,b.left+p.clientLeft);right=Math.min(right,b.left+p.clientLeft+p.clientWidth);}
        if(/(hidden|clip|auto|scroll)/.test(s.overflowY)){top=Math.max(top,b.top+p.clientTop);bottom=Math.min(bottom,b.top+p.clientTop+p.clientHeight);}
    }
    return r.left>=left-1 && r.top>=top-1 && r.right<=right+1 && r.bottom<=bottom+1;
}"""


class CaptureFailure(RuntimeError):
    def __init__(self, page, reason):
        self.page = page
        self.reason = reason
        super().__init__(reason)


def require_permission():
    if os.environ.get('TRAINING_CAPTURE_ALLOWED') != '1':
        raise CaptureFailure(1, 'CAPTURE_PERMISSION_NOT_CONFIRMED')


def check_restrictions(viewers, number):
    for viewer in viewers:
        for frame in viewer.frames:
            matches = frame.get_by_text(RESTRICTIONS)
            if any(matches.nth(i).is_visible() for i in range(matches.count())):
                raise CaptureFailure(number, 'SITE_CAPTURE_OR_COPY_PROHIBITED')


def identify_reader(viewers):
    readers = []
    for viewer in viewers:
        for frame in viewer.frames:
            if frame.locator(PAGE_SELECTOR).count():
                readers.append((viewer, frame))
    if len(readers) != 1:
        raise CaptureFailure(1, 'READER_PAGE_STRUCTURE_UNSUPPORTED' if not readers else 'READER_AMBIGUOUS')
    viewer, frame = readers[0]
    totals = frame.locator('#numPages')
    if totals.count() == 1 and totals.is_visible():
        numbers = re.findall(r'\d+', totals.inner_text())
        if numbers != ['29']:
            raise CaptureFailure(1, 'READER_TOTAL_NOT_29')
    else:
        pages = frame.locator(PAGE_SELECTOR)
        numbers = [pages.nth(i).get_attribute('data-page-number') for i in range(pages.count())]
        if len(numbers) != 29 or set(numbers) != {str(i) for i in range(1, 30)}:
            raise CaptureFailure(1, 'READER_TOTAL_UNCONFIRMED')
    return viewer, frame


def page_locator(frame, number):
    matches = frame.locator(f'.page[data-page-number="{number}"], .react-pdf__Page[data-page-number="{number}"]')
    if matches.count() != 1:
        raise CaptureFailure(number, 'PAGE_MISSING_OR_AMBIGUOUS')
    return matches


def navigate_page(viewer, frame, number):
    field = frame.locator('#pageNumber')
    if field.count() == 1 and field.is_visible() and field.is_enabled():
        # Normal reader navigation only; never fill an authentication form.
        if field.get_attribute('type') not in {'number', 'text'} or field.evaluate("e => !!e.closest('form')"):
            raise CaptureFailure(number, 'PAGE_NAVIGATION_UNSAFE')
        field.fill(str(number))
        field.press('Enter')
    for _ in range(20):
        try:
            element = page_locator(frame, number)
            element.scroll_into_view_if_needed(timeout=1500)
            return element
        except CaptureFailure:
            viewer.wait_for_timeout(250)
    raise CaptureFailure(number, 'PAGE_MISSING_OR_AMBIGUOUS')


def image_evidence(png, number):
    with Image.open(io.BytesIO(png)) as source:
        image = source.convert('RGB')
        if image.width < 600 or image.height < 300:
            raise CaptureFailure(number, 'CAPTURE_RESOLUTION_TOO_LOW')
        grey = image.convert('L').resize((128, 128))
        histogram = grey.histogram()
        # Uniform/near-uniform captures include common screenshot protection.
        if ImageStat.Stat(grey).stddev[0] < 3 or max(histogram) / (128 * 128) > .985:
            raise CaptureFailure(number, 'PAGE_BLANK_OR_CAPTURE_PROTECTED')
        small = grey.resize((64, 64)).tobytes()
        return image.size, hashlib.sha256(image.tobytes()).digest(), small


def duplicate(a, b):
    differences = [abs(x-y) for x, y in zip(a, b)]
    return sum(differences) / len(differences) <= .25 and sum(x > 3 for x in differences) / len(differences) < .01


def capture_page(viewer, frame, element, number, viewers, previous_signatures=()):
    previous, stable = None, 0
    last_reason = 'PAGE_NOT_RENDERED'
    for _ in range(40):
        check_restrictions(viewers, number)
        state = element.evaluate(PAGE_STATE)
        if state.get('number') != str(number):
            raise CaptureFailure(number, 'PAGE_NUMBER_CHANGED')
        if not state.get('full') or not state.get('unobstructed'):
            last_reason = 'PAGE_CLIPPED_OR_OBSCURED'
            stable, previous = 0, None
        elif not state.get('contentFits', True):
            last_reason = 'PAGE_CONTENT_CLIPPED'
            stable, previous = 0, None
        elif not state.get('ready'):
            last_reason = 'PAGE_NOT_RENDERED'
            stable, previous = 0, None
        else:
            ancestor = frame
            while ancestor.parent_frame is not None:
                embedding = ancestor.frame_element()
                if not embedding.evaluate(FRAME_VISIBLE):
                    raise CaptureFailure(number, 'READER_FRAME_CLIPPED')
                ancestor = ancestor.parent_frame
            # Element screenshot preserves composited watermarks and clips only
            # to the entire page container, after all clipping checks passed.
            png = element.screenshot(type='png', timeout=5000, scale='css')
            after = element.evaluate(PAGE_STATE)
            if after != state:
                stable, previous = 0, None
                last_reason = 'PAGE_CHANGED_DURING_CAPTURE'
            else:
                try:
                    size, digest, signature = image_evidence(png, number)
                except CaptureFailure as exc:
                    last_reason = exc.reason
                    stable, previous = 0, None
                else:
                    if abs(size[0]-state['width']) > 2 or abs(size[1]-state['height']) > 2:
                        raise CaptureFailure(number, 'CAPTURE_DIMENSIONS_MISMATCH')
                    stable = stable + 1 if digest == previous else 1
                    repeated = any(duplicate(signature, prior) for prior in previous_signatures)
                    last_reason = 'DUPLICATE_PAGE_CAPTURE' if repeated else 'PAGE_RENDER_UNSTABLE'
                    previous = digest
                    if stable >= 3:
                        if repeated:
                            last_reason = 'DUPLICATE_PAGE_CAPTURE'
                            stable, previous = 0, None
                            viewer.wait_for_timeout(250)
                            continue
                        return png, signature
        viewer.wait_for_timeout(250)
    raise CaptureFailure(number, last_reason)


def assemble_pdf(images, destination):
    if [number for number, _ in images] != list(range(1, 30)):
        raise CaptureFailure(1, 'CAPTURE_SEQUENCE_INCOMPLETE')
    with pymupdf.open() as document:
        for number, path in images:
            with Image.open(path) as image:
                width, height = image.size
            page = document.new_page(width=width * .75, height=height * .75)
            page.insert_image(page.rect, filename=str(path), keep_proportion=True)
        document.save(str(destination), deflate=True)
    return validate_pdf(destination)


def capture_reader_pdf(viewers, output_dir, destination):
    require_permission()
    check_restrictions(viewers, 1)
    viewer, frame = identify_reader(viewers)
    screenshot_dir = Path(output_dir) / 'screenshots'
    screenshot_dir.mkdir(exist_ok=False)
    images, signatures = [], []
    old_viewport = viewer.viewport_size
    try:
        try:
            viewer.set_viewport_size({'width': 1800, 'height': 2400})
            fit = frame.locator('#scaleSelect')
            if fit.count() == 1 and fit.is_visible() and fit.is_enabled() and fit.locator('option[value="page-fit"]').count() == 1:
                fit.select_option('page-fit')  # Visible site UI; no injected zoom/style.
        except Exception:
            raise CaptureFailure(1, 'READER_PREPARATION_FAILED') from None
        for number in range(1, 30):
            try:
                check_restrictions(viewers, number)
                element = navigate_page(viewer, frame, number)
                png, signature = capture_page(viewer, frame, element, number, viewers, signatures)
                if any(duplicate(signature, prior) for prior in signatures):
                    raise CaptureFailure(number, 'DUPLICATE_PAGE_CAPTURE')
                path = screenshot_dir / f'page-{number:02d}.png'
                with path.open('xb') as stream:
                    images.append((number, path))
                    stream.write(png)
                signatures.append(signature)
            except CaptureFailure:
                raise
            except Exception:
                raise CaptureFailure(number, 'PAGE_CAPTURE_FAILED') from None
        result = assemble_pdf(images, destination)
        result.update(captured_pages=29, pdf_kind='SCREENSHOT_IMAGE_PDF', capture_sequence_verified=True)
        return result
    finally:
        active_error = sys.exc_info()[1]
        cleanup_failed = False
        try:
            if old_viewport:
                viewer.set_viewport_size(old_viewport)
        except Exception:
            pass  # The existing context finally closes the test browser.
        # Only this function's numbered screenshots; no recursive cleanup.
        for _, path in images:
            try:
                path.unlink()
            except OSError:
                cleanup_failed = True
        try:
            screenshot_dir.rmdir()
        except OSError:
            cleanup_failed = True
        if cleanup_failed:
            if isinstance(active_error, CaptureFailure):
                active_error.cleanup_failed = True
            elif active_error is None:
                raise CaptureFailure(29, 'SCREENSHOT_CLEANUP_FAILED')
