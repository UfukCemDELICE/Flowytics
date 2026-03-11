from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from backend.app.config import get_settings

_engine = None
_async_session = None


def _get_engine():
    """Lazy engine initialisation — created on first use, not at import."""
    global _engine, _async_session
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=5)
        _async_session = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine, _async_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session. Depends on DATABASE_URL being set."""
    _, session_factory = _get_engine()
    async with session_factory() as session:
        yield session
