from datetime import datetime
from decimal import Decimal
from uuid import uuid4, UUID
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import SQLModel, Field, JSON

from backend.app.utils import utc_now

class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"
    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    tenant_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    trigger_type: str  # CHECK: scheduled, slack_message, webhook, manual
    trigger_payload: dict | None = Field(default=None, sa_column=Column(JSON))
    query: str | None = Field(default=None)
    response: str | None = Field(default=None)
    is_successful: bool = Field(default=False)
    status: str = Field(default="running")  # CHECK: running, completed, failed
    tools_called: list = Field(default=[], sa_column=Column(JSON))
    model_used: str | None = Field(default=None)
    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    cost_usd: Decimal = Field(default=Decimal("0"))
    duration_ms: int | None = Field(default=None)
    output_result: dict | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)

