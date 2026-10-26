"""Sortable list: a pinned drag and drop package and the reorder event."""

import reflex as rx
from alloq_commons.components.sortable import (
    DND_PACKAGE,
    SortableItem,
    SortableList,
    sortable_item,
    sortable_list,
)


class _Order(rx.State):
    moved: rx.Field[str] = rx.field("")

    @rx.event
    def reorder(self, key: str, index: int) -> None:
        self.moved = f"{key}:{index}"


def test_dnd_package_is_pinned_to_an_exact_version() -> None:
    name, _, version = DND_PACKAGE.rpartition("@")
    assert name == "@hello-pangea/dnd"
    assert version.count(".") == 2
    assert version[0].isdigit()
    assert DND_PACKAGE in SortableList.lib_dependencies
    assert DND_PACKAGE in SortableItem.lib_dependencies


def test_sortable_list_renders_items_and_the_event() -> None:
    rendered = str(
        sortable_list(
            sortable_item(rx.text("Eins"), item_id="a", index=0),
            sortable_item(rx.text("Zwei"), item_id="b", index=1, disabled=True),
            ids=["a", "b"],
            on_reorder=_Order.reorder,
        )
    )
    assert "SortableList" in rendered
    assert "SortableItem" in rendered
    assert 'ids:["a", "b"]' in rendered
    assert 'itemId:"b"' in rendered
    assert 'key:"b"' in rendered
    assert "disabled:true" in rendered
    assert "reorder" in rendered
