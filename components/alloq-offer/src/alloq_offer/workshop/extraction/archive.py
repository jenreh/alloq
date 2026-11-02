"""Size guard for zip based Office files, checked before a parser opens them."""

import io
import zipfile

from alloq_offer.workshop.extraction.models import ExtractionError

MAX_UNPACKED_BYTES = 100 * 1024 * 1024
MAX_XML_PART_BYTES = 10 * 1024 * 1024
MAX_PARTS = 2000
TOO_LARGE = "Die Datei ist zu groß, um sie auszuwerten."


def check_archive(data: bytes, unreadable: str) -> None:
    """Refuse files that are no zip or would unpack to too much.

    ``unreadable`` is the German message for a file that is no zip at all.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise ExtractionError(unreadable) from exc
    too_big_xml = any(
        p.file_size > MAX_XML_PART_BYTES
        for p in parts
        if p.filename.endswith((".xml", ".rels"))
    )
    if (
        len(parts) > MAX_PARTS
        or too_big_xml
        or sum(p.file_size for p in parts) > MAX_UNPACKED_BYTES
    ):
        raise ExtractionError(TOO_LARGE)
