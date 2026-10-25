"""Tests of the sources panel state and components."""

import base64
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.components.document_viewer import VIEWERS
from alloq_offer.workshop.components import draft_tab, sources_panel
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import SourceEntity, SourceKind, SourceStatus
from alloq_offer.workshop.services.sources import (
    ACCEPTED_EXTENSIONS,
    VIEWABLE_KINDS,
    DraftNotPossibleError,
    SourceOriginal,
    SourceRejectedError,
)
from alloq_offer.workshop.states import sources_state
from alloq_offer.workshop.states.sources_state import (
    ADD_ERROR,
    EMPTY_TEXT,
    RETRY_ERROR,
    REVOKE_ERROR,
    REVOKED,
    TOO_LARGE,
    TOO_LARGE_TO_SHOW,
    VIEWER_TAB_ORIGINAL,
    VIEWER_TAB_TEXT,
    SourcesState,
    source_row,
)
from alloq_offer.workshop.states.workshop_state import WorkshopState
from alloq_offer.workshop.storage import BlobTooLargeError

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.sources_state"
SERVICE = "alloq_offer.workshop.services.sources"


def _source(
    sid: int = 1,
    status: SourceStatus = SourceStatus.USABLE,
    *,
    included: bool = True,
    detail: str = "",
    kind: SourceKind = SourceKind.EML,
) -> SourceEntity:
    entity = SourceEntity(
        offer_id=5,
        kind=kind,
        title=f"Quelle {sid}",
        sha256="x",
        status=status,
        status_detail=detail,
        included=included,
    )
    entity.id = sid
    return entity


@pytest.fixture
def repo() -> Generator[AsyncMock]:
    @asynccontextmanager
    async def _ctx() -> AsyncGenerator[Any]:
        yield AsyncMock()

    sources = AsyncMock()
    sources.list_current = AsyncMock(return_value=[_source()])
    with (
        patch(f"{MODULE}.source_repo", sources),
        patch(
            f"{MODULE}.workspace_repo",
            MagicMock(
                find_by_offer=AsyncMock(return_value=SimpleNamespace(map_revision=0))
            ),
        ),
        patch(
            f"{MODULE}.job_repo", MagicMock(find_latest=AsyncMock(return_value=None))
        ),
        patch(f"{MODULE}.get_asyncdb_session", _ctx),
        patch(
            f"{MODULE}.service_registry",
            return_value=MagicMock(get=MagicMock(return_value=WorkshopConfig())),
        ),
    ):
        yield sources


@contextmanager
def _as_offer_editor(state: SourcesState, offer_id: int = 5) -> Generator[None]:
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)
    workshop = SimpleNamespace(offer_id=offer_id)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else workshop

    object.__setattr__(state, "get_state", _get_state)
    try:
        yield
    finally:
        object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> str:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""


ADDED = SimpleNamespace(created=True, source=SimpleNamespace(title="T"))


def _state() -> SourcesState:
    return SourcesState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]


def _file(name: str, data: bytes = b"x") -> MagicMock:
    file = MagicMock(content_type="text/plain", size=len(data))
    file.name = name
    file.read = AsyncMock(return_value=data)
    return file


def test_source_row_describes_status_and_flags() -> None:
    usable = source_row(
        _source(detail="Seite 7: OCR nötig", status=SourceStatus.PARTIAL)
    )
    assert usable["summary"] == "E-Mail · teilweise nutzbar · Seite 7: OCR nötig"
    assert usable["usable"]
    assert usable["ok"]
    assert not usable["retryable"]
    failed = source_row(_source(status=SourceStatus.FAILED))
    assert failed["retryable"]
    assert not failed["ok"]
    assert not failed["usable"]
    working = source_row(_source(status=SourceStatus.PROCESSING))
    assert working["working"]
    assert working["ok"]


def test_counts_labels_and_polling_follow_the_sources() -> None:
    state = _state()
    assert state.is_empty
    assert not state.can_generate
    assert state.generate_label == "Entwurf aus 0 Quellen erzeugen"
    state.sources = [
        source_row(_source(1)),
        source_row(_source(2, included=False)),
        source_row(_source(3, SourceStatus.PROCESSING)),
    ]
    assert state.included_count == 1
    assert state.generate_label == "Entwurf aus 1 Quelle erzeugen"
    assert state.has_working
    assert not state.is_empty


