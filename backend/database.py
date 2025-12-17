"""
Database connection and session management for SQLAlchemy ORM.
Uses Supabase PostgreSQL with pgvector support.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Supabase connection string from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

# Build PostgreSQL connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=10,
    max_overflow=20,
)

# Session factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Base class for all models
Base = declarative_base()


def get_session():
    """
    Dependency function to get a database session.
    Usage in Flask: session = get_session()
    """
    return SessionLocal()


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
