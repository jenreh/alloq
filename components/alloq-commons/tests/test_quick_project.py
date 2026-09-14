"""Tests for minimal-input (quick-create) project creation."""

import datetime

import pytest
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.repositories import project_repo
from alloq_commons.services.quick_project import (
    MAX_CODE_LENGTH,
    PLACEHOLDER_DURATION_DAYS,
    QuickProjectError,
    create_quick_project,
)
from sqlalchemy.ext.asyncio import AsyncSession


class TestCreateQuickProject:
    """Tests for create_quick_project."""

    @pytest.mark.asyncio
    async def test_returns_read_model_with_defaults(
        self, async_session: AsyncSession
    ) -> None:
        project = await create_quick_project(async_session, "Neue Plattform", "NEU")

        today = datetime.date.today()  # noqa: DTZ011
        assert project.id > 0
        assert project.name_de == "Neue Plattform"
        assert project.code == "NEU"
        assert project.budget == 0
        assert project.state == ProjectStateEnum.PLANNED
        assert project.start_date == today
        assert project.end_date == today + datetime.timedelta(
            days=PLACEHOLDER_DURATION_DAYS
        )

    @pytest.mark.asyncio
    async def test_persists_project(self, async_session: AsyncSession) -> None:
        await create_quick_project(async_session, "Neue Plattform", "NEU")

        stored = await project_repo.find_by_code(async_session, "NEU")

        assert stored is not None
        assert stored.name_de == "Neue Plattform"
        assert stored.budget == 0

    @pytest.mark.asyncio
    async def test_creates_no_status_or_capacity_rows(
        self, async_session: AsyncSession
    ) -> None:
        project = await create_quick_project(async_session, "Neue Plattform", "NEU")

        stored = await project_repo.find_by_id(async_session, project.id)

        assert stored is not None
        assert stored.statuses == []
        assert stored.required_capacities == []

    @pytest.mark.asyncio
    async def test_trims_surrounding_whitespace(
        self, async_session: AsyncSession
    ) -> None:
        project = await create_quick_project(
            async_session, "  Neue Plattform  ", "  NEU  "
        )

        assert project.name_de == "Neue Plattform"
        assert project.code == "NEU"

    @pytest.mark.asyncio
    async def test_rejects_blank_name(self, async_session: AsyncSession) -> None:
        with pytest.raises(QuickProjectError, match="Projektnamen"):
            await create_quick_project(async_session, "   ", "NEU")

    @pytest.mark.asyncio
    async def test_rejects_blank_code(self, async_session: AsyncSession) -> None:
        with pytest.raises(QuickProjectError, match="Projektkürzel"):
            await create_quick_project(async_session, "Neue Plattform", "  ")

    @pytest.mark.asyncio
    async def test_rejects_overlong_code(self, async_session: AsyncSession) -> None:
        too_long = "X" * (MAX_CODE_LENGTH + 1)

        with pytest.raises(QuickProjectError, match="höchstens"):
            await create_quick_project(async_session, "Neue Plattform", too_long)

    @pytest.mark.asyncio
    async def test_rejects_duplicate_code(self, async_session: AsyncSession) -> None:
        await create_quick_project(async_session, "Neue Plattform", "NEU")

        with pytest.raises(QuickProjectError, match="bereits vergeben"):
            await create_quick_project(async_session, "Andere Plattform", "NEU")
