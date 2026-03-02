from datetime import datetime, timedelta, timezone

from supabase import Client


class QBCache:
    """QuickBooks data cache backed by Supabase qb_cache table."""

    DEFAULT_TTL_MINUTES = 60  # 1 hour for financial statements
    REALTIME_TTL_MINUTES = 15  # 15 min for frequently changing data

    def __init__(self, supabase: Client):
        self.db = supabase

    async def get(self, user_id: str, report_type: str, ttl_minutes: int | None = None) -> dict | None:
        """Return cached data if fresh, None if stale or missing."""
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
        """Upsert cached data."""
        self.db.table("qb_cache").upsert({
            "user_id": user_id,
            "report_type": report_type,
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
