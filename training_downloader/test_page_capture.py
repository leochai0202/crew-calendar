"""Offline screenshot tests use generated pages only; no external requests/login."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageStat
import pymupdf
import page_capture as capture


def page_png(number=1, blank=False):
    image = Image.new('RGB', (800, 1000), 'white')
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 779, 979), outline='black', width=3)
        # Each page has a distinct position and colour; no real company content.
        draw.rectangle((40, 60+number*20, 740, 120+number*20), fill=(number*7 % 255, 90, 120))
        draw.text((220, 500), 'SYNTHETIC WATERMARK', fill=(120, 120, 120))
        draw.text((40, 930), f'PAGE {number}', fill='black')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def empty_locator():
    result = Mock()
    result.count.return_value = 0
    return result


class CaptureTests(unittest.TestCase):
    def fixture(self, number=1):
        viewer, frame, element = Mock(), Mock(), Mock()
        viewer.frames = [frame]
        frame.parent_frame = None
        frame.get_by_text.return_value = empty_locator()
        state = {'number': str(number), 'width': 800, 'height': 1000,
                 'full': True, 'ready': True, 'unobstructed': True}
        element.evaluate.return_value = state
        element.screenshot.return_value = page_png(number)
        return viewer, frame, element, state

    def test_permission_is_required_even_when_no_restriction_visible(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(capture.CaptureFailure, 'CAPTURE_PERMISSION_NOT_CONFIRMED'):
                capture.require_permission()

    def test_visible_copy_restriction_stops_capture(self):
        viewer, frame, element, _ = self.fixture()
        restriction = Mock()
        restriction.count.return_value = 1
        restriction.nth.return_value.is_visible.return_value = True
        frame.get_by_text.return_value = restriction
        with self.assertRaises(capture.CaptureFailure) as caught:
            capture.capture_page(viewer, frame, element, 7, [viewer])
        self.assertEqual(caught.exception.page, 7)
        self.assertEqual(caught.exception.reason, 'SITE_CAPTURE_OR_COPY_PROHIBITED')
        element.screenshot.assert_not_called()

    def test_three_stable_screenshots_preserve_full_page_dimensions(self):
        viewer, frame, element, _ = self.fixture()
        png, signature = capture.capture_page(viewer, frame, element, 1, [viewer])
        self.assertEqual(png, page_png(1))
        self.assertEqual(len(signature), 4096)
        self.assertEqual(element.screenshot.call_count, 3)
        for call in element.screenshot.call_args_list:
            self.assertEqual(call.kwargs, {'type': 'png', 'timeout': 5000, 'scale': 'css'})

    def test_clipping_loading_blank_and_page_number_fail_with_page_number(self):
        for change, reason in (({'full': False}, 'PAGE_CLIPPED_OR_OBSCURED'),
                               ({'ready': False}, 'PAGE_NOT_RENDERED'),
                               ({'number': '8'}, 'PAGE_NUMBER_CHANGED'),
                               ({'contentFits': False}, 'PAGE_CONTENT_CLIPPED'),
                               ({'unobstructed': False}, 'PAGE_CLIPPED_OR_OBSCURED')):
            viewer, frame, element, state = self.fixture(7)
            element.evaluate.return_value = {**state, **change}
            with self.assertRaises(capture.CaptureFailure) as caught:
                capture.capture_page(viewer, frame, element, 7, [viewer])
            self.assertEqual((caught.exception.page, caught.exception.reason), (7, reason))
            element.screenshot.assert_not_called()
        viewer, frame, element, _ = self.fixture(7)
        element.screenshot.return_value = page_png(blank=True)
        with self.assertRaises(capture.CaptureFailure) as caught:
            capture.capture_page(viewer, frame, element, 7, [viewer])
        self.assertEqual((caught.exception.page, caught.exception.reason), (7, 'PAGE_BLANK_OR_CAPTURE_PROTECTED'))

    def test_late_render_waits_and_duplicate_page_is_never_accepted(self):
        viewer, frame, element, state = self.fixture(2)
        element.evaluate.side_effect = [{**state, 'ready': False}, *([state] * 6)]
        capture.capture_page(viewer, frame, element, 2, [viewer])
        self.assertEqual(element.screenshot.call_count, 3)
        viewer, frame, element, _ = self.fixture(2)
        element.screenshot.return_value = page_png(1)
        prior = capture.image_evidence(page_png(1), 1)[2]
        with self.assertRaises(capture.CaptureFailure) as caught:
            capture.capture_page(viewer, frame, element, 2, [viewer], [prior])
        self.assertEqual((caught.exception.page, caught.exception.reason), (2, 'DUPLICATE_PAGE_CAPTURE'))

    def test_iframe_clipping_stops_before_screenshot(self):
        viewer, frame, element, _ = self.fixture()
        frame.parent_frame = Mock()
        frame.frame_element.return_value.evaluate.return_value = False
        with self.assertRaisesRegex(capture.CaptureFailure, 'READER_FRAME_CLIPPED'):
            capture.capture_page(viewer, frame, element, 1, [viewer])
        element.screenshot.assert_not_called()

    def test_page_navigation_uses_input_and_scroll_only(self):
        viewer, frame, element, _ = self.fixture(5)
        field = Mock()
        field.count.return_value = 1
        field.is_visible.return_value = field.is_enabled.return_value = True
        field.get_attribute.return_value = 'number'
        field.evaluate.return_value = False
        element.count.return_value = 1
        frame.locator.side_effect = lambda selector: field if selector == '#pageNumber' else element
        self.assertIs(capture.navigate_page(viewer, frame, 5), element)
        field.fill.assert_called_once_with('5')
        field.press.assert_called_once_with('Enter')
        element.scroll_into_view_if_needed.assert_called_once()

    def test_reader_requires_exact_total_and_unique_document(self):
        viewer, frame, _, _ = self.fixture()
        pages, total = Mock(), Mock()
        pages.count.return_value = 1
        total.count.return_value = 1
        total.is_visible.return_value = True
        frame.locator.side_effect = lambda selector: total if selector == '#numPages' else pages
        total.inner_text.return_value = 'of 29'
        self.assertEqual(capture.identify_reader([viewer]), (viewer, frame))
        total.inner_text.return_value = 'of 28'
        with self.assertRaisesRegex(capture.CaptureFailure, 'READER_TOTAL_NOT_29'):
            capture.identify_reader([viewer])
        total.count.return_value = 0
        with self.assertRaisesRegex(capture.CaptureFailure, 'READER_TOTAL_UNCONFIRMED'):
            capture.identify_reader([viewer])
        viewer.frames = [frame, frame]
        with self.assertRaisesRegex(capture.CaptureFailure, 'READER_AMBIGUOUS'):
            capture.identify_reader([viewer])

    def test_virtualized_page_waits_for_requested_number(self):
        viewer, frame, element, _ = self.fixture(9)
        frame.locator.return_value = empty_locator()
        with patch.object(capture, 'page_locator', side_effect=[
                capture.CaptureFailure(9, 'PAGE_MISSING_OR_AMBIGUOUS'), element]):
            self.assertIs(capture.navigate_page(viewer, frame, 9), element)
        viewer.wait_for_timeout.assert_called_once_with(250)

    def test_29_images_assemble_in_order_and_partial_sequence_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = []
            for number in range(1, 30):
                path = root / f'{number}.png'
                path.write_bytes(page_png(number))
                images.append((number, path))
            result = capture.assemble_pdf(images, root / 'complete.pdf')
            self.assertEqual(result['pdf_pages_rendered'], 29)
            with pymupdf.open(root / 'complete.pdf') as document:
                self.assertEqual(document.page_count, 29)
                for index, page in enumerate(document):
                    self.assertEqual(len(page.get_images()), 1)
                    self.assertEqual(page.rect.width / page.rect.height, .8)
            with self.assertRaisesRegex(capture.CaptureFailure, 'CAPTURE_SEQUENCE_INCOMPLETE'):
                capture.assemble_pdf(images[:-1], root / 'partial.pdf')
            self.assertFalse((root / 'partial.pdf').exists())

    def test_failed_page_cleans_owned_screenshots_without_padding(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'TRAINING_CAPTURE_ALLOWED': '1'}):
            root = Path(directory)
            viewer, frame, element, _ = self.fixture()
            viewer.viewport_size = {'width': 1400, 'height': 1000}
            frame.locator.return_value = empty_locator()
            def page_result(viewer, frame, element, number, viewers, signatures):
                if number == 4:
                    raise capture.CaptureFailure(4, 'PAGE_NOT_RENDERED')
                png = page_png(number)
                return png, capture.image_evidence(png, number)[2]
            with patch.object(capture, 'identify_reader', return_value=(viewer, frame)), \
                    patch.object(capture, 'navigate_page', return_value=element), \
                    patch.object(capture, 'capture_page', side_effect=page_result):
                with self.assertRaises(capture.CaptureFailure) as caught:
                    capture.capture_reader_pdf([viewer], root, root / 'target.pdf')
            self.assertEqual(caught.exception.page, 4)
            self.assertFalse((root / 'target.pdf').exists())
            self.assertFalse((root / 'screenshots').exists())

    def test_cleanup_failure_preserves_original_failed_page(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'TRAINING_CAPTURE_ALLOWED': '1'}):
            root = Path(directory)
            viewer, frame, element, _ = self.fixture()
            viewer.viewport_size = None
            frame.locator.return_value = empty_locator()
            with patch.object(capture, 'identify_reader', return_value=(viewer, frame)), \
                    patch.object(capture, 'navigate_page', return_value=element), \
                    patch.object(capture, 'capture_page', side_effect=capture.CaptureFailure(1, 'PAGE_NOT_RENDERED')), \
                    patch.object(Path, 'rmdir', side_effect=PermissionError('synthetic private path')):
                with self.assertRaises(capture.CaptureFailure) as caught:
                    capture.capture_reader_pdf([viewer], root, root / 'target.pdf')
            self.assertEqual((caught.exception.page, caught.exception.reason), (1, 'PAGE_NOT_RENDERED'))
            self.assertTrue(caught.exception.cleanup_failed)
            self.assertNotIn('private path', str(caught.exception))


@unittest.skipUnless(os.environ.get('TRAINING_OFFLINE_BROWSER_TEST') == '1', 'Opt-in local synthetic browser test')
class OfflineBrowserTests(unittest.TestCase):
    def test_continuous_scrolling_full_pages_watermarks_and_no_toolbar(self):
        from playwright.sync_api import sync_playwright
        runtime = Path(__file__).parent / '.runtime'
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime, prefix='capture-browser-') as directory, \
                patch.dict(os.environ, {'TRAINING_CAPTURE_ALLOWED': '1'}), sync_playwright() as playwright:
            root = Path(directory)
            context = playwright.chromium.launch_persistent_context(str(root / 'edge-profile'), channel='msedge', headless=True)
            try:
                context.route('**/*', lambda route: route.abort())
                page = context.pages[0]
                page.set_viewport_size({'width': 1800, 'height': 2400})
                page.set_content('''<style>body{margin:0}#toolbar{height:60px;background:red}
                #viewer{height:calc(100vh - 60px);overflow:auto}.page{width:3000px;height:3750px;margin:20px auto;position:relative}
                canvas{display:block;width:100%;height:100%}.watermark{position:absolute;left:220px;top:500px;color:#777;font:25px sans-serif;pointer-events:none}</style>
                <div id=toolbar>NOT DOCUMENT CONTENT <span id=numPages>of 29</span><input id=pageNumber type=number>
                <select id=scaleSelect onchange="document.querySelectorAll('.page').forEach(e=>{e.style.width='800px';e.style.height='1000px'})">
                <option value=oversized>Oversized</option><option value=page-fit>Fit page</option></select></div><div id=viewer></div>
                <script>for(let n=1;n<=29;n++){let e=document.createElement('div');e.className='page';e.dataset.pageNumber=n;
                let c=document.createElement('canvas');c.width=800;c.height=1000;let x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,800,1000);
                x.strokeStyle='black';x.strokeRect(2,2,796,996);x.fillStyle=`rgb(${n*7%255},90,120)`;x.fillRect(40,60+n*20,700,60);
                x.fillStyle='black';x.font='30px sans-serif';x.fillText('SYNTHETIC PAGE '+n,40,940);
                let w=document.createElement('div');w.className='watermark';w.textContent='VISIBLE WATERMARK';e.append(c,w);viewer.append(e);}</script>''')
                output = root / 'capture'
                output.mkdir()
                result = capture.capture_reader_pdf([page], output, output / 'target.pdf')
                self.assertEqual(result['captured_pages'], 29)
                self.assertEqual(page.locator('#scaleSelect').input_value(), 'page-fit')
                self.assertEqual(page.locator('#pageNumber').input_value(), '29')
                self.assertFalse((output / 'screenshots').exists())
                with pymupdf.open(output / 'target.pdf') as document:
                    for number, pdf_page in enumerate(document, 1):
                        pixmap = pdf_page.get_pixmap(matrix=pymupdf.Matrix(4/3, 4/3), alpha=False)
                        image = Image.frombytes('RGB', [pixmap.width, pixmap.height], pixmap.samples)
                        self.assertEqual(image.size, (800, 1000))
                        self.assertNotEqual(image.getpixel((2, 2)), (255, 255, 255))
                        self.assertNotEqual(image.getpixel((2, 997)), (255, 255, 255))
                        self.assertGreater(ImageStat.Stat(image.crop((220, 500, 500, 550))).stddev[0], 3)
                        self.assertNotIn((255, 0, 0), image.get_flattened_data())
                from cryptography.hazmat.primitives.asymmetric import rsa
                from cryptography.hazmat.primitives import serialization
                from private_delivery import encrypt_pdf, decrypt_pdf
                key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
                private = root / 'synthetic-test-key.pem'
                private.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
                encrypt_pdf(output / 'target.pdf', output / 'test.enc', key.public_key())
                decrypt_pdf(output / 'test.enc', private, output / 'recovered.pdf')
                self.assertEqual((output / 'recovered.pdf').read_bytes(), (output / 'target.pdf').read_bytes())
            finally:
                context.close()


if __name__ == '__main__':
    unittest.main()
