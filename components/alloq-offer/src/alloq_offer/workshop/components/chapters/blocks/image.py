"""Image chapters: one picture with alt text and an optional caption, no heading."""

import reflex as rx
from alloq_commons import theme
from reflex_base.constants import Dirs
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.function import FunctionStringVar

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row, caption
from alloq_offer.workshop.components.chapters.editor import image_frame
from alloq_offer.workshop.image_api import IMAGES_INFIX, OFFERS_PREFIX
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.image_mixin import UPLOAD_ID, WIDTH_OPTIONS
from alloq_offer.workshop.states.workshop_state import WorkshopState

DROP_TEXT = "Bild hierher ziehen oder klicken, um eine Datei zu wählen"
DROP_HINT = "PNG oder JPEG, höchstens 3 MB"
REPLACE = "Ersetzen"
ALT_LABEL = "Alternativtext"
ALT_PLACEHOLDER = "Was zeigt das Bild?"
NO_IMAGE = "Noch kein Bild."
ACCEPT = {"image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]}
# Resolves a path against Reflex's own backend URL (port 3030 in development,
# the page origin with a single port), as the upload endpoint does.
_BACKEND_URL = FunctionStringVar.create(
    "((path) => new URL(path, getBackendURL(env.UPLOAD)).href)",
    _var_data=VarData(
        imports={
            f"$/{Dirs.STATE_PATH}": "getBackendURL",
            "$/env.json": ImportVar(tag="env", is_default=True),
        }
    ),
)


def image_src(chapter: Row) -> rx.Var[str]:
    """The picture's URL on the authorised image route of the open offer."""
    path = (
        OFFERS_PREFIX.lstrip("/")
        + WorkshopState.offer_id.to_string()
        + IMAGES_INFIX
        + chapter["blob_id"].to_string()
    )
    return _BACKEND_URL.call(path).to(str)


def _picture(chapter: Row) -> rx.Component:
    return rx.el.figure(
        rx.el.img(
            src=image_src(chapter),
            alt=chapter["alt"].to(str),
            style={"width": chapter["width"].to_string() + "%"},
            class_name="aq-doc-image",
        ),
        class_name="aq-doc-figure",
        custom_attrs={"data-align": chapter["align"].to(str)},
    )


def _has_picture(chapter: Row) -> rx.Var[bool]:
    return chapter["blob_id"].to(int) > 0


def view(chapter: Row) -> rx.Component:
    return rx.fragment(
        rx.cond(
            _has_picture(chapter),
            _picture(chapter),
            mn.text(NO_IMAGE, fz="12px", c=theme.TEXT_MUTED),
        ),
        caption.view(chapter),
    )


def _upload(*children: rx.Component, class_name: str) -> rx.Component:
    return rx.upload(
        *children,
        id=UPLOAD_ID,
        accept=ACCEPT,
        multiple=False,
        max_files=1,
        no_keyboard=False,
        disabled=ChapterState.chapter_locked,
        on_drop=ChapterState.upload_image(rx.upload_files(upload_id=UPLOAD_ID)),
        class_name=class_name,
    )


def _drop_zone() -> rx.Component:
    return _upload(
        rx.icon("image-plus", size=22, color=theme.TEXT_MUTED),
        mn.text(DROP_TEXT, fz="13px"),
        mn.text(DROP_HINT, fz="12px", c=theme.TEXT_MUTED),
        class_name="aq-doc-dropzone",
    )


def _frame(chapter: Row) -> rx.Component:
    """The selectable picture: toolbar, corner resize, replace and delete."""
    return image_frame(
        _upload(
            mn.button(REPLACE, variant="subtle", color="gray", size="compact-sm"),
            class_name="aq-doc-replace",
        ),
        src=image_src(chapter),
        alt=chapter["alt"].to(str),
        width=chapter["width"].to(int),
        align=chapter["align"].to(str),
        editable=~ChapterState.chapter_locked,
        sizes=WIDTH_OPTIONS,
        on_resize=ChapterState.set_image_width,
        on_align=ChapterState.set_image_align,
        on_remove=ChapterState.ask_remove,
    )


def editing(chapter: Row, _header: rx.Component) -> rx.Component:
    """Drop zone while empty; then the picture (Confluence), its alt text and
    caption."""
    return rx.cond(
        _has_picture(chapter),
        rx.fragment(
            _frame(chapter),
            caption.editing(chapter),
            rx.el.input(
                default_value=chapter["alt"].to(str),
                key=chapter["key"].to(str)
                + ":alt:"
                + chapter["alt"].to(str)
                + ChapterState.input_reset.to_string(),
                placeholder=ALT_PLACEHOLDER,
                aria_label=ALT_LABEL,
                read_only=ChapterState.chapter_locked,
                custom_attrs={"maxLength": 300},
                class_name="aq-doc-alt-input",
                on_blur=ChapterState.set_image_alt,
            ),
        ),
        rx.fragment(_drop_zone(), caption.editing(chapter)),
    )
