"""
Seed script: create admin user + backfill tenant_id on all existing data rows.
Run once after migration 001, before migration 002 step 2/3.

Usage:
    cd backend
    python -m scripts.seed_admin_tenant --email admin@example.com --password <secret>
"""
import asyncio
import argparse
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine
from sqlalchemy import text


DATA_TABLES = [
    "listings", "listing_report", "keyword_report",
    "manual_listing_report", "manual_keyword_report",
    "import_batch", "threshold_configs", "scenarios_rules",
    "listings_int_ext", "listings_int_hist", "keywords", "refresh_state",
]


async def run(email: str, password: str):
    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_ctx.hash(password)
    admin_id = str(uuid.uuid4())

    async with engine.begin() as conn:
        # Check if admin already exists
        row = await conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
        existing = row.fetchone()
        if existing:
            admin_id = existing[0]
            print(f"Admin user already exists: {admin_id}")
        else:
            await conn.execute(text("""
                INSERT INTO users (id, email, password_hash, full_name, is_active, is_admin)
                VALUES (:id, :email, :hash, 'Admin', true, true)
            """), {"id": admin_id, "email": email, "hash": hashed})
            await conn.execute(text("""
                INSERT INTO credit_accounts (id, user_id, balance) VALUES (:id, :uid, 0)
            """), {"id": str(uuid.uuid4()), "uid": admin_id})
            print(f"Created admin user: {admin_id}")

        # Backfill tenant_id on all data tables
        for table in DATA_TABLES:
            try:
                result = await conn.execute(text(
                    f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"
                ), {"tid": admin_id})
                print(f"  Backfilled {table}: {result.rowcount} rows")
            except Exception as e:
                print(f"  Skipped {table}: {e}")

    print(f"\nDone. Seed tenant_id = {admin_id}")
    print("Now run Step 3 of migration 002 to set NOT NULL constraints.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.email, args.password))
