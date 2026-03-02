# Flowytics Architecture

## Supabase SQL Setup

Run this in the Supabase SQL Editor:

```sql
-- QuickBooks data cache
CREATE TABLE qb_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    report_type TEXT NOT NULL,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, report_type)
);

-- RLS
ALTER TABLE qb_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can access own cache"
    ON qb_cache FOR ALL
    USING (auth.uid() = user_id);

-- Index for fast lookups
CREATE INDEX idx_qb_cache_user_report ON qb_cache(user_id, report_type);
CREATE INDEX idx_qb_cache_updated ON qb_cache(updated_at);
```



# Flowytics Architecture

## System Overview

Flowytics is an Agentic CFO that connects to a startup's QuickBooks, performs deterministic financial analysis via tools, interprets results via Claude, and delivers insights through a web dashboard and Slack bot.

## Data Flow (End to End)

```
User Request (API or Slack)
    ↓
Auth Layer (Clerk JWT verification)
    ↓
Cache Check (Supabase qb_cache)
    ↓ (miss)                    ↓ (hit)
QuickBooks API Pull          Use cached data
    ↓                           ↓
    → Cache Write →             ↓
                    ↓           ↓
              Orchestrator (LangGraph)
              ↓              ↓
    Deterministic Tools    Claude (DSPy)
    - ratios.py            - Opus: deep analysis
    - runway.py            - Sonnet: reports
    - budget.py            - Haiku: Slack chat
    - anomaly.py
              ↓              ↓
           Cross-Validator
           (tools always win on numbers)
              ↓
         Merged Output
         ↓           ↓
    API Response   Slack Message
```

## Multi-Model Routing

The Orchestrator decides which Claude model to use. Rules:

### Claude Opus (claude-opus-4-20250514)
**When:** Complex multi-step financial reasoning
- Cross-statement analysis (P&L trends affecting Balance Sheet health)
- Strategic recommendations ("should this startup raise now or cut burn?")
- Multi-variable scenario analysis
- Anomaly root cause analysis when multiple signals overlap

**Cost:** ~$15/1M input, ~$75/1M output. Use sparingly.

### Claude Sonnet (claude-sonnet-4-5-20250514)
**When:** Document generation and structured analysis
- Monthly financial report generation
- Cash flow forecast narratives
- Expense analysis summaries
- Any task that produces a document or structured report

**Cost:** ~$3/1M input, ~$15/1M output. Primary workhorse.

### Claude Haiku (claude-haiku-4-5-20250301)
**When:** Quick conversational responses
- Slack bot conversations
- Simple Q&A ("what's my runway?", "how much did we spend on SaaS?")
- Status checks and confirmations
- Any response that should be < 3 seconds

**Cost:** ~$0.80/1M input, ~$4/1M output. Use freely.

### Routing Logic in Orchestrator

```python
def select_model(task_type: str, complexity: str) -> str:
    """Route to appropriate model based on task and complexity."""
    MODEL_MAP = {
        "slack_chat": "claude-haiku-4-5-20250301",
        "slack_deep": "claude-sonnet-4-5-20250514",  # when user asks for detailed analysis in Slack
        "report_generation": "claude-sonnet-4-5-20250514",
        "forecast_narrative": "claude-sonnet-4-5-20250514",
        "expense_summary": "claude-sonnet-4-5-20250514",
        "cross_statement_analysis": "claude-opus-4-20250514",
        "strategic_recommendation": "claude-opus-4-20250514",
        "multi_signal_analysis": "claude-opus-4-20250514",
    }
    return MODEL_MAP.get(task_type, "claude-sonnet-4-5-20250514")
```

## LangGraph Agent Architecture

### Graph Structure

```
START
  ↓
[fetch_financial_data] — Pull from cache or QuickBooks
  ↓
[run_deterministic_tools] — Execute all relevant tools
  ↓
[route_to_model] — Conditional edge: select Opus/Sonnet/Haiku
  ↓                    ↓                   ↓
[opus_analysis]  [sonnet_generate]   [haiku_respond]
  ↓                    ↓                   ↓
[cross_validate] — Compare LLM numbers against tool outputs
  ↓
[format_output] — Structure for API or Slack
  ↓
END
```

### State Schema

