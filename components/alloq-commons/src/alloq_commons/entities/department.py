from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from appkit_commons.database.entities import Base, Entity


class DepartmentEntity(Entity, Base):
    """Department of the organization; employees belong to at most one."""

    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    abbreviation: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "created": self.created,
            "updated": self.updated,
        }
