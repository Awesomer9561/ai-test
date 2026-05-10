"""
One-time setup script: creates the PostgreSQL database and all tables.

Run this ONCE after installing PostgreSQL:
    python setup_db.py

Prerequisites:
    pip install asyncpg psycopg2-binary
"""

import asyncio
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


DB_NAME = "ibps_adaptive"
DB_USER = "postgres"
DB_PASS = "9561"
DB_HOST = "localhost"
DB_PORT = 5432


def create_database():
    """Create the ibps_adaptive database if it doesn't exist."""
    print(f"Connecting to PostgreSQL as {DB_USER}@{DB_HOST}:{DB_PORT}...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Check if DB exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"✓ Database '{DB_NAME}' created.")
    else:
        print(f"✓ Database '{DB_NAME}' already exists.")

    cursor.close()
    conn.close()


async def create_tables():
    """Create all SQLAlchemy tables in the new database."""
    # Import after DB exists so the engine can connect
    from app.db import engine, Base
    from app.models import User, Subject, Topic, Question, Test, TestQuestion, Attempt, UserSkill  # noqa: F401

    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ All tables created.")
    await engine.dispose()


async def seed_data():
    """Load seed subjects and questions into the new DB."""
    from app.db import async_session
    from app.seed.loader import seed_database

    async with async_session() as db:
        await seed_database(db)
    print("✓ Seed data loaded.")


async def main():
    create_database()
    await create_tables()
    await seed_data()
    print("\n✅ PostgreSQL setup complete! You can now run the backend:")
    print("   cd backend && python -m uvicorn app.main:app --reload --port 8001")


if __name__ == "__main__":
    asyncio.run(main())