```python
from typing import TypedDict, Literal

class AgentState(TypedDict):
    # Input
    user_id: str
    request_type: Literal["report", "cashflow", "expense", "slack"]
    request_params: dict
    
    # QuickBooks data
    financial_data: dict | None
    cache_hit: bool
    
    # Tool outputs
    tool_results: dict  # ratios, runway, budget, anomalies
    
    # LLM outputs
    model_used: str
    llm_analysis: str
    llm_numbers: dict  # any numbers LLM produced (for cross-validation)
    
    # Validation
    discrepancies: list[dict]  # tool vs LLM mismatches
    
    # Final
    output: dict
```

### Tool Nodes

Each tool node wraps a pure function from `backend/app/tools/`:

```python
def run_deterministic_tools(state: AgentState) -> AgentState:
    """Run all relevant tools based on request type."""
    data = state["financial_data"]
    results = {}
    
    if state["request_type"] in ("report", "slack"):
        results["ratios"] = calculate_ratios(data)
    
    if state["request_type"] in ("cashflow", "report", "slack"):
        results["runway"] = calculate_runway(data)
    
    if state["request_type"] in ("expense", "report", "slack"):
        results["budget"] = analyze_budget(data)
        results["anomalies"] = detect_anomalies(data)
    
    state["tool_results"] = results
    return state
```

## Deterministic Tools Specification

### tools/ratios.py

Calculates financial ratios from QuickBooks data. All inputs and outputs are Pydantic models.

**Input:** P&L + Balance Sheet data (monthly, 1-12 months)

**Calculations:**
- Gross Margin = (Revenue - COGS) / Revenue
- Net Margin = Net Income / Revenue
- Operating Margin = Operating Income / Revenue
- Current Ratio = Current Assets / Current Liabilities
- Quick Ratio = (Current Assets - Inventory) / Current Liabilities
- Debt-to-Equity = Total Liabilities / Total Equity
- MoM Revenue Growth = (This Month Revenue - Last Month Revenue) / Last Month Revenue
- YoY Revenue Growth = (This Month Revenue - Same Month Last Year Revenue) / Same Month Last Year Revenue
- Revenue per Employee (if headcount available)
- SaaS metrics if applicable: ARR, MRR, Net Revenue Retention

**Output:** Dict of all calculated ratios with values and period labels.

### tools/runway.py

Calculates burn rate and runway from Cash Flow Statement data.

**Input:** Cash Flow data (monthly, 3-12 months) + current cash position

**Calculations:**
- Monthly Burn Rate = average of last 3 months net cash outflow
- Runway (months) = Current Cash / Monthly Burn Rate
- Burn Trend = linear regression slope over available months (increasing/stable/decreasing)
- Cash Zero Date = today + runway months
- Weighted Burn Rate = more recent months weighted higher (exponential decay)

**Threshold Alerts:**
- Runway < 3 months → CRITICAL
- Runway < 6 months → WARNING
- Runway < 12 months → INFO
- Burn rate increasing > 20% MoM → WARNING

**Output:** Runway months, burn rate, trend, alert level, projected cash zero date.

### tools/budget.py

Compares actual expenses against budget targets.

**Input:** Expense data by category (monthly) + budget targets (if set, otherwise skip)

**Calculations:**
- Variance per category = (Actual - Budget) / Budget as percentage
- Total expense MoM growth
- Category MoM growth
- Expense-to-Revenue ratio per category
- Top 5 expense categories by absolute spend

**Threshold Alerts:**
- Category > 20% over budget → WARNING
- Category > 50% over budget → CRITICAL
- Total expenses growing faster than revenue for 2+ months → WARNING

**Output:** Per-category variance, alerts, growth rates, rankings.

### tools/anomaly.py

Statistical anomaly detection on expense and revenue data.

**Input:** Monthly financial data (6+ months preferred, 3 minimum)

**Method:** Z-score analysis per category per month.

**Calculations:**
- For each category: mean and std over historical period
- Z-score = (current_value - mean) / std
- Flag if |Z-score| > 2.0
- Also flag: new categories that didn't exist before, categories that disappeared, sudden vendor concentration

**Output:** List of anomalies with category, value, Z-score, severity.

### tools/validators.py

Cross-validates LLM outputs against tool outputs.

