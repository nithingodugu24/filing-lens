from sqlalchemy import select
from app.models import Document, Page


def test_annotation_crud_and_quote_check(client, corpus):
    doc = corpus.scalar(select(Document))
    page = corpus.scalar(select(Page).where(Page.document_id == doc.id))
    path = f"/api/documents/{doc.id}/annotations"
    payload = {
        "page_index": page.page_index,
        "selected_text": page.text[:40],
        "note": "Review this figure later",
    }
    response = client.post(path, json=payload)
    assert response.status_code == 201
    note = response.json()
    assert client.get(path).json()[0]["note"] == payload["note"]
    assert (
        client.post(
            path, json={**payload, "selected_text": "This sentence never appears on the page"}
        ).status_code
        == 422
    )
    assert client.post(path, json={**payload, "page_index": 999}).status_code == 404
    assert client.delete(f"/api/annotations/{note['id']}").status_code == 200
    assert client.get(path).json() == []
