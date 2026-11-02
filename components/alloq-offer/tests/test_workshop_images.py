"""Image chapters: upload, sniffing, settings, captions and the document view."""

import base64
from types import SimpleNamespace

import pytest
from alloq_offer.workshop.components.chapters.blocks import image as image_block
from alloq_offer.workshop.export.template_package import ChapterDef
from alloq_offer.workshop.services import images
from alloq_offer.workshop.services.outline import OutlineService
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.storage import DbBlobStore
from test_chapter_state_helpers import as_editor as _as_editor
from test_chapter_state_helpers import run as _run
from test_chapter_state_helpers import shows as _shows

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20


def _file(data: bytes, name: str = "bild.png") -> SimpleNamespace:
    async def read(size: int = -1) -> bytes:
        return data if size < 0 else data[:size]

    return SimpleNamespace(name=name, size=len(data), content_type="", read=read)


async def _with_image(db) -> tuple[ChapterState, str]:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    key = await OutlineService(db.session, 1, "Anna").add_chapter(
        "loesung", chapter_type="image"
    )
    state = ChapterState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    with _as_editor(state, db):
        await _run(state.load_chapters)
        await _run(state.select_chapter, key)
    return state, key


def test_images_are_sniffed_not_trusted_by_name() -> None:
    assert images.image_mime(PNG) == "image/png"
    assert images.image_mime(JPEG) == "image/jpeg"
    assert images.image_mime(b"<svg></svg>") is None
    assert images.check_image(PNG) == "image/png"
    with pytest.raises(images.ImageError, match="PNG oder JPEG"):
        images.check_image(b"GIF89a")
    with pytest.raises(images.ImageError, match="MB"):
        images.check_image(PNG + b"\x00" * images.MAX_IMAGE_BYTES)


async def test_upload_stores_the_picture_and_shows_it(db) -> None:  # noqa: ANN001
    state, _ = await _with_image(db)
    with _as_editor(state, db):
        await _run(state.upload_image, [_file(PNG)])
    blob_id = state.active["blob_id"]
    assert blob_id > 0
    assert state.revision == 2
    stored = await DbBlobStore(10**7, db.session).get(blob_id)
    assert stored == PNG


async def test_upload_refuses_other_files(db) -> None:  # noqa: ANN001
    state, _ = await _with_image(db)
    with _as_editor(state, db):
        toast = await _run(state.upload_image, [_file(b"<svg/>", "x.png")])
        assert _shows(images.NOT_AN_IMAGE, toast)
        assert await _run(state.upload_image, []) == ""
        await _run(state.select_chapter, "loesung")
        assert await _run(state.upload_image, [_file(PNG)]) == ""
    assert state.revision == 1


async def test_image_settings_and_captions(db) -> None:  # noqa: ANN001
    state, _ = await _with_image(db)
    with _as_editor(state, db):
        await _run(state.set_image_alt, "  Architektur  ")
        await _run(state.set_image_width, "50")
        await _run(state.set_image_width, "5000")
        await _run(state.set_image_align, "left")
        await _run(state.set_image_align, "oben")
        await _run(state.set_caption, "Bild 1: Überblick")
    active = state.active
    assert (active["alt"], active["width"], active["align"]) == (
        "Architektur",
        50,
        "left",
    )
    assert active["description"] == "Bild 1: Überblick"
    with _as_editor(state, db):
        await _run(state.select_chapter, "mitwirkung")
        await _run(state.set_caption, "Pflichten")
    assert state.active["description"] == "Pflichten"


def test_image_block_renders_its_parts() -> None:
    rendered = str(image_block.view(ChapterState.active))
    assert "getBackendURL(env.UPLOAD)" in rendered
    assert "api/offers/" in rendered
    editing = str(image_block.editing(ChapterState.active, image_block.rx.fragment()))
    parts = ("aq-doc-dropzone", "set_image_align", "set_image_width", "set_caption")
    for part in parts:
        assert part in editing


def test_templates_cannot_point_at_a_picture() -> None:
    with pytest.raises(ValueError, match="keine Bilder"):
        ChapterDef(
            key="bild",
            title="",
            level=2,
            chapter_type="image",
            default_content={"blob_id": 7},
        )