**Logic:**
- Extract any numbers from LLM response
- Compare against tool-calculated numbers
- If discrepancy > 1%: log warning, use tool number in final output
- If discrepancy > 10%: log error, flag for review
- Always attach provenance: "calculated by tool" vs "estimated by LLM"

## QuickBooks Integration

### OAuth 2.0 Flow

```
1. User clicks "Connect QuickBooks" in frontend
2. Frontend redirects to: /api/v1/quickbooks/auth
3. Backend redirects to QuickBooks OAuth URL
4. User authorizes in QuickBooks
5. QuickBooks redirects to: /api/v1/quickbooks/callback
6. Backend exchanges code for access_token + refresh_token
7. Tokens stored in Supabase qb_tokens table (encrypted)
8. Frontend redirected to dashboard with success status
```

### Data Endpoints to Pull

From QuickBooks Online API, we need these reports:

| Report | QB API Endpoint | Use |
|--------|----------------|-----|
| Profit & Loss | `/v3/company/{realmId}/reports/ProfitAndLoss` | Revenue, expenses, net income |
| Balance Sheet | `/v3/company/{realmId}/reports/BalanceSheet` | Assets, liabilities, equity |
| Cash Flow | `/v3/company/{realmId}/reports/CashFlow` | Operating/investing/financing cash flows |
| General Ledger | `/v3/company/{realmId}/reports/GeneralLedger` | Transaction-level detail |
| Vendor Expenses | `/v3/company/{realmId}/reports/VendorExpenses` | Expense by vendor breakdown |

### Parameters
- `start_date` / `end_date`: Usually last 12 months
- `accounting_method`: Accrual (default) or Cash
- `summarize_column_by`: Month

### Token Refresh
- Access tokens expire in 1 hour
- Refresh tokens expire in 100 days
- Auto-refresh on every API call if expired
- If refresh token expired: notify user to reconnect

### Data Normalization

QuickBooks returns nested JSON with varying structures. Normalize to:

```python
class FinancialStatement(BaseModel):
    statement_type: Literal["profit_loss", "balance_sheet", "cash_flow"]
    company_name: str
    currency: str
    period_start: date
    period_end: date
    rows: list[FinancialRow]

class FinancialRow(BaseModel):
    category: str        # e.g., "Revenue", "Cost of Goods Sold"
    subcategory: str     # e.g., "Sales", "Services"
    amount: Decimal      # Always use Decimal, never float
    period: str          # e.g., "2025-01"
```

**CRITICAL: Use `Decimal` for all financial amounts. Never `float`. Floating point errors are unacceptable in financial calculations.**

## Slack Bot Architecture

### Event Flow

```
Slack Message → Slack Events API → POST /api/v1/slack/events
    ↓
Verify Slack signature (signing secret)
    ↓
Look up slack_user_id in slack_user_map → get clerk_user_id
    ↓ (not found)                    ↓ (found)
Reply: "Connect your account       Run Orchestrator with
at https://app.flowytics.com"       request_type="slack"
                                     ↓
                                  Haiku responds (simple queries)
                                  or Sonnet/Opus (complex queries)
                                     ↓
                                  Post reply in Slack thread
```

### Message Parsing

The Slack bot should understand natural language queries:
- "What's my runway?" → cashflow tools → Haiku response
- "Show me this month's expenses" → expense tools → Haiku response
- "Give me a full financial report" → all tools → Sonnet report (upgrade from Haiku)
- "Should I hire another engineer given my burn rate?" → all tools → Opus analysis (strategic question)

### Trigger Words for Model Upgrade
- "analyze", "deep dive", "strategy", "should I", "recommend" → Upgrade to Sonnet or Opus
- "report", "summary", "document" → Sonnet
- Simple questions, status checks → Stay on Haiku

## Supabase Schema

### Tables

**qb_cache** — QuickBooks API response cache
- `user_id` (TEXT, Clerk ID)
- `report_type` (TEXT: "profit_loss", "balance_sheet", "cash_flow", "general_ledger", "vendor_expenses")
- `data` (JSONB, normalized financial data)
- `updated_at` (TIMESTAMPTZ)

**qb_tokens** — QuickBooks OAuth tokens
- `user_id` (TEXT, Clerk ID, UNIQUE)
- `realm_id` (TEXT, QuickBooks company ID)
- `access_token` (TEXT, encrypted)
- `refresh_token` (TEXT, encrypted)
- `expires_at` (TIMESTAMPTZ)

