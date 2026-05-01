import logging

from sqlalchemy import String
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

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "created": self.created,
            "updated": self.updated,
        }
