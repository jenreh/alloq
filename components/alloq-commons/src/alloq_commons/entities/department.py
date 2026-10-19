from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from appkit_commons.database.entities import Base, Entity


class DepartmentEntity(Entity, Base):
    """Department of the organization; employees belong to at most one."""

    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    abbreviation: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    highlighted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "highlighted": self.highlighted or False,
            "created": self.created,
            "updated": self.updated,
        }
