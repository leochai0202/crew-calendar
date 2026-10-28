"""Save a site download or explicitly permitted visible-page captures."""
import re
import os
from pathlib import Path

from pdf_validation import PdfValidationError, validate_pdf
from private_delivery import encrypt_pdf, recipient

DOWNLOAD_NAME = re.compile(r"^(?:下载|下载文件|下载原文件|下载\s*PDF|保存|保存文件|保存\s*PDF|导出\s*PDF|Download|Save(?: file)?)$", re.I)
RESTRICTION = re.compile(r"禁止下载|不允许下载|不支持下载|不可下载|不能下载|不提供下载|下载已禁用|无下载权限|下载权限不足|禁止保存|禁止导出|仅限在线阅读|仅供在线阅读|仅支持在线(?:阅读|预览)|download(?:ing)? (?:is )?(?:disabled|not allowed)", re.I)


def prepare_download():
    # Run before authenticating: missing dependencies/key must not consume OTP.
    import pymupdf
    import pypdf
    recipient()
    if os.environ.get('TRAINING_CAPTURE_MODE') == '1':
        from page_capture import require_permission
        require_permission()


def inspect_controls(viewers):
    controls, disabled = [], False
    for viewer in viewers:
        for frame in viewer.frames:
            forbidden = frame.get_by_text(RESTRICTION)
            if any(forbidden.nth(i).is_visible() for i in range(forbidden.count())):
                return None, "SITE_DOWNLOAD_PROHIBITED"
            for role in ("button", "link"):
                matches = frame.get_by_role(role, name=DOWNLOAD_NAME)
                for i in range(matches.count()):
                    control = matches.nth(i)
                    if not control.is_visible():
                        continue
                    if not control.is_enabled() or control.get_attribute("aria-disabled") == "true":
                        disabled = True
                        continue
                    if control.evaluate("element => !!element.closest('form')"):
                        continue
                    controls.append(control)
    if len(controls) == 1 and not disabled:
        return controls[0], None
    return None, ("SITE_DOWNLOAD_DISABLED" if disabled else
                  "DOWNLOAD_CONTROL_AMBIGUOUS" if len(controls) > 1 else "DOWNLOAD_CONTROL_NOT_FOUND")


