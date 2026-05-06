import logging

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class RoleEntity(Entity, Base):
    """Organizational role entity for team member assignment."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ramp_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ramp_down: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "ramp_up": self.ramp_up or False,
            "ramp_down": self.ramp_down or False,
            "created": self.created,
            "updated": self.updated,
        }
