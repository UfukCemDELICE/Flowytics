# Flowytics — Project Setup Guide

## Prerequisites

### Required
```bash
# uv (Rust-based Python package manager)
# Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 20+
# Download from: https://nodejs.org/en/download
```

### Accounts Needed
- **Clerk:** https://clerk.com → Create application → Get publishable + secret keys
- **Supabase:** https://supabase.com → Create project → Get URL + service role key
- **Anthropic:** https://console.anthropic.com → Get API key
- **QuickBooks Developer:** https://developer.intuit.com → Create sandbox app → Get client ID/secret
- **Stripe:** https://dashboard.stripe.com → Get secret key + webhook secret
- **Slack:** https://api.slack.com/apps → Create bot app → Get bot token + signing secret
- **LangSmith:** https://smith.langchain.com → Get API key
- **Vercel:** https://vercel.com → Link GitHub repo
- **Railway:** https://railway.app → Link GitHub repo

---

## Step 1 — Initialize Project

```bash
mkdir flowytics && cd flowytics
git init
uv init --python 3.12
```

## Step 2 — Backend Dependencies

```bash
# Core framework
uv add fastapi uvicorn[standard] pydantic-settings

# AI / Agent stack
uv add anthropic langgraph dspy langchain-anthropic langchain-core

# Auth
uv add clerk-backend-api pyjwt cryptography

# Database
uv add supabase

# QuickBooks integration
uv add python-quickbooks

# Stripe payments
uv add stripe

# Slack
uv add slack-bolt slack-sdk

# LangSmith observability
uv add langsmith

# Utilities
uv add httpx python-dotenv

# Dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov ruff mypy
```

## Step 3 — Create Backend Structure

```bash
mkdir -p backend/app/api/v1
mkdir -p backend/app/agents
mkdir -p backend/app/tools
mkdir -p backend/app/integrations
mkdir -p backend/app/models
mkdir -p backend/app/services
mkdir -p backend/app/utils
mkdir -p backend/tests/test_tools
mkdir -p backend/tests/test_agents
mkdir -p backend/tests/test_api
mkdir -p docs

# Create __init__.py files
find backend -type d -exec touch {}/__init__.py \;

# Core files
touch backend/app/main.py
touch backend/app/config.py
touch backend/app/auth.py
touch backend/app/api/v1/reports.py
touch backend/app/api/v1/cashflow.py
touch backend/app/api/v1/expenses.py
touch backend/app/api/v1/quickbooks.py
touch backend/app/api/v1/slack.py
touch backend/app/agents/orchestrator.py
touch backend/app/agents/financial_reporting.py
touch backend/app/agents/cashflow.py
touch backend/app/agents/expense.py
touch backend/app/tools/ratios.py
touch backend/app/tools/runway.py
touch backend/app/tools/budget.py
touch backend/app/tools/anomaly.py
touch backend/app/tools/validators.py
touch backend/app/integrations/quickbooks.py
touch backend/app/integrations/stripe.py
touch backend/app/integrations/slack.py
touch backend/app/models/schemas.py
touch backend/app/services/financial.py
touch backend/app/services/cache.py
touch docs/architecture.md
```

## Step 4 — Environment Variables

Create `.env` in project root (NEVER commit):

```
# Clerk
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=

# Supabase (database only)
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Anthropic
ANTHROPIC_API_KEY=

# QuickBooks
QB_CLIENT_ID=
QB_CLIENT_SECRET=
QB_REDIRECT_URI=http://localhost:8000/api/v1/quickbooks/callback
QB_ENVIRONMENT=sandbox

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# Slack
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=flowytics
```

Create `.gitignore`:

```
.env
.env.local
.env.*.local
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
htmlcov/
node_modules/
.next/
.vercel/
.vscode/
.idea/
.DS_Store
Thumbs.db
*.log
```

## Step 5 — Create Starter Files