def test_paste_dialog_toggles() -> None:
    state = _state()
    state.open_paste()
    assert state.paste_open
    state.close_paste()
    assert not state.paste_open


@pytest.mark.usefixtures("repo")
async def test_load_sources_fills_the_list() -> None:
    state = _state()
    with _as_offer_editor(state):
        await _run(state.load_sources)
    assert [row["id"] for row in state.sources] == [1]


@pytest.mark.usefixtures("repo")
async def test_load_sources_skips_without_open_offer() -> None:
    state = _state()
    with _as_offer_editor(state, offer_id=0):
        await _run(state.load_sources)
    assert state.sources == []


async def test_load_sources_reports_failure(repo: AsyncMock) -> None:
    repo.list_current.side_effect = RuntimeError("db")
    state = _state()
    with _as_offer_editor(state):
        assert "Quellen konnten nicht geladen" in await _run(state.load_sources)


@pytest.mark.usefixtures("repo")
async def test_toggle_and_retry_call_the_service() -> None:
    state = _state()
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.set_included", AsyncMock(return_value=True)) as included,
        patch(f"{SERVICE}.retry_source", AsyncMock(return_value=True)) as retry,
    ):
        await _run(state.toggle_source, 1, False)
        await _run(state.retry_source, 1)
    assert included.await_args.args[1:] == (5, 1, False)
    assert retry.await_args.args[1:3] == (5, 1)


@pytest.mark.usefixtures("repo")
async def test_toggle_and_retry_report_failures() -> None:
    state = _state()
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.set_included", AsyncMock(side_effect=RuntimeError)),
        patch(f"{SERVICE}.retry_source", AsyncMock(side_effect=RuntimeError)),
    ):
        assert "Änderung" in await _run(state.toggle_source, 1, True)
        assert RETRY_ERROR in await _run(state.retry_source, 1)


@pytest.mark.usefixtures("repo")
async def test_upload_adds_files_and_names_rejected_ones() -> None:
    state = _state()
    add = AsyncMock(
        side_effect=[ADDED, BlobTooLargeError(9), RuntimeError("db"), ADDED],
    )
    files = [_file("a.txt"), _file("big.pdf"), _file("c.pdf"), _file("d.docm")]
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.add_source", add),
        patch(
            f"{SERVICE}.classify_filename",
            side_effect=[
                SourceKind.TXT,
                SourceKind.PDF,
                SourceKind.PDF,
                SourceRejectedError(
                    "Dateien mit Makros werden nicht angenommen: d.docm"
                ),
            ],
        ),
    ):
        toasts = await _run(state.handle_upload, files)
    assert TOO_LARGE in toasts
    assert ADD_ERROR in toasts
    assert "Makros" in toasts
    assert add.await_count == 3
    assert [row["id"] for row in state.sources] == [1]


@pytest.mark.usefixtures("repo")
async def test_upload_without_open_offer_does_nothing() -> None:
    state = _state()
    with _as_offer_editor(state, offer_id=0), patch(f"{SERVICE}.add_source") as add:
        await _run(state.handle_upload, [_file("a.txt")])
    add.assert_not_called()


@pytest.mark.usefixtures("repo")
async def test_pasted_text_becomes_a_text_source() -> None:
    state = _state()
    state.paste_open = True
    add = AsyncMock(return_value=ADDED)
    with _as_offer_editor(state), patch(f"{SERVICE}.add_source", add):
        await _run(state.add_pasted_text, {"title": "  ", "text": " Inhalt "})
    kwargs = add.await_args.kwargs
    assert kwargs["kind"] is SourceKind.TEXT
    assert kwargs["data"] == b"Inhalt"
    assert kwargs["title"] == "Eingefügter Text"
    assert not state.paste_open
    assert kwargs["now"].tzinfo is UTC
    assert isinstance(kwargs["now"], datetime)


