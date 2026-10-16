"""Entra ID settings of the desktop app (all public, none of them a secret)."""

from typing import Final

from pydantic import BaseModel

POSTGRES_SCOPE: Final = "https://ossrdbms-aad.database.windows.net/.default"
"""Access tokens for Azure Database for PostgreSQL."""


class DesktopConfig(BaseModel):
    tenant_id: str = ""
    client_id: str = ""
    """App registration of the desktop app: public client, redirect
    `http://localhost`, delegated permission for Azure OSSRDBMS."""
    db_scope: str = POSTGRES_SCOPE
    db_role: str = ""
    """Postgres role to log in as. Empty: the user's own principal (UPN).
    Set it to the Entra group name when the group is the database principal."""
    sign_in_timeout: int = 300  # seconds the browser sign-in may take

    @property
    def configured(self) -> bool:
        values = (self.tenant_id, self.client_id)
        return all(v and not v.startswith("<") for v in values)

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"
