"""Tests for client-driven cell editing in PlanningStore."""

import math
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_project.services.planning_builders import (
    build_weeks,
    cell_key,
    dirty_keys_for,
    parse_cell_changes,
)
from alloq_project.states.planning_grid_state import PlanningStore

_STATE = "alloq_project.states.planning_grid_state"


def _store(view_mode: str = "Grid") -> PlanningStore:
    weeks, spans = build_weeks(3)
    state = PlanningStore()  # type: ignore[call-arg]
    state.view_mode = view_mode
    state.weeks = weeks
    state.month_spans = spans
    state.employee_meta = [
        {
            "id": "emp-1",
            "real_id": 1,
            "name": "Alice A",
            "initials": "AA",
            "project_ids": ["proj-1", "proj-2"],
            "role_ids": [3],
        },
        {
            "id": "emp-2",
            "real_id": 2,
            "name": "Bob B",
            "initials": "BB",
            "project_ids": ["proj-2"],
            "role_ids": [4],
        },
    ]
    state.project_meta = [
        {"id": "proj-1", "real_id": 1, "code": "A", "name": "Alpha", "color": "#000"},
        {"id": "proj-2", "real_id": 2, "code": "B", "name": "Beta", "color": "#fff"},
    ]
    state.cells = {cell_key("emp-1", "A", weeks[0].key): 1.0}
    state.saved_cells = dict(state.cells)
    return state


def _key(state: PlanningStore, emp: str, code: str, week_idx: int = 0) -> str:
    return cell_key(emp, code, state.weeks[week_idx].key)


def _mock_session_ctx(session: AsyncMock) -> Any:
    @asynccontextmanager
    async def _ctx():  # noqa: ANN202
        yield session

    return _ctx


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


class TestParseCellChanges:
    rows = {("emp-1", "A")}
    weeks = {"2026_01_05"}

    def _parse(self, *changes: Any) -> tuple[dict[str, float], int]:
        return parse_cell_changes(list(changes), self.rows, self.weeks)

    def test_accepts_valid_change(self) -> None:
        assert self._parse({"key": "emp-1|A|2026_01_05", "value": 2}) == (
            {"emp-1|A|2026_01_05": 2.0},
            0,
        )

    def test_rounds_to_two_decimals(self) -> None:
        updates, _ = self._parse({"key": "emp-1|A|2026_01_05", "value": 1.23456})
        assert updates["emp-1|A|2026_01_05"] == 1.23

    def test_zero_is_valid(self) -> None:
        assert self._parse({"key": "emp-1|A|2026_01_05", "value": 0})[1] == 0

    @pytest.mark.parametrize(
        "change",
        [
            {"key": "emp-1|A|2026_01_05", "value": -1},
            {"key": "emp-1|A|2026_01_05", "value": math.nan},
            {"key": "emp-1|A|2026_01_05", "value": math.inf},
            {"key": "emp-1|A|2026_01_05", "value": "2"},
            {"key": "emp-1|A|2026_01_05", "value": True},
            {"key": "emp-1|A|2026_01_05", "value": None},
            {"key": "emp-1|B|2026_01_05", "value": 1},
            {"key": "emp-2|A|2026_01_05", "value": 1},
            {"key": "emp-1|A|2030_01_07", "value": 1},
            {"key": "emp-1|A", "value": 1},
            {"key": 42, "value": 1},
            {"value": 1},
            "emp-1|A|2026_01_05",
        ],
    )
    def test_rejects_invalid_change(self, change: Any) -> None:
        assert self._parse(change) == ({}, 1)

    def test_mixed_batch(self) -> None:
        updates, rejected = self._parse(
            {"key": "emp-1|A|2026_01_05", "value": 1.5},
            {"key": "emp-1|A|2026_01_05", "value": -3},
        )
        assert updates == {"emp-1|A|2026_01_05": 1.5}
        assert rejected == 1


