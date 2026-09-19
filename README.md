# Flowytics — Agentic CFO [Demo Loom Video](https://www.loom.com/share/16d5c70a57634b668928355aebae212d)

Flowytics is an AI-powered managerial accounting application designed specifically for founders. Instead of paying thousands of dollars a month for a fractional CFO to analyze Quickbooks and tell you your runway, Flowytics connects directly to your financial tooling and proactively alerts you via Slack using an autonomous LangGraph agent.

## Current Project Status
- **Sprint 1 (Infrastructure & Integrations): COMPLETE ✅**
  - **Database:** PostgreSQL via Supabase, modeled with SQLModel.
  - **Frontend:** Next.js unified Dashboard with Clerk Authentication.
  - **Integrations:**
    - **Stripe:** Checkout Sessions & Webhooks fully mapped.
    - **QuickBooks Online:** OAuth flow complete. Financial sync engine (`services/sync.py`) can pull P&L, Balance Sheet, and Cash Flow into JSON snapshots.
    - **Slack:** OAuth and Events API listener mapped for proactive agent responses.

- **Sprint 2 (Deterministic Tools): UP NEXT ⏳**
  - The core mathematical functions (`burn_rate`, `runway`, `cash_forecast`). 
  - (These must be built before the AI Agent so the LLM has tools to call).

- **Sprint 3 (LangGraph AI Agent): PLANNED 📅**
  - The ReAct loop routing user questions to the Python math tools. 

## Technology Architecture

### Backend (`/backend`)
- **Framework:** FastAPI (Python 3.12+)
- **ORM:** SQLModel & Async SQLAlchemy
- **Data Engine:** Polars (for lightning-fast metric calculations)
- **Agent Framework:** LangGraph & LangChain (Anthropic Claude 3.5 Sonnet / Haiku / Opus)
- **Database:** Supabase (Postgres)

### Frontend (`/frontend`)
- **Framework:** Next.js (App Router)
- **Styling:** Tailwind CSS & shadcn/ui
- **Authentication:** Clerk

## Local Development Setup

### 1. Backend Setup
Change into the root directory and use `uv` to run the backend:
```bash
uv run uvicorn backend.app.main:app --reload
```
The backend runs on `http://127.0.0.1:8000`.

### 2. Frontend Setup
Change into the `frontend` directory and run the Next.js development server:
```bash
cd frontend
npm run dev
```
The frontend runs on `http://localhost:3000`.

### 3. Environment Variables
You will need `.env` files located in the root (for FastAPI backend) and in `frontend/` (for Next.js).
**`frontend/.env.local` Required Keys:**
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`

**`backend/.env` Required Keys:**
- `DATABASE_URL` (Supabase connection string)
- `ANTHROPIC_API_KEY`
- `CLERK_SECRET_KEY` (Used for webhook validation and cryptographic signing)
- `STRIPE_SECRET_KEY` & `STRIPE_WEBHOOK_SECRET`
- `QB_CLIENT_ID`, `QB_CLIENT_SECRET`, `QB_REDIRECT_URI`
- `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN`

## Multi-Tenant Onboarding Flow
1. **Signup/Login**: Users authenticate through Clerk (mapped to `tenants` DB table via Clerk webhook or me.py).
2. **Dashboard Integrations**: Users can link Slack, QuickBooks, and Stripe trial directly from the dashboard.
3. **Data Sync**: QuickBooks synchronizes the latest financial data as JSONB snapshots.
4. **Chat**: Users message the Slackbot, which spins up a LangGraph worker to calculate insights dynamically via Polars dataframes.
