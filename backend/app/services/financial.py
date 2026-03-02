from datetime import datetime, timezone
from decimal import Decimal

from supabase import Client

from backend.app.integrations.quickbooks import QuickBooksClient
from backend.app.models.schemas import (
    AnomalyResult,
    BudgetInput,
    BudgetResult,
    FinancialStatement,
    QBTokenRecord,
    RatioInput,
    RatioResult,
    RunwayInput,
    RunwayResult,
)
from backend.app.services.cache import QBCache
from backend.app.tools.anomaly import detect_anomalies, AnomalyInput
from backend.app.tools.budget import analyze_budget
from backend.app.tools.ratios import calculate_ratios
from backend.app.tools.runway import calculate_runway


class FinancialService:
    """
    Business logic layer — orchestrates cache, QuickBooks, and deterministic tools.
    All QuickBooks data goes through the cache before reaching tools.
    """

    def __init__(self, supabase: Client) -> None:
        self._cache = QBCache(supabase)
        self._db = supabase

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def get_qb_token(self, user_id: str) -> QBTokenRecord | None:
        """Load QuickBooks token from Supabase for the given user."""
        result = (
            self._db.table("qb_tokens")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not result.data:
            return None
        row = result.data
        return QBTokenRecord(**row)

    async def save_qb_token(self, token: QBTokenRecord) -> None:
        """Upsert QuickBooks token into Supabase."""
        self._db.table("qb_tokens").upsert({
            "user_id": token.user_id,
            "realm_id": token.realm_id,
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at.isoformat(),
        }).execute()

    async def delete_qb_token(self, user_id: str) -> None:
        """Remove QuickBooks tokens (disconnect)."""
        self._db.table("qb_tokens").delete().eq("user_id", user_id).execute()

    # ------------------------------------------------------------------
    # Data fetching with cache
    # ------------------------------------------------------------------

    async def get_statements(
        self, user_id: str, months: int = 12, ttl_minutes: int | None = None
    ) -> list[FinancialStatement] | None:
        """
        Return financial statements from cache if fresh, else pull from QuickBooks.
        Returns None if QuickBooks is not connected.
        """
        cache_key = f"statements_{months}m"
        cached = await self._cache.get(user_id, cache_key, ttl_minutes)
        if cached:
            return [FinancialStatement(**s) for s in cached]

        token = await self.get_qb_token(user_id)
        if not token:
            return None

        client = QuickBooksClient(token)
        statements = await client.get_all_statements(months=months)

        # Persist refreshed token if it changed
        if client.token.access_token != token.access_token:
            await self.save_qb_token(client.token)

        # Cache the results
        await self._cache.set(
            user_id,
            cache_key,
            [s.model_dump(mode="json") for s in statements],
        )
        return statements

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def compute_ratios(
        self, user_id: str, headcount: int | None = None
    ) -> RatioResult | None:
        statements = await self.get_statements(user_id)
        if statements is None:
            return None
        return calculate_ratios(RatioInput(statements=statements, headcount=headcount))

    async def compute_runway(
        self, user_id: str, current_cash: Decimal
    ) -> RunwayResult | None:
        statements = await self.get_statements(user_id)
        if statements is None:
            return None
        cf = next((s for s in statements if s.statement_type == "cash_flow"), None)
        if not cf:
            return None
        return calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=current_cash))

    async def compute_budget(
        self,
        user_id: str,
        budget_targets: dict[str, Decimal] | None = None,
    ) -> BudgetResult | None:
        statements = await self.get_statements(user_id)
        if statements is None:
            return None
        return analyze_budget(BudgetInput(statements=statements, budget_targets=budget_targets))

    async def compute_anomalies(self, user_id: str) -> AnomalyResult | None:
        statements = await self.get_statements(user_id)
        if statements is None:
            return None
        return detect_anomalies(AnomalyInput(statements=statements))

    # ------------------------------------------------------------------
    # Slack user mapping
    # ------------------------------------------------------------------

    async def get_clerk_user_from_slack(self, slack_user_id: str) -> str | None:
        """Look up Clerk user ID from Slack user ID."""
        result = (
            self._db.table("slack_user_map")
            .select("clerk_user_id")
            .eq("slack_user_id", slack_user_id)
            .maybe_single()
            .execute()
        )
        return result.data["clerk_user_id"] if result.data else None
