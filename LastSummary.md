Edited walkthrough.md

Here's the complete gap analysis. **24 missing items** found across 5 areas:

---

## 🔴 Blocking (4 items — ship-blockers)

| # | Issue |
|---|-------|
| 1 | **Financial context never injected into agent** — `AgentState.financial_summary` is always `None` because `process_slack_message` only passes `{"messages": [...]}` to LangGraph, never loading QBO data from the DB first |
| 2 | **Subscription status never enforced** — a `cancelled` tenant can still call every endpoint and get Slack responses indefinitely |
| 3 | **Trial expiry never enforced** — `trial_ends_at` field exists but nothing reads it; payment-skipping users get free service forever |
| 4 | **Dashboard is a static UI** — no API calls wire real burn rate / runway / cash data to the dashboard page |

---

## 🟡 Important (17 items)

**Backend Logic:**
- Stripe `payment_failed` → no Slack warning to founder (open sprint item)
- Proactive alerts repeat daily with no "already alerted" deduplication
- Sync appends new snapshots forever with no deduplication/cleanup
- `financial_summary` tool not registered in the agent's tool list
- `SlackUserMap` is written but never read back
- `/sync` slash command referenced in warning messages but doesn't exist

**Frontend:**
- No `onboarding/bank/` page (Plaid step missing even as a skip placeholder)
- No subscription gating UI for `past_due`/`cancelled` state
- Next.js middleware proxy deprecation (open sprint item)

**Testing:**
- Zero tests for `services/sync.py`
- Zero tests for `services/monthly_report.py`
- No Stripe webhook integration tests
- `cross_validate.py` and `select_model.py` have no dedicated tests

**Infrastructure:**
- No database migration system (no Alembic)
- No error monitoring / Sentry
- No rate limiting on any endpoint (open sprint item)
- JWT state tokens use `CLERK_SECRET_KEY[:32]` — weak entropy (prefix bytes)

---

## 🟢 Polish (3 items)
- `ruff_report.txt` committed to git
- `docs/sprints/` directory never created (weekly sprint reports missing)
- `README.md` lacks local dev setup instructions

---

**The single highest-impact fix:** injecting financial context into the agent (#1) — it's one file change and the entire AI value proposition depends on it.