import asyncio
from sqlalchemy import text
from backend.app.database import _get_engine

async def main():
    engine, _ = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        )
        tables = [row[0] for row in result]
        print("TABLES:", tables)

if __name__ == '__main__':
    asyncio.run(main())
