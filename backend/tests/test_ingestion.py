import pymupdf
import pytest
from sqlalchemy import select

from app.demo import FIXTURES, make_pdf
from app.ingestion import ExtractionError, enqueue, extract_pdf, run_one
from app.models import Chunk, Document, ExtractedTable, Fact, Job, Page
from app.schemas import DocumentMetadata


def metadata():
    return DocumentMetadata(
        company="TCS",
        title="Test document",
        document_type="quarterly_results",
        period_start="2025-04-01",
        period_end="2025-06-30",
        basis="consolidated",
    )


def test_duplicate_hash_and_filename_independent(db):
    content = make_pdf(FIXTURES[0])
    first, duplicate = enqueue(db, content, metadata())
    second, again = enqueue(db, content, metadata())
    assert not duplicate and again and first.id == second.id
    assert len(db.scalars(select(Job)).all()) == 1


def test_extraction_pages_tables_and_unverified_facts(db):
    document, _ = enqueue(db, make_pdf(FIXTURES[0]), metadata())
    db.commit()
    assert run_one()
    db.expire_all()
    assert db.get(Document, document.id).status == "indexed"
    pages = db.scalars(select(Page).order_by(Page.page_index)).all()
    assert len(pages) == 2 and pages[0].page_index == 0
    assert "salary" in pages[1].text
    assert db.scalar(select(ExtractedTable)) is not None
    assert len(db.scalars(select(Fact)).all()) == 2
    assert all(not f.verified for f in db.scalars(select(Fact)))
    assert db.scalar(select(Chunk)).embedding_config == "local:hash-v1:256"


def test_invalid_upload_header(db):
    with pytest.raises(ValueError, match="header"):
        enqueue(db, b"not a PDF", metadata())


def test_scanned_pdf_failed_and_retry(client, db, tmp_path):
    pdf = pymupdf.open()
    pdf.new_page()
    content = pdf.tobytes()
    document, _ = enqueue(db, content, metadata())
    db.commit()
    run_one()
    db.expire_all()
    assert db.get(Document, document.id).status == "failed"
    job = db.scalar(select(Job))
    assert "Scanned" in job.error
    assert db.scalar(select(Chunk)) is None
    assert client.post(f"/api/documents/{document.id}/retry").status_code == 202
    assert client.post(f"/api/documents/{document.id}/retry").status_code == 409


def test_broken_pdf(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7 garbage")
    with pytest.raises(ExtractionError, match="damaged"):
        extract_pdf(path)


def test_upload_metadata_and_request_limits(client):
    assert (
        client.post(
            "/api/documents",
            data={"metadata": "{}"},
            files={"file": ("x.pdf", b"%PDF-test", "application/pdf")},
        ).status_code
        == 422
    )
    assert client.post("/api/demo", content=b"x" * 65537).status_code == 413
    response = client.get("/api/health")
    assert response.headers["X-Request-ID"]


def test_valid_upload_and_malicious_filename(client, db):
    content = make_pdf(FIXTURES[0])
    response = client.post(
        "/api/documents",
        data={"metadata": metadata().model_dump_json()},
        files={"file": ("../../escape.pdf", content, "application/pdf")},
    )
    assert response.status_code == 202, response.text
    doc = response.json()["document"]
    stored = db.get(Document, doc["id"])
    assert stored.path.endswith(f"{stored.sha256}.pdf")
    assert "escape" not in stored.path
    run_one()
    response = client.get(f"/api/documents/{doc['id']}/file")
    assert response.status_code == 200 and response.content.startswith(b"%PDF-")


def test_provider_failure_rolls_back_and_retries(db, monkeypatch):
    from app.providers import ProviderError

    doc, _ = enqueue(db, make_pdf(FIXTURES[0]), metadata())
    db.commit()

    def unavailable(*args):
        raise ProviderError("Provider timed out")

    monkeypatch.setattr("app.ingestion.embed", unavailable)
    run_one()
    db.expire_all()
    assert db.get(Document, doc.id).status == "queued"
    assert db.scalar(select(Chunk)) is None and db.scalar(select(Page)) is None
    job = db.scalar(select(Job))
    assert job.attempts == 1 and "timed out" in job.error
