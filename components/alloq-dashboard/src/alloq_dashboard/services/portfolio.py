"""Portfolio overview (dashboard variant C).

Four parts: time elapsed vs. progress per project, open risks as a 5x5
matrix, the resource-critical path per project, and capacity per role. The
scope is the whole department or the signed-in manager's direct reports.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from datetime import date

from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.entities.risk import RiskLevel

from alloq_dashboard.models import (
    PortfolioBubble,
    PortfolioKpi,
    PortfolioProject,
    PortfolioRoleLine,
    RiskItem,
    RiskMatrixCell,
    RiskMatrixRow,
)
from alloq_dashboard.services.portfolio_inputs import (
    SCOPE_DEPARTMENT,
    SCOPE_TEAM,
    PortfolioInputs,
    ProjectInput,
    RiskInput,
    apply_scope,
    load_inputs,
    team_employee_ids,
)
from alloq_dashboard.services.resource_path import (
    Calendar,
    Capacity,
    analyse_projects,
    buffer_label,
    buffer_tone,
    person_details,
    role_demands,
    role_details,
    weakest,
)

logger = logging.getLogger(__name__)

COMFORT_WEEKS = 4
MAX_CHAINS = 6
YELLOW_OVERRUN_RATIO = 1.10
BUBBLE_MIN_PX = 18
BUBBLE_GROWTH_PX = 42
LABEL_GAP_PX = 6
LABEL_FLIP_PERCENT = 85
LABEL_WIDTH_PX = 56
LABEL_HALF_HEIGHT_PX = 8
MATRIX_SIZE = 5
SEVERITY_LOW_MAX = 4
SEVERITY_MEDIUM_MAX = 15
_BANDS = ((4, "r1"), (9, "r2"), (15, "r3"), (19, "r4"))
_PLOTTED_STATES = frozenset(
    {ProjectStateEnum.ACTIVE.value, ProjectStateEnum.AT_RISK.value}
)

NO_PROFILE_NOTICE = (
    "Zu Ihrer Anmeldung gibt es kein Mitarbeiterprofil. "
    "Der Bereich „Direkt unterstellt“ bleibt deshalb leer."
)
EMPTY_TEAM_NOTICE = (
    "Ihnen ist niemand direkt unterstellt, und Sie verantworten keine Projekte."
)


def health(eac: float, budget: float) -> str:
    """Traffic light of EAC against budget, like ``_classify_overrun``."""
    if eac <= 0 or budget <= 0:
        return ""
    if eac <= budget:
        return "green"
    if eac <= budget * YELLOW_OVERRUN_RATIO:
        return "yellow"
    return "red"


def elapsed_percent(project: ProjectInput, today: date) -> int:
    total = (project.end_date - project.start_date).days
    if total <= 0:
        return 100
    done = (today - project.start_date).days
    return max(0, min(100, round(done / total * 100)))


def severity(score: int) -> str:
    if score <= SEVERITY_LOW_MAX:
        return RiskLevel.LOW.value
    if score <= SEVERITY_MEDIUM_MAX:
        return RiskLevel.MEDIUM.value
    return RiskLevel.HIGH.value


def risk_band(score: int) -> str:
    for limit, band in _BANDS:
        if score <= limit:
            return band
    return "r5"


def _thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _project(
    project: ProjectInput, lines: list[PortfolioRoleLine], today: date
) -> PortfolioProject:
    weak = weakest(lines)
    eac_delta = (
        (project.eac / project.budget - 1) * 100
        if project.eac > 0 and project.budget > 0
        else 0.0
    )
    buffer = weak.buffer_weeks if weak and weak.buffer_weeks is not None else 0
    return PortfolioProject(
        id=project.id,
        code=project.code,
        name=project.name,
        state=project.state,
        end_label=project.end_date.strftime("%d.%m.%Y"),
        progress=project.progress,
        elapsed_percent=elapsed_percent(project, today),
        budget=project.budget,
        eac=round(project.eac, 2),
        eac_delta_percent=round(eac_delta, 1),
        health=health(project.eac, project.budget),
        has_buffer=weak is not None,
        buffer_weeks=buffer,
        buffer_label=buffer_label(buffer) if weak else "",
        buffer_tone=buffer_tone(buffer) if weak else "",
        weakest=weak or PortfolioRoleLine(),
        roles=lines,
    )


def bubbles(projects: list[PortfolioProject]) -> list[PortfolioBubble]:
    """Plot data; bubble area grows with the budget."""
    plotted = [p for p in projects if p.state in _PLOTTED_STATES]
    max_budget = max((p.budget for p in plotted), default=0)
    result: list[PortfolioBubble] = []
    for p in plotted:
        ratio = math.sqrt(p.budget / max_budget) if max_budget > 0 else 0.0
        size = round(BUBBLE_MIN_PX + BUBBLE_GROWTH_PX * ratio)
        half = size / 2
        if p.elapsed_percent > LABEL_FLIP_PERCENT:
            label = (
                f"calc({p.elapsed_percent}% - {half + LABEL_GAP_PX + LABEL_WIDTH_PX}px)"
            )
        else:
            label = f"calc({p.elapsed_percent}% + {half + LABEL_GAP_PX}px)"
        result.append(
            PortfolioBubble(
                project_id=p.id,
                code=p.code,
                health=p.health,
                negative_buffer=p.has_buffer and p.buffer_weeks < 0,
                left=f"calc({p.elapsed_percent}% - {half}px)",
                top=f"calc({100 - p.progress}% - {half}px)",
                size=f"{size}px",
                label_left=label,
                label_top=f"calc({100 - p.progress}% - {LABEL_HALF_HEIGHT_PX}px)",
                tooltip=(
                    f"{p.code} {p.name}: {p.elapsed_percent} % Zeit, "
                    f"{p.progress} % Fortschritt, Budget {_thousands(p.budget)} €"
                ),
            )
        )
    return result


def not_plotted_label(projects: list[ProjectInput]) -> str:
    planned = sorted(
        p.code for p in projects if p.state == ProjectStateEnum.PLANNED.value
    )
    completed = sum(1 for p in projects if p.state == ProjectStateEnum.COMPLETED.value)
    parts: list[str] = []
    if planned:
        noun = "geplantes Projekt" if len(planned) == 1 else "geplante Projekte"
        parts.append(f"{len(planned)} {noun} ({', '.join(planned)})")
    if completed:
        noun = "abgeschlossenes" if completed == 1 else "abgeschlossene"
        parts.append(f"{completed} {noun}")
    return "Nicht im Diagramm: " + " und ".join(parts) + "." if parts else ""


def risk_matrix(risks: list[RiskInput]) -> list[RiskMatrixRow]:
    counts: dict[tuple[int, int], int] = {}
    for r in risks:
        counts[r.probability, r.impact] = counts.get((r.probability, r.impact), 0) + 1
    return [
        RiskMatrixRow(
            probability=p,
            cells=[
                RiskMatrixCell(
                    key=f"{p}-{i}",
                    probability=p,
                    impact=i,
                    score=p * i,
                    band=risk_band(p * i),
                    count=counts.get((p, i), 0),
                )
                for i in range(1, MATRIX_SIZE + 1)
            ],
        )
        for p in range(MATRIX_SIZE, 0, -1)
    ]


def risk_items(
    risks: list[RiskInput], projects: dict[int, ProjectInput]
) -> list[RiskItem]:
    items = [
        RiskItem(
            id=r.id,
            project_id=r.project_id,
            project_code=projects[r.project_id].code,
            project_name=projects[r.project_id].name,
            name=r.name,
            severity=severity(r.probability * r.impact),
            probability=r.probability,
            impact=r.impact,
            score=r.probability * r.impact,
            mitigation_status=r.mitigation_status,
        )
        for r in risks
    ]
    return sorted(items, key=lambda i: (-i.score, i.project_code, i.name))


def chains(projects: list[PortfolioProject]) -> tuple[list[PortfolioProject], str]:
    """Projects below the comfort buffer, and a line for the rest."""
    with_buffer = sorted(
        (p for p in projects if p.has_buffer),
        key=lambda p: (p.buffer_weeks, p.code),
    )
    tight = [p for p in with_buffer if p.buffer_weeks < COMFORT_WEEKS][:MAX_CHAINS]
    comfortable = [p for p in with_buffer if p.buffer_weeks >= COMFORT_WEEKS]
    parts: list[str] = []
    if comfortable:
        listed = ", ".join(f"{p.code} {p.buffer_label}" for p in comfortable)
        parts.append(f"Mit {COMFORT_WEEKS} Wochen Puffer oder mehr: {listed}.")
    missing = sum(1 for p in projects if not p.has_buffer)
    if missing:
        noun = "Projekt" if missing == 1 else "Projekte"
        parts.append(f"Ohne erfassten Bedarf: {missing} {noun}.")
    return tight, " ".join(parts)


def _notice(raw: PortfolioInputs, scoped: PortfolioInputs, scope: str) -> str:
    if scope != SCOPE_TEAM:
        return ""
    if raw.current_employee_id is None:
        return NO_PROFILE_NOTICE
    if not scoped.employees and not scoped.projects:
        return EMPTY_TEAM_NOTICE
    return ""


def build_portfolio(raw: PortfolioInputs, scope: str, today: date) -> PortfolioKpi:
    """Assemble the portfolio for ``scope`` from loaded inputs."""
    scope = scope if scope in (SCOPE_DEPARTMENT, SCOPE_TEAM) else SCOPE_DEPARTMENT
    scoped = apply_scope(raw, scope)
    capacity = Capacity(scoped, Calendar.for_today(today))
    lines = analyse_projects(scoped, capacity)
    projects = [
        _project(p, lines[p.id], today)
        for p in sorted(scoped.projects, key=lambda p: p.code)
        if p.id in lines
    ]
    by_id = {p.id: p for p in scoped.projects}
    open_risks = [
        r for r in raw.risks if r.project_id in by_id and r.mitigation_status == "open"
    ]
    items = risk_items(open_risks, by_id)
    tight, comfortable = chains(projects)
    roles = role_demands(scoped, capacity, lines)
    return PortfolioKpi(
        scope=scope,
        notice=_notice(raw, scoped, scope),
        department_employee_count=len(raw.all_employees),
        team_employee_count=len(team_employee_ids(raw)),
        projects=projects,
        bubbles=bubbles(projects),
        not_plotted_label=not_plotted_label(list(scoped.projects)),
        matrix=risk_matrix(open_risks),
        risks=items,
        risk_open_total=len(items),
        risk_high=sum(1 for i in items if i.severity == RiskLevel.HIGH.value),
        risk_medium=sum(1 for i in items if i.severity == RiskLevel.MEDIUM.value),
        risk_low=sum(1 for i in items if i.severity == RiskLevel.LOW.value),
        chains=tight,
        comfortable_label=comfortable,
        roles=roles,
        gap_total=round(sum(r.gap_days for r in roles), 1),
        role_details=role_details(scoped, capacity, lines),
        person_details=person_details(scoped, capacity, lines),
    )


async def load_portfolio(scope: str, email: str | None) -> PortfolioKpi:
    today = dt.datetime.now(tz=dt.UTC).date()
    raw = await load_inputs(today, email)
    return build_portfolio(raw, scope, today)
