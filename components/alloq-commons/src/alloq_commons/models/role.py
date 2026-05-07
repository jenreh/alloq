from datetime import datetime

from pydantic import BaseModel, Field


class Role(BaseModel):
    """Read model for organizational roles."""

    id: int = 0
    name: str = ""
    abbreviation: str = ""
    description: str = ""
    ramp_up: bool = False
    ramp_down: bool = False
    created: datetime | None = None
    updated: datetime | None = None


class RoleCreate(BaseModel):
    """Write model for creating/updating roles."""

    name: str = Field(..., max_length=255)
    abbreviation: str = Field(default="", max_length=3)
    description: str = ""
    ramp_up: bool = False
    ramp_down: bool = False
