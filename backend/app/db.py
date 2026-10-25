from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from .config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def engine():
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        settings.storage_dir.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {"connect_timeout": 10},
    )


def init_db():
    from . import models  # noqa: F401

    with engine().begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)
        if conn.dialect.name == "postgresql":
            conn.execute(
                text(
                    "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS search_vector tsvector "
                    "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_fts ON chunks USING gin(search_vector)"))


@contextmanager
def session_scope():
    with Session(engine(), expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_db():
    with session_scope() as session:
        yield session
