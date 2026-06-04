from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import SQLModel, Field

from backend.app.utils import utc_now

class Integration(SQLModel, table=True):
    __tablename__ = "integrations"
    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    tenant_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    provider: str  # CHECK: quickbooks
    provider_connection_id: str
    credentials_encrypted: str | None = Field(default=None)
    platform_name: str | None = Field(default=None)
    sync_status: str = Field(default="pending")  # CHECK: pending, active, error, disconnected
    last_synced_at: datetime | None = Field(default=None)
    sync_cursor: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)

class IntegrationCreate(SQLModel):
    tenant_id: UUID
    provider: str
    provider_connection_id: str

class IntegrationRead(SQLModel):
    id: UUID
    tenant_id: UUID
    provider: str
    platform_name: str | None
    sync_status: str
    last_synced_at: datetime | None
