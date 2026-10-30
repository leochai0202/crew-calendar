"""Synthetic PDFs, browser events and ephemeral keys only; no login/network."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pymupdf
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import pdf_download as download
import pdf_validation as validation
import private_delivery as delivery


def synthetic_pdf(count=29):
    with pymupdf.open() as document:
        for number in range(count):
            page = document.new_page(width=200, height=200)
            page.insert_text((20, 50), f"Synthetic offline page {number + 1}")
        return document.tobytes()


class PdfFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = synthetic_pdf()
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

    def test_real_file_parses_and_renders_all_29_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "synthetic.pdf"
            pdf.write_bytes(self.pdf)
            self.assertEqual(validation.validate_pdf(pdf), {
                "pdf_file_validated": True, "pdf_page_count": 29, "pdf_pages_rendered": 29})

    def test_html_truncation_malformed_and_wrong_page_count_rejected(self):
        cases = [(b"<html>login page</html>", "NOT_A_PDF"),
                 (self.pdf[:-20], "PDF_TRUNCATED"), (synthetic_pdf(28), "PDF_PAGE_COUNT_MISMATCH"),
                 (b"%PDF-1.7\nbroken\n%%EOF", "PDF_PARSE_OR_RENDER_FAILED")]
        for data, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                pdf = Path(directory) / "synthetic.pdf"
                pdf.write_bytes(data)
                with self.assertRaisesRegex(validation.PdfValidationError, reason):
                    validation.validate_pdf(pdf)

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(validation.PdfValidationError, "PDF_FILE_MISSING"):
                validation.validate_pdf(Path(directory) / "missing.pdf")

    def test_encrypted_document_is_not_decrypted_or_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "encrypted.pdf"
            with pymupdf.open(stream=self.pdf, filetype="pdf") as doc:
                doc.save(pdf, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="synthetic", user_pw="synthetic")
            with self.assertRaisesRegex(validation.PdfValidationError, "PDF_ENCRYPTION_OR_DRM_UNSUPPORTED"):
                validation.validate_pdf(pdf)

    def test_encrypted_delivery_roundtrip_and_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf, package, private = root / "source.pdf", root / "training-pdf.enc", root / "private.pem"
            pdf.write_bytes(self.pdf)
            private.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            result = delivery.encrypt_pdf(pdf, package, self.key.public_key())
            self.assertFalse(result["delivery_completed"])
            self.assertNotIn(b"%PDF-", package.read_bytes())
            recovered = root / "recovered.pdf"
            delivery.decrypt_pdf(package, private, recovered)
            self.assertEqual(recovered.read_bytes(), self.pdf)
            damaged = bytearray(package.read_bytes())
            damaged[-1] ^= 1
            package.write_bytes(damaged)
            failed = root / "failed.pdf"
            with self.assertRaises(Exception):
                delivery.decrypt_pdf(package, private, failed)
            self.assertFalse(failed.exists())

    def test_wrong_recipient_and_existing_output_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf, package = root / "source.pdf", root / "training-pdf.enc"
            pdf.write_bytes(self.pdf)
            delivery.encrypt_pdf(pdf, package, self.key.public_key())
            other = rsa.generate_private_key(public_exponent=65537, key_size=4096)
            private = root / "other.pem"
            private.write_bytes(other.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            with self.assertRaisesRegex(RuntimeError, "DELIVERY_RECIPIENT_MISMATCH"):
                delivery.decrypt_pdf(package, private, root / "result.pdf")
            with self.assertRaisesRegex(RuntimeError, "DELIVERY_DESTINATION_EXISTS"):
                delivery.decrypt_pdf(package, private, pdf)
            self.assertEqual(pdf.read_bytes(), self.pdf)


class SiteDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = synthetic_pdf()
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

    def controls(self, *items):
        result = Mock()
        result.count.return_value = len(items)
        result.nth.side_effect = lambda i: items[i]
        return result

    def fixture(self, *, channel="event", allowed=True, restriction=False, disabled=False, ambiguous=False, data=None):
        opened = [False]
        callbacks = {}
        page, context, frame = Mock(), Mock(), Mock()
        page.frames, context.pages = [frame], [page]
        page.on.side_effect = lambda event, callback: callbacks.update({event: callback})
        title = Mock()
        title.is_visible.return_value = True
        title.click.side_effect = lambda **kwargs: opened.__setitem__(0, True)
        page.get_by_text.return_value = self.controls(title)
        button = Mock()
        button.is_visible.return_value = True
        button.is_enabled.return_value = not disabled
        button.get_attribute.return_value = None
        button.evaluate.return_value = False
        forbidden = Mock()
        forbidden.is_visible.return_value = True
        frame.get_by_text.side_effect = lambda pattern: self.controls(forbidden) if restriction else self.controls()
        frame.get_by_role.side_effect = lambda role, name: self.controls(
            *([button] * (2 if ambiguous else 1) if opened[0] and allowed and role == "button" else []))
        downloaded = Mock()
        downloaded.failure.return_value = None
        downloaded.save_as.side_effect = lambda path: Path(path).write_bytes(self.pdf if data is None else data)
        response = Mock(status=200, headers={"content-type": "application/pdf"})
        response.request.is_navigation_request.return_value = True
        response.body.return_value = self.pdf if data is None else data
        def click(**kwargs):
            if channel == "event":
                callbacks["download"](downloaded)
            elif channel == "response":
                callbacks["response"](response)
        button.click.side_effect = click
        frame.evaluate.side_effect = AssertionError("PDF.js data must not be read")
        return page, context, title, button, downloaded, response

    def test_download_event_saves_validates_encrypts_and_removes_plaintext(self):
        for channel in ("event", "response"):
            with self.subTest(channel=channel), tempfile.TemporaryDirectory() as directory:
                page, context, title, button, saved, response = self.fixture(channel=channel)
                destination = Path(directory) / "new-download"
                with patch.object(download, "recipient", return_value=self.key.public_key()):
                    report = download.download_target_pdf(page, context, destination, "target.pdf")
                self.assertEqual(report["status"], "PDF_DOWNLOADED_ENCRYPTED")
                self.assertEqual(report["pdf_page_count"], 29)
                self.assertEqual(report["pdf_pages_rendered"], 29)
                self.assertFalse(report["delivery_completed"])
                self.assertTrue((destination / "training-pdf.enc").is_file())
                self.assertFalse((destination / "target.pdf").exists())
                title.click.assert_called_once()
                button.click.assert_called_once()
                page.frames[0].evaluate.assert_not_called()
                context.request.get.assert_not_called()
                self.assertNotIn("https://", str(report))

    def test_capture_without_download_button_encrypts_valid_pdf(self):
        import page_capture
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'TRAINING_CAPTURE_MODE': '1', 'TRAINING_CAPTURE_ALLOWED': '1'}):
            page, context, title, button, saved, response = self.fixture(allowed=False)
            destination = Path(directory) / 'capture'
            def capture(viewers, output, raw):
                raw.write_bytes(self.pdf)
                return {**validation.validate_pdf(raw), 'captured_pages': 29}
            with patch.object(download, 'recipient', return_value=self.key.public_key()), \
                    patch.object(page_capture, 'identify_reader', side_effect=[
                        page_capture.CaptureFailure(1, 'READER_TOTAL_UNCONFIRMED'), None]), \
                    patch.object(page_capture, 'capture_reader_pdf', side_effect=capture):
                result = download.download_target_pdf(page, context, destination, 'target.pdf')
            self.assertEqual(result['status'], 'PDF_CAPTURED_ENCRYPTED')
            self.assertEqual(result['captured_pages'], 29)
            self.assertFalse(result['delivery_completed'])
            self.assertTrue((destination / 'training-pdf.enc').is_file())
            self.assertFalse((destination / 'target.pdf').exists())
            title.click.assert_called_once()
            button.click.assert_not_called()
            response.body.assert_not_called()
            context.request.get.assert_not_called()
            page.wait_for_timeout.assert_called_once_with(500)

    def test_failed_capture_reports_page_and_never_delivers_partial_pdf(self):
        import page_capture
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'TRAINING_CAPTURE_MODE': '1', 'TRAINING_CAPTURE_ALLOWED': '1'}):
            page, context, *_ = self.fixture(allowed=False)
            destination = Path(directory) / 'capture'
            with patch.object(download, 'recipient', return_value=self.key.public_key()), \
                    patch.object(page_capture, 'identify_reader'), \
                    patch.object(page_capture, 'capture_reader_pdf', side_effect=page_capture.CaptureFailure(17, 'PAGE_NOT_RENDERED')):
                result = download.download_target_pdf(page, context, destination, 'target.pdf')
            self.assertEqual(result['status'], 'PAGE_CAPTURE_FAILED')
            self.assertEqual(result['failed_page'], 17)
            self.assertEqual(result['capture_failure_reason'], 'PAGE_NOT_RENDERED')
            self.assertFalse((destination / 'training-pdf.enc').exists())
            self.assertFalse((destination / 'target.pdf').exists())

    def test_restrictions_disabled_ambiguous_and_absent_controls_stop(self):
        for options, expected in (({"restriction": True}, "SITE_DOWNLOAD_PROHIBITED"),
                                  ({"disabled": True}, "SITE_DOWNLOAD_DISABLED"),
                                  ({"ambiguous": True}, "DOWNLOAD_CONTROL_AMBIGUOUS"),
                                  ({"allowed": False}, "DOWNLOAD_CONTROL_NOT_FOUND"),
                                  ({"channel": "none"}, "DOWNLOAD_ACTION_NO_FILE")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                page, context, title, button, saved, response = self.fixture(**options)
                destination = Path(directory) / "new-download"
                with patch.object(download, "recipient", return_value=self.key.public_key()):
                    report = download.download_target_pdf(page, context, destination, "target.pdf")
                self.assertEqual(report["status"], expected)
                saved.save_as.assert_not_called()
                response.body.assert_not_called()
                self.assertFalse((destination / "training-pdf.enc").exists())

    def test_invalid_download_never_becomes_delivery_package(self):
        with tempfile.TemporaryDirectory() as directory:
            page, context, *_ = self.fixture(data=b"<html>login</html>")
            destination = Path(directory) / "new-download"
            with patch.object(download, "recipient", return_value=self.key.public_key()):
                report = download.download_target_pdf(page, context, destination, "target.pdf")
            self.assertEqual(report["status"], "NOT_A_PDF")
            self.assertEqual(list(destination.iterdir()), [])

    def test_direct_site_download_needs_no_viewer_or_download_button(self):
        with tempfile.TemporaryDirectory() as directory:
            page, context, title, button, saved, response = self.fixture(allowed=False)
            def click(**kwargs):
                callback = [c.args[1] for c in page.on.call_args_list if c.args[0] == "download"][0]
                callback(saved)
            title.click.side_effect = click
            with patch.object(download, "recipient", return_value=self.key.public_key()):
                result = download.download_target_pdf(page, context, Path(directory) / "new", "target.pdf")
            self.assertEqual(result["status"], "PDF_DOWNLOADED_ENCRYPTED")
            button.click.assert_not_called()
            saved.save_as.assert_called_once()

    def test_rendering_pdf_response_is_not_a_download_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            page, context, title, button, saved, response = self.fixture(allowed=False)
            def render(**kwargs):
                callback = [c.args[1] for c in page.on.call_args_list if c.args[0] == "response"][0]
                callback(response)
            title.click.side_effect = render
            with patch.object(download, "recipient", return_value=self.key.public_key()):
                result = download.download_target_pdf(page, context, Path(directory) / "new", "target.pdf")
            self.assertEqual(result["status"], "DOWNLOAD_CONTROL_NOT_FOUND")
            response.body.assert_not_called()
            saved.save_as.assert_not_called()

    def test_multiple_downloads_and_failed_download_are_refused(self):
        for multiple in (False, True):
            with self.subTest(multiple=multiple), tempfile.TemporaryDirectory() as directory:
                page, context, title, button, saved, response = self.fixture()
                if multiple:
                    def click(**kwargs):
                        callback = [c.args[1] for c in page.on.call_args_list if c.args[0] == "download"][0]
                        callback(saved)
                        callback(Mock())
                    button.click.side_effect = click
                else:
                    saved.failure.return_value = "synthetic failure with private URL"
                with patch.object(download, "recipient", return_value=self.key.public_key()):
                    result = download.download_target_pdf(page, context, Path(directory) / "new", "target.pdf")
                self.assertEqual(result["status"], "MULTIPLE_DOWNLOADS_REFUSED" if multiple else "SITE_DOWNLOAD_FAILED")
                saved.save_as.assert_not_called()
                self.assertNotIn("private URL", str(result))

    def test_existing_directory_is_not_cleaned_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            page, context, *_ = self.fixture()
            sentinel = Path(directory) / "target.pdf"
            sentinel.write_bytes(b"keep existing file")
            report = download.download_target_pdf(page, context, Path(directory), "target.pdf")
            self.assertEqual(report["status"], "DOWNLOAD_OR_ENCRYPTION_FAILED")
            self.assertEqual(sentinel.read_bytes(), b"keep existing file")


if __name__ == "__main__":
    unittest.main()
