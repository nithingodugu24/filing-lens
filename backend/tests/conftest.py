import os
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import Base, engine, init_db, session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        from sqlalchemy.engine import make_url

        if not (make_url(test_url).database or "").startswith("filinglens_test"):
            raise RuntimeError("Integration tests require a dedicated database named filinglens_test*.")
    monkeypatch.setenv("DATABASE_URL", test_url or f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "documents"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("EMBEDDING_MODEL", "hash-v1")
    monkeypatch.setenv("ANSWER_PROVIDER", "extractive")
    get_settings.cache_clear()
    engine.cache_clear()
    if test_url:
        Base.metadata.drop_all(engine())
    init_db()
    yield
    if test_url:
        Base.metadata.drop_all(engine())
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
