from sqlalchemy import select

from app.auth import _attempts
from app.config import get_settings
from app.models import Document, User


def test_auth_and_tenant_isolation(client, corpus, monkeypatch):
    _attempts.clear()
    docs = corpus.scalars(select(Document)).all()
    doc_id = docs[0].id
    monkeypatch.setenv("JWT_SECRET_KEY", "a-test-secret-that-is-at-least-32-characters")
    get_settings.cache_clear()

    def register(email):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": "test-password-long", "full_name": "Test Analyst"},
        )
        assert response.status_code == 201, response.text
        return response.json()

    admin = register("admin@example.test")
    second = register("analyst@example.test")
    assert admin["user"]["role"] == "admin"
    assert second["user"]["role"] == "analyst"
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/health").status_code == 200
    headers = {"Authorization": "Bearer " + second["access_token"]}
    assert client.get("/api/documents", headers=headers).json() == []
    assert client.get(f"/api/documents/{doc_id}", headers=headers).status_code == 404
    assert client.get(f"/api/documents/{doc_id}/file", headers=headers).status_code == 404
    assert client.get("/api/facts", headers=headers).json() == []
    assert client.get("/api/analytics", headers=headers).json()["summary"]["fact_count"] == 0
    assert client.post("/api/demo", json={}, headers=headers).status_code == 403
    assert client.post("/api/search", json={"question": "revenue"}, headers=headers).json()["evidence"] == []
    assert client.get("/api/auth/me", headers=headers).json()["email"] == "analyst@example.test"
    assert (
        len(client.get("/api/documents", headers={"Authorization": "Bearer " + admin["access_token"]}).json())
        == 4
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": "analyst@example.test", "password": "test-password-long"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": "analyst@example.test", "password": "wrong-password"}
        ).status_code
        == 401
    )
    user = corpus.scalar(select(User).where(User.email == "analyst@example.test"))
    user.role = "viewer"
    corpus.commit()
    assert client.post(f"/api/documents/{doc_id}/retry", json={}, headers=headers).status_code == 403
    from uuid import uuid4

    assert (
        client.post(
            "/api/conversations",
            json={"session_id": str(uuid4()), "question": "What is this report?"},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.post("/api/auth/refresh", json={}, headers=headers).status_code == 200
