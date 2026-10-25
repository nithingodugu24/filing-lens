import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import engine, init_db, session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "documents"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("EMBEDDING_MODEL", "hash-v1")
    monkeypatch.setenv("ANSWER_PROVIDER", "extractive")
    get_settings.cache_clear()
    engine.cache_clear()
    init_db()
    yield
    engine().dispose()
    engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def db():
    with session_scope() as db:
        yield db


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def corpus(db):
    from app.demo import seed_demo, verify_demo_facts
    from app.ingestion import run_one
    seed_demo(db)
    while run_one():
        pass
    verify_demo_facts(db)
    db.commit()
    return db
