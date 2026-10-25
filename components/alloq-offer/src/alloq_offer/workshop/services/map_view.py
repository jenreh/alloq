"""The story map as a grid of plain values for the page (from a map snapshot)."""

from collections.abc import Collection
from typing import Any

NO_SLICE_ID = 0
NO_SLICE_TITLE = "Ohne Umsetzungsschnitt"
ORIGIN_SOURCE = "Quellenstellen"


def count_label(count: int) -> str:
    return f"{count} {'Story' if count == 1 else 'Stories'}"


def _with_count(row: dict[str, Any]) -> dict[str, Any]:
    count = sum(len(cell["stories"]) for cell in row["cells"])
    return {**row, "count_label": count_label(count)}


def _card(story: dict) -> dict[str, Any]:
    """What a map card shows; the rest of a story only travels when it is opened."""
    return {
        "id": story["id"],
        "key": story["key"],
        "title": story["title"],
        "skeleton": story["skeleton"],
    }


def _detail(story: dict) -> dict[str, Any]:
    refs = len(story["source_refs"])
    return {
        **_card(story),
        "origin": story["origin"],
        "sentence": story["sentence"],
        "description": story.get("description", ""),
        "refs": f"{refs} {ORIGIN_SOURCE}" if refs else "ohne Quellenbezug",
    }


def build_view(snapshot: dict) -> dict[str, Any]:
    """Columns, slice rows, option lists and a story lookup for the editor."""
    activities = [a for a in snapshot["activities"] if not a["archived"]]
    slices = snapshot["slices"]
    tasks_of = {
        a["id"]: [t for t in a["tasks"] if not t["archived"]] for a in activities
    }
    columns = [
        {
            "id": a["id"],
            "index": index,
            "title": a["title"],
            "tasks": " · ".join(t["title"] for t in tasks_of[a["id"]]),
            "task_id": tasks_of[a["id"]][0]["id"] if tasks_of[a["id"]] else 0,
            "first": index == 0,
            "last": index == len(activities) - 1,
        }
        for index, a in enumerate(activities)
    ]

    def cell(activity: dict, slice_id: int) -> dict[str, Any]:
        stories = [
            _card(s)
            for t in tasks_of[activity["id"]]
            for s in t["stories"]
            if not s["archived"] and (s["slice_id"] or NO_SLICE_ID) == slice_id
        ]
        first_task = (
            tasks_of[activity["id"]][0]["id"] if tasks_of[activity["id"]] else 0
        )
        return {
            "activity_id": activity["id"],
            "task_id": first_task,
            "stories": stories,
        }

    row_defs = [(s["id"], s["title"], True) for s in slices] + [
        (NO_SLICE_ID, NO_SLICE_TITLE, False)
    ]
    rows = [
        _with_count(
            {
                "slice_id": slice_id,
                # A new slice inserted at this row's top edge gets this index.
                "index": index,
                "title": title,
                "editable": editable,
                "cells": [cell(a, slice_id) for a in activities],
            }
        )
        for index, (slice_id, title, editable) in enumerate(row_defs)
    ]
    lookup = {
        str(story["id"]): {
            **_detail(story),
            "role": story["role"],
            "goal": story["goal"],
            "benefit": story["benefit"],
            "task_id": str(task["id"]),
            "slice_id": str(story["slice_id"] or NO_SLICE_ID),
        }
        for activity in activities
        for task in tasks_of[activity["id"]]
        for story in task["stories"]
        if not story["archived"]
    }
    archived = [
        {
            "id": story["id"],
            "key": story["key"],
            "title": story["title"],
            "task_id": str(task["id"]),
            "where": f"{activity['title']} · {task['title']}",
            "sentence": story["sentence"],
        }
        for activity in snapshot["activities"]
        for task in activity["tasks"]
        for story in task["stories"]
        if story["archived"]
    ]
    return {
        "archived": archived,
        "columns": columns,
        "rows": rows,
        "stories": lookup,
        "story_count": len(lookup),
        "task_groups": [
            {
                "group": a["title"],
                "items": [
                    {"value": str(t["id"]), "label": t["title"]}
                    for t in tasks_of[a["id"]]
                ],
            }
            for a in activities
            if tasks_of[a["id"]]
        ],
        "task_options": [
            {"value": str(t["id"]), "label": f"{a['title']} · {t['title']}"}
            for a in activities
            for t in tasks_of[a["id"]]
        ],
        "slice_options": [{"value": str(NO_SLICE_ID), "label": NO_SLICE_TITLE}]
        + [{"value": str(s["id"]), "label": s["title"]} for s in slices],
    }


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    search: str = "",
    slice_ids: Collection[str] = (),
    skeleton_only: bool = False,
) -> list[dict[str, Any]]:
    """Rows of the chosen slices with only the stories matching every filter."""
    needle = search.strip().casefold()

    def keep(story: dict[str, Any]) -> bool:
        text = f"{story['key']} {story['title']}".casefold()
        return (not skeleton_only or story["skeleton"]) and needle in text

    return [
        _with_count(
            {
                **row,
                "cells": [
                    {**cell, "stories": [s for s in cell["stories"] if keep(s)]}
                    for cell in row["cells"]
                ],
            }
        )
        for row in rows
        if not slice_ids or str(row["slice_id"]) in slice_ids
    ]


def list_rows(
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    stories: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stories as list lines: by activity, then slice, then their map order.

    ``stories`` is the lookup of ``build_view``; the map cards stay slim.
    """
    return [
        {
            "id": card["id"],
            "key": card["key"],
            "activity": column["title"],
            "title": card["title"],
            "story": stories[str(card["id"])]["sentence"],
            "description": stories[str(card["id"])]["description"],
        }
        for index, column in enumerate(columns)
        for row in rows
        for card in row["cells"][index]["stories"]
    ]


def filter_archived(
    stories: list[dict[str, Any]], search: str = ""
) -> list[dict[str, Any]]:
    """Archived stories whose key, title or old place contain the search text."""
    needle = search.strip().casefold()
    return [
        s
        for s in stories
        if needle in f"{s['key']} {s['title']} {s['where']}".casefold()
    ]
