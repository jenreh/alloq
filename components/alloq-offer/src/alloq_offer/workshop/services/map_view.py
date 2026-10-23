"""The story map as a grid of plain values for the page (from a map snapshot)."""

from typing import Any

NO_SLICE_ID = 0
NO_SLICE_TITLE = "Ohne Umsetzungsschnitt"
ORIGIN_SOURCE = "Quellenstellen"


def _card(story: dict, task_title: str) -> dict[str, Any]:
    refs = len(story["source_refs"])
    return {
        "id": story["id"],
        "key": story["key"],
        "title": story["title"],
        "meta": f"{task_title} · {story['scope']} · {story['origin']}",
        "scope": story["scope"],
        "skeleton": story["skeleton"],
        "origin": story["origin"],
        "sentence": story["sentence"],
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
            _card(s, t["title"])
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
        {
            "slice_id": slice_id,
            "title": title,
            "editable": editable,
            "cells": [cell(a, slice_id) for a in activities],
        }
        for slice_id, title, editable in row_defs
    ]
    lookup = {
        str(story["id"]): {
            **_card(story, task["title"]),
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
    return {
        "columns": columns,
        "rows": rows,
        "stories": lookup,
        "story_count": len(lookup),
        "task_options": [
            {"value": str(t["id"]), "label": f"{a['title']} · {t['title']}"}
            for a in activities
            for t in tasks_of[a["id"]]
        ],
        "slice_options": [{"value": str(NO_SLICE_ID), "label": NO_SLICE_TITLE}]
        + [{"value": str(s["id"]), "label": s["title"]} for s in slices],
    }
