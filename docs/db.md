# Database

## Overview


Supabase managed PostgreSQL. Connected directly via asyncpg (not REST API). SQLModel as ORM. Row-Level Security enabled on every table.

## Connection

Direct Postgres connection through Supabase's PgBouncer pooler:

```
postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

Use the **pooler URL (port 6543)**, not the direct connection (port 5432). PgBouncer handles connection pooling — critical for serverless/Railway deployments where connections are limited.

## Schema

### tenants

One row per startup customer. Clerk Organization = Tenant.

```sql
CREATE TABLE tenants (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    clerk_org_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    stage TEXT DEFAULT 'pre_seed'
        CHECK (stage IN ('pre_seed', 'seed', 'series_a', 'series_b')),
    currency TEXT DEFAULT 'USD',
    slack_team_id TEXT,
    slack_channel_id TEXT,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    subscription_status TEXT DEFAULT 'trial'
        CHECK (subscription_status IN ('trial', 'active', 'past_due', 'cancelled', 'churned')),
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    trial_started_at TIMESTAMPTZ,
    trial_ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenants_clerk_org ON tenants(clerk_org_id);
CREATE INDEX idx_tenants_status ON tenants(subscription_status);
```

**Why `clerk_org_id` not `clerk_user_id`:** A startup may have multiple founders. Clerk Organization groups them. All queries scope by tenant (org), not individual user.

### integrations

Codat and Plaid connections per tenant.

```sql
CREATE TABLE integrations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('codat', 'plaid')),
    provider_connection_id TEXT NOT NULL,
    credentials_encrypted TEXT,
    platform_name TEXT,
    sync_status TEXT DEFAULT 'pending'
        CHECK (sync_status IN ('pending', 'active', 'error', 'disconnected')),
    last_synced_at TIMESTAMPTZ,
    sync_cursor TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_integrations_tenant ON integrations(tenant_id);
CREATE INDEX idx_integrations_provider ON integrations(tenant_id, provider);
```

**Column decisions:**
- `provider_connection_id`: Codat's `company_id` or Plaid's `item_id`. Generic name for both.
- `credentials_encrypted`: Access/refresh tokens encrypted at rest. Decrypted only when calling the API.
- `sync_cursor`: Plaid uses cursors for incremental sync. Codat uses push keys. Same column, different semantics.
- `error_message`: When `sync_status = 'error'`, this explains why. Shown to user if they ask.

### financial_snapshots

Raw data from integrations. Source of truth for all analysis.

```sql
CREATE TABLE financial_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE NOT NULL,
    snapshot_date DATE NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('codat', 'plaid')),
    data_type TEXT NOT NULL CHECK (data_type IN (
        'profit_loss', 'balance_sheet', 'cash_flow',
        'transactions', 'accounts', 'invoices', 'bills'
    )),
    raw_data JSONB NOT NULL,
    period_start DATE,
    period_end DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_snapshots_tenant_type ON financial_snapshots(tenant_id, data_type);
CREATE INDEX idx_snapshots_tenant_date ON financial_snapshots(tenant_id, snapshot_date DESC);
CREATE INDEX idx_snapshots_source ON financial_snapshots(source);
```

**Data principle: Store raw, transform on read.**
- `raw_data` contains the full API response as-is from Codat/Plaid.
- Never transform during ingest. Transformation happens in tools when reading.
- Why: when you discover a field you initially ignored (e.g., vendor names for AP aging), the data is already there. No re-sync needed.
- Trade-off: JSONB queries are slower than normalized columns. At startup scale (thousands of rows, not millions), this is irrelevant. Normalize post-product-market-fit if query performance matters.

### computed_metrics

Cached output of deterministic tools. Avoids re-running expensive calculations.

```sql
CREATE TABLE computed_metrics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE NOT NULL,
    metric_type TEXT NOT NULL CHECK (metric_type IN (
        'burn_rate', 'runway', 'cash_forecast', 'anomaly',
        'scenario', 'fundraising', 'monthly_report'
    )),
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    period TEXT,
    value JSONB NOT NULL,
    agent_run_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_tenant_type ON computed_metrics(tenant_id, metric_type);
