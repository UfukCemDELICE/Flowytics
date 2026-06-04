# Backend

## Python Conventions

### Package Management
- **uv only.** Never pip. `uv add <package>` to add, `uv sync` to install, `uv run` to execute.
- Lock file (`uv.lock`) committed to git. Reproducible builds.
- Prefer Rust-based packages where production-ready alternatives exist:
  - `polars` over pandas (Rust-based DataFrame, 10-50x faster)
  - `orjson` over json (Rust-based JSON serializer, 3-10x faster)
  - `ruff` over flake8/black (Rust-based linter + formatter)
  - `pydantic` v2 (pydantic-core is Rust)
  - `cryptography` (uses Rust for crypto operations)

### Type Safety
- Type hints on every function signature and return type.
- Pydantic models for all data boundaries (API input/output, tool input/output, config).
- `mypy` in strict mode for type checking.
- `Decimal` for all financial amounts. Never `float`. Import from `decimal`.

### Code Style
- `ruff` for linting and formatting. Single tool, fast.
- Max line length: 100 characters.
- Imports: stdlib → third-party → local, separated by blank lines.
- Docstrings: Google style. Required on all public functions.

## ORM — SQLModel

SQLModel combines Pydantic and SQLAlchemy. One model class serves as both DB table definition and API validation schema. This is DRY.

### Why SQLModel (not supabase-py)
- Proper ORM with relationships, type safety, query builder
- Direct Postgres connection via asyncpg (faster than REST API)
- Same model validates API input AND maps to DB table
- Alembic migrations when schema changes (post-MVP)
- FastAPI creator built it — natural integration

### Database Connection

```python
# backend/app/database.py
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=5)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

Supabase provides PgBouncer connection pooler URL — use it for production.

### Model Pattern

```python
# backend/app/models/tenant.py
from sqlmodel import SQLModel, Field
from datetime import datetime
from uuid import uuid4

class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    clerk_org_id: str = Field(unique=True, index=True)
    name: str
    subscription_status: str = Field(default="trial")
    # ... see db.md for full schema

class TenantCreate(SQLModel):
    """API input — no id, no defaults."""
    clerk_org_id: str
    name: str

class TenantRead(SQLModel):
    """API output — safe fields only."""
    id: str
    name: str
    subscription_status: str
```

Three classes per entity: `Table` (DB), `Create` (input), `Read` (output).

## FastAPI Patterns

### Application Startup

```python
# backend/app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_all_tenants, "cron", hour=6)
    scheduler.add_job(check_thresholds, "cron", hour=7)
    scheduler.add_job(generate_monthly_reports, "cron", day=1, hour=9)
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown()

app = FastAPI(title="Flowytics API", version="0.1.0", lifespan=lifespan)
```

Slack Bolt mounted as ASGI middleware inside the same app.

### Auth Middleware

```python
# backend/app/auth.py
from fastapi import Depends, HTTPException, Header
import jwt
from app.config import settings

async def get_current_user(authorization: str = Header(...)) -> dict:
    """Extract and verify Clerk JWT. Returns user claims."""
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, settings.CLERK_SECRET_KEY, algorithms=["RS256"])
        return {"user_id": payload["sub"], "org_id": payload.get("org_id")}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

Every protected route depends on `get_current_user`. The `org_id` maps to `tenant_id`.

### API Route Pattern

```python
# backend/app/api/v1/health.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])

@router.get("/health")
async def health():
    return {"status": "ok"}
```

All routes under `/api/v1/`. Routers registered in `main.py`.

### Background Tasks for Slack

```python
@router.post("/api/v1/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    # Acknowledge immediately (Slack 3-second rule)
    background_tasks.add_task(process_slack_message, payload)
    return {"ok": True}
```

### Error Handling

```python
# Standardized error responses
from fastapi import HTTPException

# Integration errors — graceful degradation
class IntegrationError(Exception):
    """QuickBooks API failure."""
    pass

@app.exception_handler(IntegrationError)
async def integration_error_handler(request, exc):
    return JSONResponse(status_code=502, content={
        "error": "integration_unavailable",
        "message": "Using last known data. Live data temporarily unavailable."
    })
```

**Error categories:**
| Source | Strategy |
|--------|----------|
| QuickBooks 401 | Auto-refresh token → retry once |
| QuickBooks 429 | Exponential backoff, use cached data |
| QuickBooks 500 | Use last snapshot with "stale" warning |
| Claude timeout | Retry once, then return tool-only results |
| Claude rate limit | Queue, notify user of delay |
| LLM number mismatch | Use tool numbers, log discrepancy |
| Slack user not mapped | Reply with connection link |
| QB not connected | Reply with connection instructions |

## Data Processing — Polars

Use Polars for all financial data transformations. Convert raw JSONB from DB to Polars DataFrame, compute metrics, return results.

```python
import polars as pl
from decimal import Decimal

def calculate_monthly_burn(transactions: list[dict]) -> Decimal:
    df = pl.DataFrame(transactions)
    monthly = df.group_by("month").agg(
        pl.col("amount").filter(pl.col("type") == "expense").sum().alias("total_expenses"),
        pl.col("amount").filter(pl.col("type") == "income").sum().alias("total_income"),
    )
    monthly = monthly.with_columns(
        (pl.col("total_expenses") - pl.col("total_income")).alias("net_burn")
    )
    # Weighted average — recent months weighted higher
    # ... (see tools in agents.md for full specs)
```

**Why Polars over raw Python loops:**
- Rust-based execution — handles 100K+ transactions without performance concern
- Built-in group_by, rolling window, linear regression
- Memory efficient — columnar storage
- Will matter when tenants accumulate years of financial data

## Prompt Management

Plain text files in `backend/app/prompts/`. No DSPy, no framework.

```
backend/app/prompts/
├── slack_chat.txt              # Haiku — conversational responses
├── report_generation.txt       # Sonnet — monthly CFO report
├── scenario_analysis.txt       # Opus — what-if simulation narrative
├── anomaly_interpretation.txt  # Sonnet — explain detected anomalies
└── system_base.txt             # Shared system context (appended to all)
```

### Prompt Loading

```python
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str, **kwargs) -> str:
    """Load prompt template and format with kwargs."""
    template = (PROMPT_DIR / f"{name}.txt").read_text()
    base = (PROMPT_DIR / "system_base.txt").read_text()
    return base + "\n\n" + template.format(**kwargs)
```

When a prompt needs improvement: edit the text file, test, commit. Fast iteration loop. No compilation step.

**Future (post-launch):** When real user interaction data exists (from `agent_runs` and `slack_messages` tables), migrate to DSPy for systematic prompt optimization.

## Configuration

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    ANTHROPIC_API_KEY: str
    CLERK_SECRET_KEY: str
    QBO_CLIENT_ID: str
    QBO_CLIENT_SECRET: str
    QBO_ENVIRONMENT: str = "sandbox"
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    SLACK_BOT_TOKEN: str
    SLACK_SIGNING_SECRET: str
    SLACK_APP_TOKEN: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
```

No hardcoded values. Everything from environment.
