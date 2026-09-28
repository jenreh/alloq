import logging

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import RiskEntity
from alloq_commons.entities.risk import (
    HIGH_RISK_SCORE_THRESHOLD,
    RiskMitigationStatus,
)
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)

MIN_RISK_IMPACT = 1
MAX_RISK_IMPACT = 5


class RiskRepository(BaseRepository[RiskEntity, AsyncSession]):
    """Async repository for project risks."""

    @property
    def model_class(self) -> type[RiskEntity]:
        return RiskEntity

    async def find_by_project_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[RiskEntity]:
        """Find risks for a project."""
        statement = select(RiskEntity).where(RiskEntity.project_id == project_id)
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def find_open_by_min_score(
        self,
        session: AsyncSession,
        min_score: int = HIGH_RISK_SCORE_THRESHOLD,
    ) -> list[RiskEntity]:
        """Find open risks with score >= min_score, ordered by score DESC.

        The score clamps impact to 1..5 exactly like the ``Risk`` read model.
        """
        clamped_impact = case(
            (RiskEntity.impact < MIN_RISK_IMPACT, MIN_RISK_IMPACT),
            (RiskEntity.impact > MAX_RISK_IMPACT, MAX_RISK_IMPACT),
            else_=RiskEntity.impact,
        )
        risk_score = RiskEntity.probability * clamped_impact
        statement = (
            select(RiskEntity)
            .where(
                RiskEntity.mitigation_status == RiskMitigationStatus.OPEN.value,
                risk_score >= min_score,
            )
            .order_by(risk_score.desc())
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


risk_repo = RiskRepository()
