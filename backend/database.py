"""
Database connection and session management for SQLAlchemy ORM.
Uses Supabase PostgreSQL with pgvector support.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()

# Supabase connection string from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

# Build PostgreSQL connection URLs as structured objects so special characters in
# credentials are handled correctly and driver substitution is explicit, not fragile.
_sync_url = URL.create(
    drivername="postgresql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

# Expose a rendered string for logging / external consumers that need a plain URL.
DATABASE_URL = _sync_url.render_as_string(hide_password=False)

# Create SQLAlchemy engine — used only at startup (init_db, test_connection); NullPool avoids
# holding persistent connections for a path that never runs under load.
engine = create_engine(
    _sync_url,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using them
    poolclass=NullPool,  # no persistent pool — connect-on-demand, close immediately
)

# Session factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Base class for all models
Base = declarative_base()


def get_db():
    """
    Dependency function to get a database session.
    Yields a session and ensures it closes after request.
    Usage in FastAPI: def route(db: Session = Depends(get_db)):
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Alias for compatibility if needed, but get_db is standard
get_session = get_db


def init_db():
    """
    Create all tables defined in models.
    Call this once during application startup.
    """
    Base.metadata.create_all(bind=engine)


def test_connection():
    """
    Test the database connection.
    Returns: (success: bool, message: str)
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(__import__('sqlalchemy').text("SELECT 1"))
            return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"


# ---------------------------------------------------------------------------
# Async engine — FastAPI endpoints (Option B: asyncpg driver)
# ---------------------------------------------------------------------------
# Derive async URL by replacing only the drivername — credentials and params are preserved.
_async_url = _sync_url.set(drivername="postgresql+asyncpg")

async_engine = create_async_engine(
    _async_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,    # max 20 connections total (10 base + 10 overflow) — well within Supabase limits
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_db():
    """Async session dependency for FastAPI endpoints. Uses asyncpg driver."""
    async with AsyncSessionLocal() as session:
        yield session
