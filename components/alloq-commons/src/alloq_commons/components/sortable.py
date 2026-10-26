"""A list whose rows are reordered by drag and drop or the keyboard.

Built on ``@hello-pangea/dnd``: a row is lifted with the mouse, or focused and
moved with space and the arrow keys. Render each row as a ``sortable_item``
(also inside ``rx.foreach``) within one ``sortable_list``; ``on_reorder``
receives the moved id and its new index.
"""

from typing import Any

import reflex as rx
from reflex.event import EventHandler
from reflex.vars.base import Var

DND_PACKAGE = "@hello-pangea/dnd@18.0.1"
_LIBRARY = rx.asset("sortable.jsx", shared=True).importable_path


class SortableList(rx.Component):
    library = _LIBRARY
    tag = "SortableList"
    lib_dependencies: list[str] = [DND_PACKAGE]

    ids: Var[list[str]]
    """The ids of the rows in their stored order."""

    version: Var[int]
    """Changes after every answer to ``on_reorder``, also a failed one."""

    droppable_id: Var[str]

    instructions: Var[str]
    """What screen readers say about moving a row with the keyboard."""

    on_reorder: EventHandler[lambda key, index: [key, index]]


class SortableItem(rx.Component):
    library = _LIBRARY
    tag = "SortableItem"
    lib_dependencies: list[str] = [DND_PACKAGE]

    item_id: Var[str]
    index: Var[int]
    """The position of the row in the stored order."""

    disabled: Var[bool]
    """True when the row cannot be dragged."""


def sortable_list(*children: Any, **props: Any) -> rx.Component:
    return SortableList.create(*children, **props)


def sortable_item(*children: Any, item_id: Any, **props: Any) -> rx.Component:
    """One row; keyed by its id, as the drag library needs stable keys (a
    ``foreach`` keys by position otherwise)."""
    return SortableItem.create(*children, item_id=item_id, key=item_id, **props)
