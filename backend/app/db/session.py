"""Database engines and session factory.

Two engines on purpose. `engine` is the application's read-write connection.
`readonly_engine` connects as a role with SELECT-only grants and exists solely
to execute NL2SQL-generated statements — a required defence layer, not an
optimisation (.claude/rules/security.md).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Never route application queries through this. Never route NL2SQL through
# `engine`.
readonly_engine = create_engine(settings.database_url_readonly, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that always closes."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
