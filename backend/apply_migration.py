#!/usr/bin/env python3
"""
Apply SQL migrations to the database.
Usage: python apply_migration.py [migration_name]
If no name provided, applies all pending migrations.
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from app.core.database import _get_engine

async def apply_migration(filename: str):
    """Apply a single migration file."""
    migration_path = Path(__file__).parent / "migrations" / filename

    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        return False

    engine, _ = _get_engine()

    try:
        # Read migration SQL and split into individual statements.
        # asyncpg's prepared-statement interface rejects multi-statement strings.
        # CRITICAL: strip `-- ...` comment lines BEFORE splitting on `;`, because
        # comments may contain `;` (e.g. "-- foo; bar") which would otherwise
        # break the split. engine.begin() handles the transaction so we also
        # skip explicit BEGIN/COMMIT/ROLLBACK keywords.
        raw = migration_path.read_text()
        no_comments = "\n".join(
            line for line in raw.splitlines() if not line.strip().startswith("--")
        )
        statements = []
        for stmt in no_comments.split(";"):
            cleaned = stmt.strip()
            if not cleaned:
                continue
            if cleaned.upper() in ("BEGIN", "COMMIT", "ROLLBACK"):
                continue
            statements.append(cleaned)

        async with engine.begin() as conn:
            for stmt in statements:
                await conn.execute(text(stmt))

        print(f"✅ Applied migration: {filename} ({len(statements)} statements)")
        return True
    except Exception as e:
        print(f"❌ Failed to apply migration {filename}: {e}")
        return False
    finally:
        await engine.dispose()

async def main():
    migration_files = [
        "008_add_onboarding_fields.sql",
    ]

    if len(sys.argv) > 1:
        migration_files = sys.argv[1:]

    failed = []
    for migration_file in migration_files:
        success = await apply_migration(migration_file)
        if not success:
            failed.append(migration_file)

    if failed:
        print(f"\n❌ {len(failed)} migration(s) failed")
        sys.exit(1)
    else:
        print(f"\n✅ All migrations applied successfully")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
