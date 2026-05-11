
import asyncio
import logging
from backend.app.core.database import engine, Base
from backend.app.models import (
    import_batch, 
    listing_report, 
    keyword_report, 
    manual_listing_report, 
    manual_keyword_report
)

logging.basicConfig(level=logging.INFO)

async def force_create_tables():
    print("Starting force table creation...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(force_create_tables())
