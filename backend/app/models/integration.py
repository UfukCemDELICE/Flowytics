from datetime import datetime, timezone
from uuid import uuid4
from sqlmodel import SQLModel, Field

class Integration(SQLModel, table=True):
    __tablename__ = "integrations"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    provider: str  # CHECK: codat, plaid
    provider_connection_id: str
    credentials_encrypted: str | None = Field(default=None)
    platform_name: str | None = Field(default=None)
    sync_status: str = Field(default="pending")  # CHECK: pending, active, error, disconnected
    last_synced_at: datetime | None = Field(default=None)
    sync_cursor: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class IntegrationCreate(SQLModel):
    tenant_id: str
    provider: str
    provider_connection_id: str

class IntegrationRead(SQLModel):
    id: str
    tenant_id: str
    provider: str
    platform_name: str | None
    sync_status: str
    last_synced_at: datetime | None
