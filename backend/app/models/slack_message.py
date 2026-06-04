from datetime import datetime
from uuid import uuid4, UUID
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import SQLModel, Field

from backend.app.utils import utc_now

class SlackMessage(SQLModel, table=True):
    __tablename__ = "slack_messages"
    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    tenant_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    direction: str  # CHECK: inbound, outbound
    slack_user_id: str | None = Field(default=None)
    slack_team_id: str | None = Field(default=None)
    slack_channel_id: str | None = Field(default=None)
    slack_ts: str | None = Field(default=None)
    slack_thread_ts: str | None = Field(default=None)
    content: str | None = Field(default=None)
    is_bot: bool = Field(default=False)
    agent_run_id: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), nullable=True))
    feedback: str | None = Field(default=None)  # CHECK: positive, negative, correction, NULL
    created_at: datetime = Field(default_factory=utc_now)

class SlackUserMap(SQLModel, table=True):
    __tablename__ = "slack_user_map"
    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    tenant_id: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), nullable=True, index=True))
    clerk_user_id: str | None = Field(default=None)
    slack_user_id: str = Field(unique=True)
    slack_team_id: str
    created_at: datetime = Field(default_factory=utc_now)

