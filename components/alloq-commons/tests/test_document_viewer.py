"""Tests of the document viewer wrappers."""

import inspect
import re
from pathlib import Path

import pytest
from alloq_commons.components.document_viewer.document_viewer import (
    VIEWER_CLASS,
    VIEWER_LIBRARIES,
    VIEWER_PACKAGES,
    VIEWERS,
    document_viewer,
)

FOLDER = Path(inspect.getfile(VIEWERS["pdf"])).parent


def test_every_viewer_has_its_packages() -> None:
    assert set(VIEWERS) == set(VIEWER_PACKAGES)


@pytest.mark.parametrize("name", sorted(VIEWER_PACKAGES))
def test_viewer_loads_its_local_jsx_with_pinned_packages(name: str) -> None:
    component = VIEWERS[name].create(encoded="QQ==", file_name="a")
    assert component.library == VIEWER_LIBRARIES[name]
    assert str(component.library).endswith(f"document_viewer/viewer_{name}.jsx")
    assert all(re.search(r"@\d", pkg) for pkg in component.lib_dependencies)
    assert "lazy" in component.add_imports()["react"]


@pytest.mark.parametrize("name", sorted(VIEWER_PACKAGES))
def test_viewer_jsx_is_wrapped_in_the_error_boundary(name: str) -> None:
    source = (FOLDER / f"viewer_{name}.jsx").read_text(encoding="utf-8")
    assert "export default withBoundary(" in source


def test_viewers_never_load_from_a_cdn() -> None:
    for path in FOLDER.glob("*.js*"):
        assert "https://" not in path.read_text(encoding="utf-8"), path.name


def test_document_viewer_sends_bytes_and_name_camel_cased() -> None:
    rendered = str(document_viewer("pdf", "QQ==", "angebot.pdf"))
    assert VIEWER_CLASS in rendered
    assert "fileName" in rendered
    assert "encoded" in rendered
