"""Validate a saved original PDF. No repair, decryption or content export."""
from pathlib import Path

MAX_PDF_BYTES = 100 * 1024 * 1024


class PdfValidationError(RuntimeError):
    pass


def validate_pdf(path):
    from pypdf import PdfReader
    import pymupdf

    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise PdfValidationError("PDF_FILE_MISSING")
    size = path.stat().st_size
    if not 8 <= size <= MAX_PDF_BYTES:
        raise PdfValidationError("PDF_SIZE_INVALID")
    with path.open("rb") as stream:
        if not stream.read(8).startswith(b"%PDF-"):
            raise PdfValidationError("NOT_A_PDF")
        stream.seek(max(0, size - 1024))
        if not stream.read().rstrip().endswith(b"%%EOF"):
            raise PdfValidationError("PDF_TRUNCATED")
    try:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            raise PdfValidationError("PDF_ENCRYPTION_OR_DRM_UNSUPPORTED")
        if len(reader.pages) != 29:
            raise PdfValidationError("PDF_PAGE_COUNT_MISMATCH")
        for page in reader.pages:
            contents = page.get_contents()
            if contents is not None:
                contents.get_data()
        pymupdf.TOOLS.mupdf_display_errors(False)
        pymupdf.TOOLS.mupdf_display_warnings(False)
        pymupdf.TOOLS.mupdf_warnings(reset=True)
        with pymupdf.open(str(path)) as document:
            if document.needs_pass or document.is_encrypted:
                raise PdfValidationError("PDF_ENCRYPTION_OR_DRM_UNSUPPORTED")
            if document.is_repaired or document.page_count != 29:
                raise PdfValidationError("PDF_DAMAGED")
            for page in document:
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5), alpha=False)
                if not pixmap.width or not pixmap.height:
                    raise PdfValidationError("PDF_RENDER_FAILED")
            if pymupdf.TOOLS.mupdf_warnings(reset=True):
                raise PdfValidationError("PDF_RENDER_WARNINGS")
    except PdfValidationError:
        raise
    except Exception:
        raise PdfValidationError("PDF_PARSE_OR_RENDER_FAILED") from None
    return {"pdf_file_validated": True, "pdf_page_count": 29, "pdf_pages_rendered": 29}
