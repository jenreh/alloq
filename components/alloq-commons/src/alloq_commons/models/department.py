from datetime import datetime

from pydantic import BaseModel, Field


class Department(BaseModel):
    """Read model for departments."""

    id: int = 0
    name: str = ""
    abbreviation: str = ""
    created: datetime | None = None
    updated: datetime | None = None

    @property
    def label(self) -> str:
        """Name with abbreviation, e.g. 'Informationstechnik (IT)'."""
        return f"{self.name} ({self.abbreviation})"


class DepartmentCreate(BaseModel):
    """Write model for creating/updating departments."""

    name: str = Field(..., min_length=1, max_length=255)
    abbreviation: str = Field(..., min_length=1, max_length=10)