def download_target_pdf(page, context, output_dir, target):
    report = {"status": "DOWNLOAD_NOT_COMPLETED", "pdf_file_validated": False,
              "pdf_29_pages_confirmed": False, "target_pdf_name_confirmed": False,
              "delivery_completed": False, "delivery_status": "NOT_READY"}
    output_dir = Path(output_dir)
    raw = output_dir / "target.pdf"
    encrypted = output_dir / "training-pdf.enc"
    downloads, responses, listeners = [], [], []
    owned = False
    allow_response = [False]
    previous_pages = list(context.pages)

    def downloaded(download):
        if downloads:
            download.cancel()
        downloads.append(download)

    def responded(response):
        # Only a normal navigation caused by the visible Download/Save action.
        # Never enumerate viewer caches, intercept rendering XHR or infer URLs.
        if not allow_response[0] or responses:
            return
        try:
            if (response.request.is_navigation_request() and response.status == 200 and
                    "attachment" not in response.headers.get("content-disposition", "").lower() and
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/pdf"):
                responses.append(response)
        except Exception:
            pass

    def watch(candidate):
        candidate.on("download", downloaded)
        candidate.on("response", responded)
        listeners.append(candidate)

    try:
        output_dir.mkdir(parents=True, exist_ok=False)
        owned = True
        key = recipient()
        targets = page.get_by_text(target, exact=True)
        visible = [targets.nth(i) for i in range(targets.count()) if targets.nth(i).is_visible()]
        if len(visible) != 1:
            report["status"] = "TARGET_LINK_NOT_UNIQUE"
            return report
        # A restriction on the task itself is also authoritative.
        _, obstacle = inspect_controls([page])
        if obstacle == "SITE_DOWNLOAD_PROHIBITED":
            report["status"] = obstacle
            return report
        for candidate in previous_pages:
            watch(candidate)
        context.on("page", watch)
        visible[0].click(timeout=10_000)
        report["target_pdf_name_confirmed"] = True
        if os.environ.get('TRAINING_CAPTURE_MODE') == '1':
            from page_capture import CaptureFailure, capture_reader_pdf, identify_reader, check_restrictions
            try:
                # Wait for the actual reader DOM after the already-successful
                # target-title click. No download control or hidden API is used.
                for attempt in range(30):
                    viewers = [candidate for candidate in context.pages if candidate not in previous_pages] or [page]
                    check_restrictions([page, *viewers], 1)
                    try:
                        identify_reader(viewers)
                        break
                    except CaptureFailure as exc:
                        if exc.reason not in {'READER_PAGE_STRUCTURE_UNSUPPORTED',
                                              'READER_TOTAL_UNCONFIRMED', 'READER_TOTAL_NOT_29'} or attempt == 29:
                            raise
                        page.wait_for_timeout(500)
                report.update(capture_reader_pdf(viewers, output_dir, raw))
                report['pdf_29_pages_confirmed'] = True
                report.update(encrypt_pdf(raw, encrypted, key))
                raw.unlink()
                report.update(status='PDF_CAPTURED_ENCRYPTED', download_channel='VISIBLE_PAGE_SCREENSHOTS')
                return report
            except CaptureFailure as exc:
                report.update(status='PAGE_CAPTURE_FAILED', failed_page=exc.page, capture_failure_reason=exc.reason)
                if getattr(exc, 'cleanup_failed', False):
                    report['screenshot_cleanup_failed'] = True
                return report
        control, obstacle = None, "DOWNLOAD_CONTROL_NOT_FOUND"
        for _ in range(30):
            viewers = [candidate for candidate in context.pages if candidate not in previous_pages] or [page]
            control, obstacle = inspect_controls(viewers)
            if obstacle in {"SITE_DOWNLOAD_PROHIBITED", "SITE_DOWNLOAD_DISABLED", "DOWNLOAD_CONTROL_AMBIGUOUS"}:
                report["status"] = obstacle
                return report
            if downloads or control is not None:
                break
            page.wait_for_timeout(500)
        if not downloads:
            if control is None:
                report["status"] = obstacle
                return report
            allow_response[0] = True
            control.click(timeout=10_000)  # One real Download action; no retries.
            for _ in range(60):
                if downloads or responses:
                    break
                page.wait_for_timeout(500)
        viewers = [candidate for candidate in context.pages if candidate not in previous_pages] or [page]
        _, final_obstacle = inspect_controls(viewers)
        if final_obstacle in {"SITE_DOWNLOAD_PROHIBITED", "SITE_DOWNLOAD_DISABLED"}:
            report["status"] = final_obstacle
            return report
        if len(downloads) > 1:
            report["status"] = "MULTIPLE_DOWNLOADS_REFUSED"
            return report
        if downloads:
            if downloads[0].failure() is not None:
                report["status"] = "SITE_DOWNLOAD_FAILED"
                return report
            downloads[0].save_as(str(raw))
            report["download_channel"] = "SITE_DOWNLOAD_EVENT"
        elif responses:
            # Full body from the site's explicit save action, never a guessed
            # request, range reconstruction or PDF.js getData()/print export.
            body = responses[0].body()
            with raw.open("xb") as stream:
                stream.write(body)
            report["download_channel"] = "SITE_SAVE_PDF_RESPONSE"
        else:
            report["status"] = "DOWNLOAD_ACTION_NO_FILE"
            return report
        report.update(validate_pdf(raw))
        report["pdf_29_pages_confirmed"] = True
        report.update(encrypt_pdf(raw, encrypted, key))
        raw.unlink()  # Plaintext never becomes an artifact upload candidate.
        report["status"] = "PDF_DOWNLOADED_ENCRYPTED"
        return report
    except PdfValidationError as exc:
        # This class contains only locally defined fixed failure codes.
        report["status"] = str(exc)
        return report
    except Exception:
        report["status"] = "DOWNLOAD_OR_ENCRYPTION_FAILED"
        return report
    finally:
        try:
            context.remove_listener("page", watch)
        except Exception:
            pass
        for candidate in listeners:
            try:
                candidate.remove_listener("download", downloaded)
                candidate.remove_listener("response", responded)
            except Exception:
                pass
        if report["status"] not in {"PDF_DOWNLOADED_ENCRYPTED", "PDF_CAPTURED_ENCRYPTED"}:
            for download in downloads:
                try:
                    download.cancel()
                except Exception:
                    pass
            # Only our two fixed filenames under the new per-run directory.
            if owned:
                for path in (raw, encrypted):
                    if path.is_file() and not path.is_symlink():
                        path.unlink()
