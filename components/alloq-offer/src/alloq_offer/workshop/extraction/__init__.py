"""Parsers that turn an uploaded source into citable blocks."""

from alloq_offer.workshop.extraction.audio import (
    TranscriptionUnavailableError,
    Transcriber,
    to_result,
)
from alloq_offer.workshop.extraction.eml import parse_eml
from alloq_offer.workshop.extraction.models import (
    ExtractedBlock,
    ExtractionError,
    ExtractionResult,
)
from alloq_offer.workshop.extraction.pdf import parse_pdf
from alloq_offer.workshop.extraction.slides import parse_pptx
from alloq_offer.workshop.extraction.text import parse_html, parse_text
from alloq_offer.workshop.extraction.word import parse_docx

__all__ = [
    "ExtractedBlock",
    "ExtractionError",
    "ExtractionResult",
    "Transcriber",
    "TranscriptionUnavailableError",
    "parse_docx",
    "parse_eml",
    "parse_html",
    "parse_pdf",
    "parse_pptx",
    "parse_text",
    "to_result",
]
