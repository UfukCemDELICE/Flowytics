from datetime import datetime, timezone

def utc_now() -> datetime:
    """Return a timezone-naive UTC datetime object (compatible with PostgreSQL TIMESTAMP WITHOUT TIME ZONE)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