CREATE INDEX idx_metrics_computed ON computed_metrics(computed_at DESC);
```

**Invalidation:** Metrics are recomputed when new financial_snapshots arrive (via daily sync). Old metrics remain for historical comparison. No deletion.

### agent_runs

Every agent execution logged. Observability now, training data later.

```sql
CREATE TABLE agent_runs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE NOT NULL,
    trigger_type TEXT NOT NULL
        CHECK (trigger_type IN ('scheduled', 'slack_message', 'webhook', 'manual')),
    trigger_payload JSONB,
    status TEXT DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    tools_called JSONB DEFAULT '[]',
    model_used TEXT,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    duration_ms INTEGER,
    output_result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_runs_tenant ON agent_runs(tenant_id, created_at DESC);
CREATE INDEX idx_runs_status ON agent_runs(status);
```

**Why log everything:** This table is the future DSPy training dataset. Each row is: input (trigger_payload) → tools called → model used → output. When you have 1000+ rows, you can optimize prompts systematically. Also: cost tracking per tenant for pricing decisions.

### slack_messages

Conversation log. Debugging + feedback signal.

```sql
CREATE TABLE slack_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    slack_user_id TEXT,
    slack_ts TEXT,
    thread_ts TEXT,
    content TEXT,
    agent_run_id UUID REFERENCES agent_runs(id),
    feedback TEXT CHECK (feedback IN ('positive', 'negative', 'correction', NULL)),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_slack_tenant ON slack_messages(tenant_id, created_at DESC);
CREATE INDEX idx_slack_agent_run ON slack_messages(agent_run_id);
```

**`feedback` column:** Not auto-filled in MVP. Manually tagged during first 5 customers based on founder responses. "Thanks" = positive. "No, I meant..." = correction. 10-20 labeled examples = enough to bootstrap DSPy later.

### slack_user_map

Maps Slack users to Clerk users within a tenant.

```sql
CREATE TABLE slack_user_map (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE NOT NULL,
    clerk_user_id TEXT NOT NULL,
    slack_user_id TEXT UNIQUE NOT NULL,
    slack_team_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_slack_map_user ON slack_user_map(slack_user_id);
CREATE INDEX idx_slack_map_tenant ON slack_user_map(tenant_id);
```

## Row-Level Security

RLS enabled on every table. The backend connects with the Postgres password (bypasses RLS), so these policies are a **safety net** — if someone accidentally uses the anon key, data leaks are prevented.

Application layer MUST also filter by `tenant_id` on every query. Belt and suspenders.

```sql
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE computed_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_user_map ENABLE ROW LEVEL SECURITY;

-- Policies for anon/authenticated roles (safety net)
CREATE POLICY "tenant_isolation" ON integrations
    FOR ALL USING (tenant_id IN (
        SELECT id FROM tenants WHERE clerk_org_id = current_setting('app.clerk_org_id', true)
    ));
-- Repeat pattern for all tables
```

## Migrations

**MVP:** Create tables directly via Supabase SQL Editor. Fast, visual, no tooling overhead.

**Post-MVP:** Add Alembic when schema changes become frequent. SQLModel models will auto-generate migrations.

```bash
# Future setup
uv add alembic
alembic init alembic
alembic revision --autogenerate -m "add column"
alembic upgrade head
```

**Rule:** Never modify production tables without:
1. Testing the change on a local/sandbox Supabase instance
2. Backing up the table (Supabase dashboard → SQL → `CREATE TABLE backup_x AS SELECT * FROM x`)
3. Reviewing the SQL before executing

## Entity Relationships

```
tenants
  ├── integrations (1:N — one Codat + optionally one Plaid per tenant)
  ├── financial_snapshots (1:N — daily snapshots accumulate)
  ├── computed_metrics (1:N — metrics per period)
  ├── agent_runs (1:N — every agent execution)
  ├── slack_messages (1:N — conversation history)
  └── slack_user_map (1:N — multiple users per tenant)

agent_runs
  ├── computed_metrics (1:N — one run may produce multiple metrics)
  └── slack_messages (1:N — one run may produce multiple messages)
```

## Data Volume Estimates (First Year, 10 Tenants)

| Table | Rows/tenant/month | After 12 months (10 tenants) |
|-------|-------------------|------------------------------|
| financial_snapshots | ~30 (daily syncs × data types) | ~3,600 |
| computed_metrics | ~10 (daily + monthly) | ~1,200 |
| agent_runs | ~50 (scheduled + Slack) | ~6,000 |
| slack_messages | ~100 | ~12,000 |

Total: ~23,000 rows. Supabase Free tier handles millions. Performance is not a concern at MVP scale. Polars handles data processing regardless.
