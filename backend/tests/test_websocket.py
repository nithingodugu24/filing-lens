from sqlalchemy import select
from app.models import Document, StatusEvent


def test_events_cross_database_sessions(client, corpus):
    doc = corpus.scalar(select(Document))
    with client.websocket_connect("/api/ws") as ws:
        assert ws.receive_json()["type"] == "connected"
        corpus.add(
            StatusEvent(
                document_id=doc.id,
                payload={"type": "job_complete", "document_id": doc.id, "status": "indexed", "page_count": 2},
            )
        )
        corpus.commit()
        event = ws.receive_json()
        assert event["type"] == "job_complete" and event["page_count"] == 2


def test_worker_events_respect_tenant_boundary(corpus):
    from app.websocket import events_after

    assert events_after(0, {"id": "another-user", "role": "analyst"}) == []
    assert events_after(0)
