
import asyncio
from sqlalchemy import text
from backend.app.core.database import engine

async def check_tables():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [row[0] for row in result.fetchall()]
        print("Existing tables:")
        for t in sorted(tables):
            print(f"- {t}")

if __name__ == "__main__":
    asyncio.run(check_tables())
