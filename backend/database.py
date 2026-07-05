"""
database.py
-----------
Database configuration for EcoPulse.

Uses SQLite through SQLAlchemy by default (zero external services needed to
run the project). The connection string is fully configurable through the
DATABASE_URL environment variable, so the same code works unmodified against
Postgres, MySQL, or a managed cloud database -- swap the URL and go.

Why SQLite for the reference implementation:
- Ships with Python, needs no separate container/service for grading or demos
- SQLAlchemy abstracts the engine, so moving to MongoDB-style storage or a
  managed Postgres instance on AWS/Azure later is a config change, not a
  rewrite (see README "Swapping the database" section).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/ecopulse.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
