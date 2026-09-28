import logging

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class RequiredCapacityEntity(Entity, Base):
    """Required project staffing in person-days for a role."""

    __tablename__ = "required_capacities"
    __table_args__ = (
        CheckConstraint("person_days >= 0", name="ck_required_capacities_pd"),
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    person_days: Mapped[int] = mapped_column(Integer, nullable=False)

    project = relationship(
        "ProjectEntity", back_populates="required_capacities", lazy="raise_on_sql"
    )
    role = relationship("RoleEntity", lazy="selectin")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "role_id": self.role_id,
            "role_name": self.role.name if self.role else "",
            "person_days": self.person_days,
            "created": self.created,
            "updated": self.updated,
        }