@pytest.mark.usefixtures("repo")
async def test_pasted_text_rejects_empty_and_reports_errors() -> None:
    state = _state()
    with _as_offer_editor(state):
        assert EMPTY_TEXT in await _run(state.add_pasted_text, {"text": "  "})
        with patch(f"{SERVICE}.add_source", AsyncMock(side_effect=RuntimeError)):
            assert ADD_ERROR in await _run(state.add_pasted_text, {"text": "x"})
        with patch(
            f"{SERVICE}.add_source", AsyncMock(side_effect=BlobTooLargeError(1))
        ):
            assert TOO_LARGE in await _run(state.add_pasted_text, {"text": "x"})


def test_upload_picker_matches_the_accepted_extensions() -> None:
    picked = {e for exts in sources_panel.UPLOAD_ACCEPT.values() for e in exts}
    assert picked == set(ACCEPTED_EXTENSIONS)


def test_panel_and_draft_tab_render_constants() -> None:
    panel = str(sources_panel.sources_panel())
    assert sources_panel.DROP_TEXT in panel
    assert "Text als Quelle" in panel
    assert "dashed" in panel
    assert "5em" not in panel
    assert sources_state.UPLOAD_ID in panel
    tab = str(draft_tab.draft_tab())
    assert "can_generate" in tab
    assert WorkshopState.__name__


@pytest.mark.usefixtures("repo")
async def test_known_content_and_oversized_files_are_reported() -> None:
    state = _state()
    known = SimpleNamespace(created=False, source=SimpleNamespace(title="Alt"))
    big = _file("big.txt", b"x")
    big.size = WorkshopConfig().max_blob_bytes + 1
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.add_source", AsyncMock(return_value=known)) as add,
    ):
        toasts = await _run(state.handle_upload, [_file("a.txt"), big])
        pasted = await _run(state.add_pasted_text, {"text": "x"})
    assert sources_state.KNOWN in toasts
    assert TOO_LARGE in toasts
    assert sources_state.KNOWN in pasted
    assert add.await_count == 2


def test_draft_button_state_follows_map_and_job() -> None:
    state = _state()
    state.sources = [source_row(_source(1))]
    assert state.can_generate
    state.has_map = True
    assert not state.can_generate
    state.has_map = False
    state.draft_job = "running"
    assert state.draft_working
    assert state.has_working
    assert not state.can_generate
    assert "gerade erzeugt" in state.draft_message
    state.draft_job = "succeeded"
    assert state.draft_message == ""


@pytest.mark.usefixtures("repo")
async def test_generate_draft_queues_the_job() -> None:
    state = _state()
    state.sources = [source_row(_source(1))]
    request = AsyncMock()
    with _as_offer_editor(state), patch(f"{SERVICE}.request_initial_draft", request):
        toasts = await _run(state.generate_draft)
    request.assert_awaited_once()
    assert sources_state.DRAFT_QUEUED in toasts
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.request_initial_draft", AsyncMock(side_effect=RuntimeError)),
    ):
        assert sources_state.DRAFT_ERROR in await _run(state.generate_draft)


@pytest.mark.usefixtures("repo")
async def test_generate_draft_does_nothing_without_sources() -> None:
    state = _state()
    request = AsyncMock()
    with _as_offer_editor(state), patch(f"{SERVICE}.request_initial_draft", request):
        await _run(state.generate_draft)
    request.assert_not_called()


@pytest.mark.usefixtures("repo")
async def test_generate_draft_reports_a_draft_that_is_not_possible() -> None:
    state = _state()
    state.sources = [source_row(_source(1))]
    error = DraftNotPossibleError("Zu diesem Angebot gibt es schon eine Story Map.")
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.request_initial_draft", AsyncMock(side_effect=error)),
    ):
        assert "schon eine Story Map" in await _run(state.generate_draft)


def test_failed_draft_shows_the_reason() -> None:
    state = _state()
    state.draft_job = "failed"
    state.draft_error = "Bitte prüfen Sie die Einrichtung."
    assert state.draft_message.endswith("Bitte prüfen Sie die Einrichtung.")


