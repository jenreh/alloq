"""E-Mail (EML) with header, body, quoted chain, signature and attachments."""

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from alloq_offer.workshop.extraction.models import (
    KIND_HEADER,
    KIND_PARAGRAPH,
    KIND_QUOTE,
    KIND_SIGNATURE,
    Attachment,
    ExtractedBlock,
    ExtractionError,
    ExtractionResult,
)
from alloq_offer.workshop.extraction.text import html_to_text, split_paragraphs

SIGNATURE_MARKER = "-- "


def _header_text(message: EmailMessage) -> str:
    lines = [
        f"{label}: {message[name]}"
        for label, name in (
            ("Betreff", "Subject"),
            ("Von", "From"),
            ("An", "To"),
            ("Datum", "Date"),
        )
        if message[name]
    ]
    return "\n".join(lines)


def _split_body(body: str) -> tuple[list[str], list[str], list[str]]:
    """Own lines, quoted lines and signature lines of a plain text body."""
    own: list[str] = []
    quoted: list[str] = []
    signature: list[str] = []
    in_signature = False
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.rstrip() == SIGNATURE_MARKER.rstrip():
            in_signature = True
        elif in_signature:
            signature.append(line)
        elif line.lstrip().startswith(">"):
            quoted.append(line.lstrip().lstrip(">").strip())
        else:
            own.append(line)
    return own, quoted, signature


def _body_text(message: EmailMessage) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_subtype() != "html":
        return content
    return html_to_text(content)


def _attachment_bytes(part: EmailMessage) -> bytes:
    payload = part.get_payload(decode=True)
    return payload if isinstance(payload, bytes) else b""


def parse_eml(data: bytes) -> ExtractionResult:
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
    except Exception as exc:  # noqa: BLE001 - the stdlib parser raises many types
        raise ExtractionError("Die E-Mail konnte nicht gelesen werden.") from exc
    if not isinstance(message, EmailMessage):
        raise ExtractionError("Die E-Mail konnte nicht gelesen werden.")

    anchor_base = {"message_id": (message["Message-ID"] or "").strip()}
    blocks = [
        ExtractedBlock(
            KIND_HEADER, _header_text(message), {**anchor_base, "part": "header"}
        )
    ]
    own, quoted, signature = _split_body(_body_text(message))
    blocks.extend(
        ExtractedBlock(KIND_PARAGRAPH, text, {**anchor_base, "paragraph": index})
        for index, text in enumerate(split_paragraphs("\n".join(own)), 1)
    )
    if quoted:
        blocks.append(
            ExtractedBlock(
                KIND_QUOTE, "\n".join(quoted), {**anchor_base, "part": "quote"}
            )
        )
    if signature:
        blocks.append(
            ExtractedBlock(
                KIND_SIGNATURE,
                "\n".join(signature).strip(),
                {**anchor_base, "part": "signature"},
            )
        )
    attachments = [
        Attachment(
            filename=part.get_filename() or "Anhang",
            mime=part.get_content_type(),
            data=_attachment_bytes(part),
        )
        for part in message.iter_attachments()
        if not part.is_multipart()
    ]
    return ExtractionResult(
        blocks=blocks, title=str(message["Subject"] or ""), attachments=attachments
    )
