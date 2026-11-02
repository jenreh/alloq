"""PDF files with a text layer; pages without one are reported as gaps."""

import io

from pypdf import PdfReader

from alloq_offer.workshop.extraction.models import (
    KIND_PARAGRAPH,
    ExtractedBlock,
    ExtractionError,
    ExtractionResult,
    gap,
)

NO_TEXT_LAYER = "OCR nötig"
MAX_PAGES = 1000
TOO_MANY_PAGES = "Die PDF-Datei hat zu viele Seiten, um sie auszuwerten."


def parse_pdf(data: bytes) -> ExtractionResult:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("Die PDF-Datei ist passwortgeschützt.")
        if len(reader.pages) > MAX_PAGES:
            raise ExtractionError(TOO_MANY_PAGES)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001 - pypdf raises many types
        raise ExtractionError("Die PDF-Datei konnte nicht gelesen werden.") from exc
    blocks = [
        ExtractedBlock(KIND_PARAGRAPH, text, {"page": number})
        if text
        else gap(NO_TEXT_LAYER, {"page": number})
        for number, text in enumerate(pages, 1)
    ]
    return ExtractionResult(blocks=blocks)
