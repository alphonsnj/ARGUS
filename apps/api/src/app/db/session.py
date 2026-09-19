from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=20
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db_session(request: Request) -> Generator[Session, None, None]:
    session = SessionLocal()
    session.info["request_id"] = getattr(request.state, "request_id", None)
    try:
        yield session
    finally:
        session.close()