### backend/app/config.py
```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Clerk
    clerk_secret_key: str

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # Anthropic
    anthropic_api_key: str

    # QuickBooks
    qb_client_id: str
    qb_client_secret: str
    qb_redirect_uri: str = "http://localhost:8000/api/v1/quickbooks/callback"
    qb_environment: str = "sandbox"

    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str

    # Slack
    slack_bot_token: str
    slack_signing_secret: str

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "flowytics"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### backend/app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Flowytics",
    description="Agentic CFO for startup finance",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

### backend/app/auth.py
```python
from fastapi import Depends, HTTPException, Request
from functools import lru_cache
import httpx

from backend.app.config import get_settings


async def verify_clerk_token(request: Request) -> dict:
    """Verify Clerk JWT from Authorization header. Returns user claims."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.clerk.com/v1/sessions/verify",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            params={"token": token},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")

    return response.json()


async def get_current_user_id(claims: dict = Depends(verify_clerk_token)) -> str:
    """Extract Clerk user ID from verified token claims."""
    return claims["sub"]
```

### backend/app/services/cache.py
```python
from datetime import datetime, timedelta, timezone

from supabase import Client


class QBCache:
    """QuickBooks data cache backed by Supabase qb_cache table."""

    DEFAULT_TTL_MINUTES = 60
    REALTIME_TTL_MINUTES = 15

    def __init__(self, supabase: Client):
        self.db = supabase

    async def get(self, user_id: str, report_type: str, ttl_minutes: int | None = None) -> dict | None:
        ttl = ttl_minutes or self.DEFAULT_TTL_MINUTES
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl)

        result = (
            self.db.table("qb_cache")
            .select("data, updated_at")
            .eq("user_id", user_id)
            .eq("report_type", report_type)
            .gte("updated_at", cutoff.isoformat())
            .maybe_single()
            .execute()
        )

        return result.data["data"] if result.data else None

    async def set(self, user_id: str, report_type: str, data: dict) -> None:
        self.db.table("qb_cache").upsert({
            "user_id": user_id,
            "report_type": report_type,
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
```

## Step 6 — Supabase Setup

Run in Supabase SQL Editor:

```sql
-- QuickBooks data cache
CREATE TABLE qb_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,  -- Clerk user ID (not Supabase auth)
    report_type TEXT NOT NULL,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, report_type)
);

CREATE INDEX idx_qb_cache_user_report ON qb_cache(user_id, report_type);
CREATE INDEX idx_qb_cache_updated ON qb_cache(updated_at);

-- Slack-to-Clerk user mapping
CREATE TABLE slack_user_map (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    clerk_user_id TEXT NOT NULL UNIQUE,
    slack_user_id TEXT NOT NULL UNIQUE,
    slack_team_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_slack_map_slack ON slack_user_map(slack_user_id);

-- QuickBooks OAuth tokens
CREATE TABLE qb_tokens (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,  -- Clerk user ID
    realm_id TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Step 7 — Frontend Setup

```bash
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --use-npm

cd frontend
npm install @clerk/nextjs
npm install @supabase/supabase-js
npm install stripe @stripe/stripe-js
npm install axios
cd ..
```

## Step 8 — Verify Setup

```bash
# Backend
uv run fastapi dev backend/app/main.py
# → http://localhost:8000/health → {"status": "ok", "version": "0.1.0"}

# Frontend (another terminal)
cd frontend && npm run dev
# → http://localhost:3000

# Tests
uv run pytest --co -q

# Verify packages
uv run python -c "import langgraph; print('LangGraph OK')"
uv run python -c "import dspy; print('DSPy OK')"
uv run python -c "import anthropic; print('Anthropic OK')"
uv run python -c "import slack_bolt; print('Slack OK')"
```

## Step 9 — First Commit

```bash
git add .
git commit -m "feat: initial project setup — Agentic CFO stack"
```

---

## Development Order

1. `backend/app/integrations/quickbooks.py` — QuickBooks OAuth + data pull
2. `backend/app/tools/` — All deterministic financial tools + tests
3. `backend/app/agents/orchestrator.py` — LangGraph graph with multi-model routing
4. `backend/app/api/v1/` — REST endpoints for three MVP features
5. `backend/app/integrations/slack.py` + `api/v1/slack.py` — Slack bot
6. `frontend/` — Dashboard with Clerk auth + QB connection + results display
