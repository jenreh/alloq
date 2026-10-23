"""Word documents (DOCX): paragraphs and tables in document order."""

import io

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from alloq_offer.workshop.extraction.models import (
    KIND_PARAGRAPH,
    KIND_TABLE,
    ExtractedBlock,
    ExtractionError,
    ExtractionResult,
)


def _table_text(table: Table) -> str:
    rows = (" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows)
    return "\n".join(rows)


def parse_docx(data: bytes) -> ExtractionResult:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - python-docx raises many types
        raise ExtractionError("Das Word-Dokument konnte nicht gelesen werden.") from exc
    blocks: list[ExtractedBlock] = []
    paragraphs = tables = 0
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraphs += 1
            text = Paragraph(child, document).text.strip()
            if text:
                blocks.append(
                    ExtractedBlock(KIND_PARAGRAPH, text, {"paragraph": paragraphs})
                )
        elif child.tag.endswith("}tbl"):
            tables += 1
            text = _table_text(Table(child, document))
            if text.strip():
                blocks.append(ExtractedBlock(KIND_TABLE, text, {"table": tables}))
    return ExtractionResult(blocks=blocks)
