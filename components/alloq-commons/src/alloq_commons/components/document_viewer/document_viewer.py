"""Document viewers for PDF, Word and PowerPoint files, drawn from bytes.

Ported from the mail-archive viewer kit. The file reaches the browser as a
base64 prop over the state socket, so no route serves source files. Each viewer
is a ``NoSSRComponent`` loaded as its own lazy chunk: the renderers touch
``document`` and start WebAssembly, and each is about a megabyte.

All assets are registered from this module, so ``rx.asset(shared=True)`` puts
them into one folder and the JSX files can import ``./viewer_shell.jsx``.
The npm versions are pinned exactly; nothing may load from a CDN.
"""

from types import MappingProxyType

import reflex as rx
from reflex.components.component import NoSSRComponent
from reflex.utils.imports import ImportDict
from reflex.vars.base import Var

VIEWER_PACKAGES = MappingProxyType(
    {
        "docx": ("@extend-ai/react-docx@0.9.1",),
        "pptx": ("@extend-ai/react-pptx@0.2.0",),
        "pdf": (
            "@embedpdf/core@2.15.0",
            "@embedpdf/engines@2.15.0",
            "@embedpdf/models@2.15.0",
            "@embedpdf/pdfium@2.15.0",
            "@embedpdf/plugin-document-manager@2.15.0",
            "@embedpdf/plugin-interaction-manager@2.15.0",
            "@embedpdf/plugin-render@2.15.0",
            "@embedpdf/plugin-rotate@2.15.0",
            "@embedpdf/plugin-scroll@2.15.0",
            "@embedpdf/plugin-thumbnail@2.15.0",
            "@embedpdf/plugin-viewport@2.15.0",
            "@embedpdf/plugin-zoom@2.15.0",
        ),
    }
)
"""npm packages per viewer, keyed by the name in ``viewer_<name>.jsx``."""

# Imported by the JSX files, not by Python; registering puts them next to them.
rx.asset("viewer_shell.jsx", shared=True)
rx.asset("viewer_bytes.js", shared=True)

# importable_path omits the ?v= hash, which Vite would cache as an optimised dep.
VIEWER_LIBRARIES = MappingProxyType(
    {
        name: rx.asset(f"viewer_{name}.jsx", shared=True).importable_path
        for name in VIEWER_PACKAGES
    }
)

VIEWER_CLASS = "aq-viewer"


class _DocumentViewer(NoSSRComponent):
    """A file as base64 plus its name; props reach the JSX camelCased."""

    is_default = True

    encoded: Var[str]
    """The file as base64 without a ``data:`` prefix."""

    file_name: Var[str]

    def add_imports(self) -> ImportDict:
        return {
            "react": ["lazy"],
            f"$/{rx.constants.Dirs.UTILS}/context": ["ClientSide"],
        }


class _PdfViewer(_DocumentViewer):
    library = VIEWER_LIBRARIES["pdf"]
    tag = "PdfViewer"
    lib_dependencies: list[str] = list(VIEWER_PACKAGES["pdf"])


class _DocxViewer(_DocumentViewer):
    library = VIEWER_LIBRARIES["docx"]
    tag = "DocxViewer"
    lib_dependencies: list[str] = list(VIEWER_PACKAGES["docx"])


class _PptxViewer(_DocumentViewer):
    library = VIEWER_LIBRARIES["pptx"]
    tag = "PptxViewer"
    lib_dependencies: list[str] = list(VIEWER_PACKAGES["pptx"])


VIEWERS: dict[str, type[_DocumentViewer]] = {
    "pdf": _PdfViewer,
    "docx": _DocxViewer,
    "pptx": _PptxViewer,
}


def document_viewer(
    kind: Var[str] | str, encoded: Var[str] | str, file_name: Var[str] | str
) -> rx.Component:
    """The viewer for ``kind`` in a box with a height; nothing for other kinds.

    A viewer measures its container once at mount, so the box needs a height.
    """
    return rx.box(
        rx.match(
            kind,
            *(
                (name, viewer.create(encoded=encoded, file_name=file_name))
                for name, viewer in VIEWERS.items()
            ),
            rx.fragment(),
        ),
        class_name=VIEWER_CLASS,
    )
