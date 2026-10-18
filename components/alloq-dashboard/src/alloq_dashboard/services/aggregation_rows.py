"""Plain transport rows for the dashboard aggregation.

Every needed entity attribute is copied into a frozen dataclass while the
session is still open, so reducers never touch lazy ORM relationships.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from alloq_commons.entities.capacity_allocation import CapacityAllocationEntity
from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.entities.project import ProjectEntity
from alloq_commons.entities.risk import (
    HIGH_RISK_SCORE_THRESHOLD,
    RiskEntity,
    RiskLevel,
    RiskMitigationStatus,
)
from alloq_commons.entities.role import RoleEntity
from alloq_commons.entities.status import ProjectStatusEntity
from alloq_commons.models.employee import STANDARD_WEEKLY_HOURS
from alloq_commons.repositories.risk_repository import MAX_RISK_IMPACT, MIN_RISK_IMPACT

SEVERITY_LOW_MAX = 4
SEVERITY_MEDIUM_MAX = 15

_ROLE_COLORS = [
    "#4ade80",  # green
    "#facc15",  # yellow
    "#60a5fa",  # blue
    "#fb923c",  # orange
    "#c084fc",  # purple
    "#f87171",  # red
    "#34d399",  # emerald
    "#a78bfa",  # violet
    "#38bdf8",  # sky
    "#f472b6",  # pink
]


@dataclass(frozen=True)
class _ProjectRow:
    id: int
    code: str
    name_de: str
    state: str
    start_date: date | None
    end_date: date | None
    budget: int
    color: str
    progress: int
    spent: int
    open_risk_count: int
    created_date: date | None = None
    ev_earned_value: float = 0.0
    ev_actual_cost: float = 0.0
    ev_eac_linear: float = 0.0
    ev_eac_additive: float = 0.0


@dataclass(frozen=True)
class _RiskRow:
    id: int
    project_id: int
    name: str
    severity: str
    probability: int
    impact: int
    mitigation_status: str
    owner: str | None
    created_date: date | None
    updated_date: date | None


@dataclass(frozen=True)
class _StatusRow:
    project_id: int
    status_date: date
    progress: int
    budget_spent: int
    budget: float | None = None
    earned_value: float | None = None
    actual_cost: float | None = None
    eac_linear: float | None = None
    eac_additive: float | None = None


@dataclass(frozen=True)
class _AllocationRow:
    project_id: int
    employee_id: int
    role_id: int
    week_start: date
    person_days: float


@dataclass(frozen=True)
class _AbsenceRow:
    start_date: date
    end_date: date


@dataclass(frozen=True)
class _EmployeeRow:
    id: int
    first_name: str
    last_name: str
    hours_per_week: float
    internal_hours: int
    role_ids: tuple[int, ...]
    role_names: tuple[str, ...]
    absences: tuple[_AbsenceRow, ...]

    @property
    def workload_percent(self) -> int:
        return round(self.hours_per_week / STANDARD_WEEKLY_HOURS * 100)


@dataclass(frozen=True)
class _RoleRow:
    id: int
    name: str
    color: str = "#888"


def _risk_score(probability: int, impact: int) -> int:
    """Score with impact clamped to 1..5, same as ``RiskRepository``."""
    return probability * max(MIN_RISK_IMPACT, min(MAX_RISK_IMPACT, impact))


def _project_to_row(entity: ProjectEntity) -> _ProjectRow:
    latest = entity.statuses[0] if entity.statuses else None
    open_risks = sum(
        1
        for r in entity.risks or []
        if r.mitigation_status == RiskMitigationStatus.OPEN.value
        and _risk_score(r.probability, r.impact) >= HIGH_RISK_SCORE_THRESHOLD
    )
    created = entity.created.date() if entity.created else None
    return _ProjectRow(
        id=entity.id,
        code=entity.code,
        name_de=entity.name_de,
        state=entity.state,
        start_date=entity.start_date,
        end_date=entity.end_date,
        budget=entity.budget or 0,
        color=entity.color or "#888",
        progress=latest.progress if latest else 0,
        spent=latest.budget_spent if latest else 0,
        open_risk_count=open_risks,
        created_date=created,
        ev_earned_value=entity.ev_earned_value or 0.0,
        ev_actual_cost=entity.ev_actual_cost or 0.0,
        ev_eac_linear=entity.ev_eac_linear or 0.0,
        ev_eac_additive=entity.ev_eac_additive or 0.0,
    )


def _severity_from_score(probability: int, impact: int) -> str:
    """Derive severity label from probability * impact."""
    score = probability * impact
    if score <= SEVERITY_LOW_MAX:
        return RiskLevel.LOW.value
    if score <= SEVERITY_MEDIUM_MAX:
        return RiskLevel.MEDIUM.value
    return RiskLevel.HIGH.value


def _risk_to_row(entity: RiskEntity) -> _RiskRow:
    created = entity.created.date() if entity.created else None
    updated = entity.updated.date() if entity.updated else None
    return _RiskRow(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        severity=_severity_from_score(entity.probability, entity.impact),
        probability=entity.probability,
        impact=entity.impact,
        mitigation_status=entity.mitigation_status,
        owner=None,
        created_date=created,
        updated_date=updated,
    )


def _status_to_row(entity: ProjectStatusEntity) -> _StatusRow:
    return _StatusRow(
        project_id=entity.project_id,
        status_date=entity.status_date,
        progress=entity.progress,
        budget_spent=entity.budget_spent,
        budget=entity.budget,
        earned_value=entity.earned_value,
        actual_cost=entity.actual_cost,
        eac_linear=entity.eac_linear,
        eac_additive=entity.eac_additive,
    )


def _allocation_to_row(entity: CapacityAllocationEntity) -> _AllocationRow:
    return _AllocationRow(
        project_id=entity.project_id,
        employee_id=entity.employee_id,
        role_id=entity.role_id,
        week_start=entity.week_start,
        person_days=float(entity.person_days),
    )


def _employee_to_row(entity: EmployeeEntity) -> _EmployeeRow:
    roles = entity.roles or []
    absences = tuple(
        _AbsenceRow(start_date=absence.start_date, end_date=absence.end_date)
        for absence in entity.absences or []
        if absence.start_date and absence.end_date
    )
    return _EmployeeRow(
        id=entity.id,
        first_name=entity.first_name,
        last_name=entity.last_name,
        hours_per_week=float(entity.hours_per_week or 40.0),
        internal_hours=int(entity.internal_hours or 0),
        role_ids=tuple(role.id for role in roles),
        role_names=tuple(role.name for role in roles),
        absences=absences,
    )


def _role_to_row(entity: RoleEntity, index: int = 0) -> _RoleRow:
    color = _ROLE_COLORS[index % len(_ROLE_COLORS)]
    return _RoleRow(id=entity.id, name=entity.name, color=color)
