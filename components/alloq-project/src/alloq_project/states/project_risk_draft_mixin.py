"""Risk drafts and the risk matrix of the project drawer; mixed into
`ProjectState`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import reflex as rx
from alloq_commons.entities.risk import RiskMitigationStatus
from alloq_commons.models.project import Risk, RiskMatrixCell

_SCORE_LOW = 4
_SCORE_MEDIUM = 9
_SCORE_HIGH = 15
_SCORE_VERY_HIGH = 20
_DEFAULT_SCORE = 3


def _risk_score_color(score: int) -> str:
    """Return background color for a risk matrix cell based on score."""
    if score <= _SCORE_LOW:
        return "var(--alloq-risk-low)"
    if score <= _SCORE_MEDIUM:
        return "var(--alloq-risk-medium)"
    if score <= _SCORE_HIGH:
        return "var(--alloq-risk-high)"
    if score <= _SCORE_VERY_HIGH:
        return "var(--alloq-risk-very-high)"
    return "var(--alloq-risk-critical)"


def _clamp_score(value: str) -> int:
    """Parse a 1..5 risk score; invalid input becomes the default score."""
    try:
        return max(1, min(5, int(value or _DEFAULT_SCORE)))
    except TypeError, ValueError:
        return _DEFAULT_SCORE


class ProjectRiskDraftMixin(rx.State, mixin=True):
    """Inline risk draft (new or existing) and the derived risk views."""

    if TYPE_CHECKING:  # Provided by ProjectState.
        risks: list[Risk]

    # Risk draft state (0=none, -1=new unsaved, positive=editing existing)
    expanded_risk_id: rx.Field[int] = rx.field(0)
    risk_draft_name: rx.Field[str] = rx.field("")
    risk_draft_description: rx.Field[str] = rx.field("")
    risk_draft_measures: rx.Field[str] = rx.field("")
    risk_draft_impact: rx.Field[int] = rx.field(_DEFAULT_SCORE)
    risk_draft_probability: rx.Field[int] = rx.field(_DEFAULT_SCORE)
    risk_draft_mitigation_status: rx.Field[str] = rx.field(
        RiskMitigationStatus.OPEN.value
    )
    risk_draft_form_version: rx.Field[int] = rx.field(0)

    def _reset_risk_draft(self) -> None:
        """Close the risk draft and restore the field defaults."""
        self.expanded_risk_id = 0
        self.risk_draft_name = ""
        self.risk_draft_description = ""
        self.risk_draft_measures = ""
        self.risk_draft_impact = _DEFAULT_SCORE
        self.risk_draft_probability = _DEFAULT_SCORE
        self.risk_draft_mitigation_status = RiskMitigationStatus.OPEN.value

    @rx.event
    def add_project_risk(self) -> None:
        """Open a draft form for a new risk without persisting yet."""
        self._reset_risk_draft()
        self.expanded_risk_id = -1
        self.risk_draft_form_version += 1

    @rx.event
    def expand_risk(self, risk_id: int) -> None:
        """Toggle the inline edit form for an existing risk."""
        if self.expanded_risk_id == risk_id:
            self.expanded_risk_id = 0
            return
        risk = next((r for r in self.risks if r.id == risk_id), None)
        if not risk:
            return
        self.expanded_risk_id = risk_id
        self.risk_draft_name = risk.name
        self.risk_draft_description = risk.description
        self.risk_draft_measures = risk.measures
        self.risk_draft_impact = risk.auswirkung_score
        self.risk_draft_probability = risk.probability
        self.risk_draft_mitigation_status = risk.mitigation_status
        self.risk_draft_form_version += 1

    @rx.event
    def collapse_risk_edit(self) -> None:
        """Close the risk edit form without saving."""
        self.expanded_risk_id = 0

    @rx.event
    def set_risk_draft_name(self, value: str) -> None:
        """Update risk draft name."""
        self.risk_draft_name = value or ""

    @rx.event
    def set_risk_draft_description(self, value: str) -> None:
        """Update risk draft description."""
        self.risk_draft_description = value or ""

    @rx.event
    def set_risk_draft_measures(self, value: str) -> None:
        """Update risk draft measures."""
        self.risk_draft_measures = value or ""

    @rx.event
    def set_risk_draft_impact(self, value: str) -> None:
        """Update risk draft impact score (1-5)."""
        self.risk_draft_impact = _clamp_score(value)

    @rx.event
    def set_risk_draft_probability(self, value: str) -> None:
        """Update risk draft probability (1-5)."""
        self.risk_draft_probability = _clamp_score(value)

    @rx.event
    def set_risk_draft_mitigation_status(self, value: str) -> None:
        """Update risk draft mitigation status."""
        self.risk_draft_mitigation_status = value or RiskMitigationStatus.OPEN.value

    @rx.var
    def sorted_risks(self) -> list[Risk]:
        """Risks sorted by creation date descending (newest first)."""
        return sorted(self.risks, key=lambda r: r.created or "", reverse=True)

    @rx.var
    def risk_matrix_cells(self) -> list[RiskMatrixCell]:
        """Return 25 cells for the 5x5 risk matrix (row-major, top to bottom)."""
        cells = []
        for w in range(5, 0, -1):
            for a in range(1, 6):
                matching = [
                    r
                    for r in self.risks
                    if r.probability == w and r.auswirkung_score == a
                ]
                cells.append(
                    RiskMatrixCell(
                        w=w,
                        a=a,
                        score=w * a,
                        risk_numbers=[r.number for r in matching],
                        risk_names=[r.name for r in matching],
                        color=_risk_score_color(w * a),
                    )
                )
        return cells
