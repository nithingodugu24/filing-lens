from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session
from fastapi import Request

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
        # Additive migration preserves existing reports and extracted evidence.
        for table, additions in {
            "documents": {"user_id": "VARCHAR(32) REFERENCES users(id)", "dedup_key": "VARCHAR(64)"},
            "query_runs": {
                "user_id": "VARCHAR(32) REFERENCES users(id)",
                "question": "TEXT",
                "response": "JSON",
            },
            "facts": {"verification_method": "VARCHAR(24) DEFAULT 'manual'", "source_details": "JSON"},
        }.items():
            present = {c["name"] for c in inspect(conn).get_columns(table)}
            for name, definition in additions.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        if conn.dialect.name == "postgresql":
            # The same PDF may belong to separate accounts; deduplication is tenant-specific.
            for constraint in inspect(conn).get_unique_constraints("documents"):
                if constraint["column_names"] == ["sha256"]:
                    quoted = conn.dialect.identifier_preparer.quote(constraint["name"])
                    conn.execute(text(f"ALTER TABLE documents DROP CONSTRAINT {quoted}"))
        elif conn.dialect.name == "sqlite":
            import re

            sql = conn.scalar(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='documents'"))
            if re.search(r"UNIQUE\s*\(sha256\)", sql, re.I):
                # SQLite has no DROP CONSTRAINT; rebuild in the same transaction and preserve every column.
                indexes = conn.scalars(
                    text(
                        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='documents' AND sql IS NOT NULL"
                    )
                ).all()
                rebuilt = re.sub(r",?\s*UNIQUE\s*\(sha256\)", "", sql, flags=re.I)
                rebuilt = rebuilt.replace("CREATE TABLE documents", "CREATE TABLE documents_migrating", 1)
                conn.execute(text(rebuilt))
                columns = ", ".join(c["name"] for c in inspect(conn).get_columns("documents"))
                conn.execute(
                    text(f"INSERT INTO documents_migrating ({columns}) SELECT {columns} FROM documents")
                )
                conn.execute(text("DROP TABLE documents"))
                conn.execute(text("ALTER TABLE documents_migrating RENAME TO documents"))
                for index in indexes:
                    conn.execute(text(index))
        conn.execute(text("UPDATE documents SET dedup_key = sha256 WHERE dedup_key IS NULL"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_dedup_key ON documents(dedup_key)"))
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


def get_db(request: Request):
    with session_scope() as session:
        from .auth import authenticate_request

        authenticate_request(session, request)
        yield session
