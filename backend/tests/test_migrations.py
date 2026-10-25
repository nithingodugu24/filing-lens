import sqlite3

from app.config import get_settings
from app.db import engine, init_db
from sqlalchemy import text


def test_old_sqlite_documents_survive_tenant_migration(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE documents (id VARCHAR(32) PRIMARY KEY, sha256 VARCHAR(64), UNIQUE (sha256))")
        db.execute("INSERT INTO documents VALUES ('old-report', 'original-hash')")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(path))
    get_settings.cache_clear()
    engine.cache_clear()
    init_db()
    init_db()
    with engine().begin() as db:
        assert db.execute(text("SELECT id, sha256, dedup_key FROM documents")).first() == (
            "old-report",
            "original-hash",
            "original-hash",
        )
        db.execute(
            text(
                "INSERT INTO documents(id,sha256,dedup_key) VALUES ('same-pdf-other-user','original-hash','other-owner-key')"
            )
        )
