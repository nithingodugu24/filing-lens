import hashlib
import re
from datetime import timedelta

import pymupdf
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .db import session_scope
from .models import Chunk, Document, ExtractedTable, Fact, Job, Page, WorkerState, now, uid
from .providers import ProviderError, embed, fingerprint
from .schemas import DocumentMetadata


class ExtractionError(ValueError):
    pass


def enqueue(db, content: bytes, metadata: DocumentMetadata, synthetic=False):
    if not content.startswith(b"%PDF-"):
        raise ValueError("Only PDF files are supported. The file header is invalid.")
    if len(content) > get_settings().max_upload_mb * 1024 * 1024:
        raise ValueError("PDF exceeds the 20 MB upload limit.")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Document).where(Document.sha256 == digest))
    if existing:
        return existing, True
    folder = get_settings().storage_dir
    folder.mkdir(parents=True, exist_ok=True)
    # Never use a supplied filename as a storage path.
    path = folder / f"{digest}.pdf"
    path.write_bytes(content)
    values = metadata.model_dump(mode="python")
    values["source_url"] = str(metadata.source_url) if metadata.source_url else None
    document = Document(id=uid(), **values, synthetic=synthetic, sha256=digest, path=str(path.resolve()))
    try:
        with db.begin_nested():
            db.add(document)
            db.flush()
            db.add(Job(document_id=document.id))
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(Document).where(Document.sha256 == digest))
        if existing:
            return existing, True
        raise
    return document, False


def extract_pdf(path):
    try:
        pdf = pymupdf.open(path)
    except Exception:
        raise ExtractionError("PDF is damaged or unsupported. Upload a valid digitally generated PDF.") from None
    with pdf:
        if pdf.needs_pass:
            raise ExtractionError("Password-protected PDFs are unsupported. Upload an unlocked copy.")
        if not 1 <= len(pdf) <= 500:
            raise ExtractionError("PDF must contain between 1 and 500 pages.")
        pages, tables, warnings = [], [], []
        for index, page in enumerate(pdf):
            text = page.get_text(sort=True).strip().replace("\x00", "")
            pages.append((index, page.get_label() or None, text))
            try:
                for number, table in enumerate(page.find_tables().tables):
                    cells = table.extract()
                    if cells:
                        tables.append((index, number, cells))
            except Exception:
                warnings.append(f"Table extraction unavailable on PDF page {index + 1}.")
        good_pages = sum(len(re.findall(r"\w", p[2])) >= 40 for p in pages)
        if good_pages == 0:
            raise ExtractionError("Scanned or empty PDF: no reliable text. OCR is not included; use a text PDF.")
        if good_pages / len(pages) < 0.6:
            raise ExtractionError("Poor text extraction on most pages. Review the PDF or provide an accessible version.")
        if good_pages < len(pages):
            warnings.append("Some pages have little text; review before relying on this document.")
        return pages, tables, warnings


def split_text(text, max_chars=1500, overlap=180):
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + max_chars//2, end)
            if boundary > start:
                end = boundary
        value = text[start:end].strip()
        if value:
            yield value
        if end == len(text):
            break
        start = max(start + 1, end - overlap)


def process_document(db, document):
    pages, tables, warnings = extract_pdf(document.path)
    # All writes and status changes are atomic. Retrying never leaves partial evidence.
    for model in [Fact, Chunk, ExtractedTable, Page]:
        db.execute(delete(model).where(model.document_id == document.id))
    chunks = []
    for index, label, text in pages:
        db.add(Page(id=f"{document.id}:p{index}", document_id=document.id,
                    page_index=index, printed_label=label, text=text))
        for number, passage in enumerate(split_text(text)):
            chunks.append(Chunk(id=f"{document.id}:p{index}:c{number}", document_id=document.id,
                                page_index=index, text=passage, kind="passage"))
    for index, number, cells in tables:
        table_id = f"{document.id}:p{index}:t{number}"
        db.add(ExtractedTable(id=table_id, document_id=document.id, page_index=index, cells=cells))
        rendered = "\n".join(" | ".join(str(v or "") for v in row) for row in cells)
        chunks.append(Chunk(id=table_id, document_id=document.id, page_index=index,
                            kind="table", text=rendered))
    # Small batches respect provider limits and bound request memory.
    for start in range(0, len(chunks), 32):
        batch = chunks[start:start+32]
        vectors, _ = embed([c.text for c in batch])
        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_config = fingerprint()
            db.add(chunk)
    db.flush()
    # Conservative candidates: explicit metric/value/currency/unit rows only. Never auto-verify uploads.
    for chunk in chunks:
        if chunk.kind != "table":
            continue
        for match in re.finditer(r"(?im)^(Revenue|Operating margin)\s*\|\s*([\d,]+(?:\.\d+)?)"
                                 r"\s*\|\s*(INR|USD|EUR|GBP|PCT)\s*\|\s*"
                                 r"(crore|lakh|million|billion|unit|percent)\s*$", chunk.text):
            metric, value, currency, units = match.groups()
            db.add(Fact(document_id=document.id, chunk_id=chunk.id,
                        metric="revenue" if metric.lower() == "revenue" else "operating_margin",
                        value=value.replace(",", ""), currency=currency, units=units,
                        period_start=document.period_start, period_end=document.period_end,
                        basis=document.basis, verified=False, revision="original"))
    document.page_count = len(pages)
    document.warning = " ".join(warnings) or None
    document.status = "indexed"


def run_one():
    with session_scope() as db:
        state = db.get(WorkerState, "main")
        if state:
            state.last_seen = now()
        else:
            db.add(WorkerState(id="main"))
        # A crashed worker's lease can be claimed again. Exhausted jobs become failed.
        expired = db.scalars(select(Job).where(Job.status == "processing", Job.lease_until < now())).all()
        for old in expired:
            old.status = "failed" if old.attempts >= 3 else "queued"
            old.error = "Worker stopped during processing; lease expired."
            db.get(Document, old.document_id).status = old.status
        db.flush()
        statement = (select(Job).where(Job.status == "queued", Job.available_at <= now())
                     .order_by(Job.created_at).limit(1).with_for_update(skip_locked=True))
        job = db.scalar(statement)
        if not job:
            return False
        claimed = db.execute(update(Job).where(Job.id == job.id, Job.status == "queued")
                             .values(status="processing", attempts=Job.attempts + 1,
                                     lease_until=now() + timedelta(minutes=15)))
        if claimed.rowcount != 1:
            return False
        document_id, job_id = job.document_id, job.id
        db.get(Document, document_id).status = "processing"
    try:
        with session_scope() as db:
            process_document(db, db.get(Document, document_id))
            job = db.get(Job, job_id)
            job.status, job.error, job.lease_until = "complete", None, None
    except Exception as error:
        with session_scope() as db:
            job = db.get(Job, job_id)
            retry = isinstance(error, ProviderError) and job.attempts < 3
            job.status = "queued" if retry else "failed"
            job.available_at = now() + timedelta(seconds=10 * job.attempts)
            job.error = str(error) if isinstance(error, (ExtractionError, ProviderError)) else "Processing failed. Check worker logs with this job ID."
            job.lease_until = None
            document = db.get(Document, document_id)
            document.status, document.warning = job.status, job.error
        if not isinstance(error, (ExtractionError, ProviderError)):
            import logging
            logging.getLogger("filinglens").error('processing_failed job_id=%s error_type=%s', job_id, type(error).__name__)
    return True