@pytest.mark.usefixtures("repo")
async def test_revoke_source_reports_success_and_failure() -> None:
    state = _state()
    with (
        _as_offer_editor(state),
        patch(f"{MODULE}.revoke_source", AsyncMock(return_value=True)) as revoke,
    ):
        assert REVOKED in await _run(state.revoke_source, 1)
    assert revoke.await_args.args[1:3] == (5, 1)
    with (
        _as_offer_editor(state),
        patch(f"{MODULE}.revoke_source", AsyncMock(side_effect=RuntimeError)),
    ):
        assert REVOKE_ERROR in await _run(state.revoke_source, 1)


@pytest.mark.usefixtures("repo")
async def test_viewer_opens_with_blocks_and_closes() -> None:
    state = _state()
    blocks = [{"label": "Seite 1", "speaker": "", "text": "Hallo", "gap": False}]
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.load_blocks", AsyncMock(return_value=("Mail", blocks))),
        patch(f"{SERVICE}.load_original", AsyncMock(return_value=None)),
    ):
        await _run(state.open_viewer, 1)
    assert state.viewer_open
    assert (state.viewer_title, state.viewer_blocks) == ("Mail", blocks)
    assert (state.viewer_kind, state.viewer_tab) == ("", VIEWER_TAB_TEXT)
    state.close_viewer()
    assert not state.viewer_open
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.load_blocks", AsyncMock(side_effect=RuntimeError)),
    ):
        assert "geladen" in await _run(state.open_viewer, 1)


@pytest.mark.usefixtures("repo")
async def test_viewer_shows_the_original_file_and_releases_it_on_close() -> None:
    state = _state()
    original = SourceOriginal(SourceKind.PDF, "angebot.pdf", b"%PDF")
    with (
        _as_offer_editor(state),
        patch(f"{SERVICE}.load_blocks", AsyncMock(return_value=("PDF", []))),
        patch(f"{SERVICE}.load_original", AsyncMock(return_value=original)),
    ):
        await _run(state.open_viewer, 1)
    assert (state.viewer_kind, state.viewer_file) == ("pdf", "angebot.pdf")
    assert state.viewer_encoded == base64.b64encode(b"%PDF").decode()
    assert (state.viewer_tab, state.viewer_note) == (VIEWER_TAB_ORIGINAL, "")
    state.set_viewer_tab(VIEWER_TAB_TEXT)
    assert state.viewer_tab == VIEWER_TAB_TEXT
    state.set_viewer_tab(None)
    assert state.viewer_tab == VIEWER_TAB_TEXT
    state.close_viewer()
    assert state.viewer_encoded == ""


@pytest.mark.usefixtures("repo")
async def test_viewer_does_not_send_files_over_the_preview_limit() -> None:
    state = _state()
    original = SourceOriginal(SourceKind.DOCX, "gross.docx", b"x" * 11)
    with (
        _as_offer_editor(state),
        patch(f"{MODULE}.PREVIEW_LIMIT", 10),
        patch(f"{SERVICE}.load_blocks", AsyncMock(return_value=("Doc", []))),
        patch(f"{SERVICE}.load_original", AsyncMock(return_value=original)),
    ):
        await _run(state.open_viewer, 1)
    assert (state.viewer_kind, state.viewer_encoded) == ("docx", "")
    assert state.viewer_note == TOO_LARGE_TO_SHOW


def test_viewer_dialog_offers_original_and_read_text() -> None:
    panel = str(sources_panel.sources_panel())
    assert sources_panel.ORIGINAL_TAB in panel
    assert "viewer_encoded" in panel
    assert "aq-viewer" in panel


def test_view_is_an_icon_button_with_a_label() -> None:
    panel = str(sources_panel.sources_panel())
    assert "LucideEye" in panel
    assert sources_panel.VIEW_LABEL in panel


def test_viewer_slides_in_from_the_right() -> None:
    panel = str(sources_panel.sources_panel())
    assert "Drawer" in panel
    assert '"right"' in panel
    assert sources_panel.VIEWER_DRAWER_SIZE in panel


def test_every_viewable_source_kind_has_a_viewer() -> None:
    assert set(VIEWERS) == {str(k) for k in VIEWABLE_KINDS}