**slack_user_map** — Slack to Clerk user mapping
- `clerk_user_id` (TEXT, UNIQUE)
- `slack_user_id` (TEXT, UNIQUE)
- `slack_team_id` (TEXT)

### No RLS — Service Role Access

Since auth is handled by Clerk (not Supabase Auth), all database queries use the `service_role_key`. Every query MUST filter by `user_id` (Clerk ID) to ensure tenant isolation. This is enforced at the application layer, not the database layer.

**CRITICAL: Every Supabase query must include `.eq("user_id", clerk_user_id)`. Missing this filter = data leak between tenants.**

## Clerk Auth Integration

### Backend (FastAPI)
- Every protected endpoint depends on `get_current_user_id()` from `auth.py`
- This extracts and verifies the Clerk JWT from the Authorization header
- Returns the Clerk user ID string

### Frontend (Next.js)
- `@clerk/nextjs` provides `<SignIn>`, `<SignUp>`, `<UserButton>` components
- `middleware.ts` protects routes — unauthenticated users redirected to sign-in
- `useAuth()` hook provides the session token for API calls
- API calls include `Authorization: Bearer <token>` header

### Clerk → Supabase User ID
- Supabase tables use `clerk_user_id` (TEXT), NOT Supabase `auth.uid()`
- No Supabase Auth is used at all
- Clerk webhook can sync user data to Supabase if needed later

## Stripe Integration

### Billing Model (MVP)
- Free tier: limited reports per month
- Pro tier: unlimited reports + Slack bot
- Usage-based: charge per Opus analysis (expensive)

### Implementation
- Stripe Checkout for subscription creation
- Stripe webhooks for payment events → update user tier in Supabase
- Middleware checks user tier before allowing certain features
- Track Opus usage per user per billing period

## DSPy Module Design

### Why DSPy
DSPy optimizes prompts programmatically instead of manual prompt engineering. Each financial task is a DSPy module with defined inputs/outputs.

### Modules

```python
# Example: Financial Report Module (Sonnet)
class FinancialReportGenerator(dspy.Module):
    def __init__(self):
        self.generate = dspy.ChainOfThought("tool_results, financial_data -> report")
    
    def forward(self, tool_results: dict, financial_data: dict) -> str:
        return self.generate(
            tool_results=json.dumps(tool_results),
            financial_data=json.dumps(financial_data)
        ).report

# Example: Slack Response Module (Haiku)
class SlackResponder(dspy.Module):
    def __init__(self):
        self.respond = dspy.Predict("user_question, tool_results -> answer")
    
    def forward(self, user_question: str, tool_results: dict) -> str:
        return self.respond(
            user_question=user_question,
            tool_results=json.dumps(tool_results)
        ).answer

# Example: Strategic Analysis Module (Opus)
class StrategicAnalyzer(dspy.Module):
    def __init__(self):
        self.analyze = dspy.ChainOfThought(
            "tool_results, financial_data, user_question -> analysis, recommendations, risks"
        )
    
    def forward(self, tool_results: dict, financial_data: dict, user_question: str):
        return self.analyze(
            tool_results=json.dumps(tool_results),
            financial_data=json.dumps(financial_data),
            user_question=user_question
        )
```

### DSPy + LangGraph Integration
- DSPy modules are called inside LangGraph nodes
- LangGraph handles the flow (which node runs when)
- DSPy handles the quality (optimized prompts for each node)
- Model selection happens in LangGraph, DSPy module receives the model as a parameter

## Error Handling

### QuickBooks API Errors
- 401: Token expired → auto-refresh → retry
- 403: User disconnected QB → notify via API + Slack
- 429: Rate limited → exponential backoff → cache more aggressively
- 500: QB service down → return cached data with "stale data" warning

### LLM Errors
- Timeout: Retry once, then return tool-only results with "AI analysis unavailable"
- Rate limit: Queue the request, notify user of delay
- Hallucination detected (via cross-validator): Strip bad numbers, use tool numbers, log for review

### Slack Errors
- User not mapped: Reply with connection link
- QB not connected: Reply with connection instructions
- Analysis timeout: Reply "Working on it..." → post results when ready