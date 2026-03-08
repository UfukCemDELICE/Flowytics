from datetime import datetime, timezone
from uuid import uuid4
from sqlmodel import SQLModel, Field

class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    clerk_org_id: str = Field(unique=True, index=True)
    name: str
    stage: str = Field(default="pre_seed")  # CHECK: pre_seed, seed, series_a, series_b
    currency: str = Field(default="USD")
    slack_team_id: str | None = Field(default=None)
    slack_channel_id: str | None = Field(default=None)
    onboarding_completed: bool = Field(default=False)
    subscription_status: str = Field(default="trial")  # CHECK: trial, active, past_due, cancelled, churned
    stripe_customer_id: str | None = Field(default=None)
    stripe_subscription_id: str | None = Field(default=None)
    trial_started_at: datetime | None = Field(default=None)
    trial_ends_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TenantCreate(SQLModel):
    clerk_org_id: str
    name: str

class TenantRead(SQLModel):
    id: str
    name: str
    stage: str
    currency: str
    onboarding_completed: bool
    subscription_status: str
    created_at: datetime
