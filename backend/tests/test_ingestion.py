import pymupdf
import pytest
from sqlalchemy import select

from app.demo import FIXTURES, make_pdf
from app.ingestion import ExtractionError, enqueue, extract_pdf, normalise_pdf_text, run_one
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


def test_annual_report_larger_than_old_limit_indexes(client, db):
    # Valid PDF with a large metadata stream, keeping text extraction small and deterministic.
    with pymupdf.open(stream=make_pdf(FIXTURES[0]), filetype="pdf") as pdf:
        pdf.set_xml_metadata("<synthetic-test>" + "x" * (21 * 1024 * 1024) + "</synthetic-test>")
        content = pdf.tobytes(deflate=False)
    assert len(content) > 20 * 1024 * 1024
    assert client.get("/api/ready").json()["max_upload_mb"] == 100
    response = client.post(
        "/api/documents",
        data={"metadata": metadata().model_dump_json()},
        files={"file": ("large-annual-report.pdf", content, "application/pdf")},
    )
    assert response.status_code == 202, response.text
    document_id = response.json()["document"]["id"]
    db.commit()
    run_one()
    db.expire_all()
    assert db.get(Document, document_id).status == "indexed"


def test_configured_upload_limit_returns_413(client):
    from app.config import get_settings

    get_settings().max_upload_mb = 1
    assert client.get("/api/ready").json()["max_upload_mb"] == 1
    content = b"%PDF-1.7\n" + b"x" * (1024 * 1024)
    response = client.post(
        "/api/documents",
        data={"metadata": metadata().model_dump_json()},
        files={"file": ("large.pdf", content, "application/pdf")},
    )
    assert response.status_code == 413 and "1 MB" in response.json()["detail"]
    assert client.post("/api/documents", content=b"x" * (2 * 1024 * 1024 + 1)).status_code == 413


def test_normalisation_keeps_financial_values_and_line_boundaries():
    assert normalise_pdf_text("  Revenue\t    1,23,456 crore\n\n  Operating margin     25.2% \x00\n") == (
        "Revenue 1,23,456 crore\n\nOperating margin 25.2%"
    )


def fake_pdf(monkeypatch, texts):
    from types import SimpleNamespace

    class Pdf:
        needs_pass = False

        def __len__(self):
            return len(texts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            for value in texts:
                yield SimpleNamespace(
                    get_text=lambda **kwargs: value,
                    get_label=lambda: "",
                    find_tables=lambda: SimpleNamespace(tables=[]),
                )

    monkeypatch.setattr("app.ingestion.pymupdf.open", lambda _: Pdf())


def test_column_padding_does_not_exhaust_document_budget(monkeypatch):
    value = (
        "Annual report revenue 100 crore with consolidated figures and management commentary." + " " * 1100000
    )
    fake_pdf(monkeypatch, [value, value])
    pages, _, _ = extract_pdf("unused.pdf")
    assert sum(len(p[2]) for p in pages) < 200
    assert len(pages) == 2 and "100 crore" in pages[1][2]


@pytest.mark.parametrize("kind", ["page", "document"])
def test_normalised_text_budgets_still_fail_with_actionable_message(monkeypatch, kind):
    from app.config import get_settings

    value = "Annual report revenue and operating margin commentary. " * 30
    fake_pdf(monkeypatch, [value, value])
    if kind == "page":
        get_settings().max_page_text_chars = 1000
        message = r"PDF page 1.*MAX_PAGE_TEXT_CHARS"
    else:
        get_settings().max_document_text_chars = 2000
        message = r"2,000.*MAX_DOCUMENT_TEXT_CHARS"
    with pytest.raises(ExtractionError, match=message):
        extract_pdf("unused.pdf")


def test_large_tables_have_bounded_chunks_and_no_duplicate_facts(db, monkeypatch):
    document, _ = enqueue(db, make_pdf(FIXTURES[0]), metadata())
    db.commit()
    cells = [["Metric", "Value", "Currency", "Units"], ["Revenue", "100", "INR", "crore"]]
    cells += [[f"Note {i}", "Long table cells for retrieval and inspection " * 3, "", ""] for i in range(50)]
    monkeypatch.setattr(
        "app.ingestion.extract_pdf",
        lambda path, progress=None: (
            [(0, None, "Annual financial report with consolidated revenue and management commentary.")],
            [(0, 0, cells)],
            [],
        ),
    )
    run_one()
    db.expire_all()
    chunks = db.scalars(select(Chunk).where(Chunk.document_id == document.id, Chunk.kind == "table")).all()
    assert len(chunks) > 1 and all(len(c.text) <= 1500 for c in chunks)
    facts = db.scalars(select(Fact).where(Fact.document_id == document.id)).all()
    assert len(facts) == 1 and facts[0].value == "100"
    assert "Revenue | 100 | INR | crore" in db.get(Chunk, facts[0].chunk_id).text


def test_progress_is_visible_and_cleared_after_success(db, monkeypatch):
    from app.db import session_scope
    from app.ingestion import record_progress

    document, _ = enqueue(db, make_pdf(FIXTURES[0]), metadata())
    db.commit()
    events = []

    def observe(job_id, document_id, completed, total, stage):
        record_progress(job_id, document_id, completed, total, stage)
        with session_scope() as progress_db:
            current = progress_db.get(Document, document_id)
            assert current.page_count == total and current.status == "processing"
            assert progress_db.get(Job, job_id).lease_until is not None
            events.append((completed, total, stage, current.warning))

    monkeypatch.setattr("app.ingestion.record_progress", observe)
    run_one()
    db.expire_all()
    assert events[0][:3] == (0, 2, "reading") and events[-1][:3] == (2, 2, "indexing")
    assert db.get(Document, document.id).status == "indexed"
    assert db.get(Document, document.id).warning is None
