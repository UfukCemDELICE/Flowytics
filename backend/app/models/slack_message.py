from datetime import datetime, timezone
from uuid import uuid4
from sqlmodel import SQLModel, Field

class SlackMessage(SQLModel, table=True):
    __tablename__ = "slack_messages"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    direction: str  # CHECK: inbound, outbound
    slack_user_id: str | None = Field(default=None)
    slack_ts: str | None = Field(default=None)
    thread_ts: str | None = Field(default=None)
    content: str | None = Field(default=None)
    agent_run_id: str | None = Field(default=None, foreign_key="agent_runs.id")
    feedback: str | None = Field(default=None)  # CHECK: positive, negative, correction, NULL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SlackUserMap(SQLModel, table=True):
    __tablename__ = "slack_user_map"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    clerk_user_id: str
    slack_user_id: str = Field(unique=True)
    slack_team_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