class TestDirtyKeysFor:
    def test_changed_and_new_keys_are_dirty(self) -> None:
        cells = {"a": 1.0, "b": 2.0, "c": 0.0, "d": 3.0}
        saved = {"a": 1.0, "b": 1.0, "c": 0.0}
        assert dirty_keys_for(cells, saved) == ["b", "d"]

    def test_new_zero_key_is_clean(self) -> None:
        assert dirty_keys_for({"a": 0.0}, {}) == []


class TestApplyCellChanges:
    def test_applies_batch_and_marks_dirty(self) -> None:
        state = _store()
        k1 = _key(state, "emp-1", "B", 1)
        k2 = _key(state, "emp-2", "B", 2)

        result = state.apply_cell_changes(
            [{"key": k1, "value": 2.5}, {"key": k2, "value": 1}]
        )

        assert result is None
        assert state.cells[k1] == 2.5
        assert state.cells[k2] == 1.0
        assert state.dirty_keys == sorted([k1, k2])
        assert state.has_dirty is True

    def test_reverting_to_saved_value_clears_dirty(self) -> None:
        state = _store()
        key = _key(state, "emp-1", "A")

        state.apply_cell_changes([{"key": key, "value": 4}])
        assert state.dirty_keys == [key]

        state.apply_cell_changes([{"key": key, "value": 1}])
        assert state.dirty_keys == []

    def test_rejects_unassigned_project_and_warns(self) -> None:
        state = _store()
        key = _key(state, "emp-2", "A")

        result = state.apply_cell_changes([{"key": key, "value": 1}])

        assert result is not None
        assert key not in state.cells
        assert state.dirty_keys == []

    def test_updates_employee_pivot_and_gesamt(self) -> None:
        state = _store()
        key = _key(state, "emp-2", "B")

        state.apply_cell_changes([{"key": key, "value": 2}])

        bob = next(e for e in state.filtered_employees if e.id == "emp-2")
        assert bob.projects[0].cells[0].value == 2.0
        assert bob.projects[0].cells[0].is_dirty is True


class TestViewGating:
    def test_grid_view_only_sends_filtered_employees(self) -> None:
        state = _store("Grid")
        assert len(state.filtered_employees) == 2
        assert state.filtered_projects == []
        assert state.employees == []
        assert state.avg_heat == []

    def test_heatmap_view_only_sends_heat_data(self) -> None:
        state = _store("Heatmap")
        assert state.filtered_employees == []
        assert len(state.employees) == 2
        assert len(state.avg_heat) == len(state.weeks)

    def test_project_view_only_sends_filtered_projects(self) -> None:
        state = _store("Projekte")
        assert state.filtered_employees == []
        assert [p.code for p in state.filtered_projects] == ["A", "B"]


class TestPopulate:
    @pytest.mark.asyncio
    async def test_populate_snapshots_cells_and_bumps_revision(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        state.dirty_keys = ["stale"]
        with (
            patch.object(
                PlanningStore, "_fetch_holidays", AsyncMock(return_value=set())
            ),
            patch.object(
                PlanningStore, "_fetch_data", AsyncMock(return_value=([], []))
            ),
        ):
            await state._populate(2)

        assert state.grid_revision == 1
        assert state.dirty_keys == []
        assert state.saved_cells == state.cells
        assert len(state.weeks) == 2


class TestSaveGrid:
    @pytest.mark.asyncio
    async def test_save_resets_snapshot_and_dirty(self) -> None:
        state = _store()
        key = _key(state, "emp-1", "A", 1)
        state.apply_cell_changes([{"key": key, "value": 2}])
        session = AsyncMock()

        with (
            patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(session)),
            patch(
                f"{_STATE}.capacity_allocation_repo.batch_upsert", AsyncMock()
            ) as upsert,
        ):
            await _drain(state.save_grid())

        rows = upsert.await_args.args[1]
        assert [r["person_days"] for r in rows] == [2.0]
        assert state.dirty_keys == []
        assert state.saved_cells[key] == 2.0
        assert state.is_saving is False

    @pytest.mark.asyncio
    async def test_save_is_noop_while_saving(self) -> None:
        state = _store()
        state.is_saving = True
        state.dirty_keys = ["x"]

        assert await _drain(state.save_grid()) == []
        assert state.dirty_keys == ["x"]
