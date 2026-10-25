import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .db import engine, get_db, init_db
from .demo import seed_demo, verify_demo_facts
from .ingestion import enqueue
from .models import Chunk, Document, ExtractedTable, Fact, Job, Page, WorkerState
from .schemas import CompareRequest, DocumentMetadata, FactReview, SearchRequest
from .answers import answer
from .finance import compare_facts
from .providers import ProviderError
from .retrieval import retrieve

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("filinglens")


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(
    title="FilingLens",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    description="Evidence-first Indian financial filings intelligence. Local demo, no authentication.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "PUT"}:
            return await self.app(scope, receive, send)
        limit = (
            (get_settings().max_upload_mb + 1) * 1024 * 1024 if scope["path"] == "/api/documents" else 65536
        )
        messages, total = [], 0
        while True:
            message = await receive()
            total += len(message.get("body", b""))
            if total > limit:
                response = JSONResponse({"detail": "Request exceeds size limit."}, status_code=413)
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)


app.add_middleware(BodyLimitMiddleware)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id, start = uuid4().hex, time.perf_counter()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info(
        json.dumps(
            {
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(ValueError)
async def invalid_value(request, error):
    return JSONResponse(
        {"detail": str(error), "request_id": getattr(request.state, "request_id", None)}, status_code=422
    )


@app.exception_handler(ProviderError)
async def provider_error(request, error):
    return JSONResponse(
        {"detail": str(error), "request_id": getattr(request.state, "request_id", None)}, status_code=503
    )


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request, error):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        json.dumps(
            {"event": "database_unavailable", "request_id": request_id, "error_type": type(error).__name__}
        )
    )
    return JSONResponse(
        {"detail": "Database is temporarily unavailable. Please try again.", "request_id": request_id},
        status_code=503,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FilingLens"}


@app.get("/docs", include_in_schema=False)
def docs_redirect():
    return RedirectResponse("/api/docs")


@app.get("/api/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    state = db.get(WorkerState, "main")
    worker_ok = (
        state is not None
        and (datetime.now(timezone.utc) - state.last_seen.replace(tzinfo=timezone.utc)).total_seconds() < 30
    )
    s = get_settings()
    return {
        "database": engine().dialect.name,
        "worker": "online" if worker_ok else "offline",
        "answer_provider": s.answer_provider,
        "embedding_provider": s.embedding_provider,
        "embedding_model": s.embedding_model,
        "embedding_dimensions": s.embedding_dimensions,
        "mode": "extractive offline demo" if s.answer_provider == "extractive" else "generative provider",
    }


def require_document(db, document_id):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return document


def document_json(db, document):
    data = {
        column.name: getattr(document, column.name)
        for column in Document.__table__.columns
        if column.name != "path"
    }
    job = db.scalar(select(Job).where(Job.document_id == document.id).order_by(Job.created_at.desc()))
    data["job"] = (
        {"id": job.id, "status": job.status, "attempts": job.attempts, "error": job.error} if job else None
    )
    return data


@app.post("/api/documents", status_code=202)
async def upload_document(
    metadata: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
):
    try:
        parsed = DocumentMetadata.model_validate_json(metadata)
    except ValidationError:
        raise HTTPException(
            422, "Invalid metadata: check company, dates, document type, basis, currency and units."
        ) from None
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(415, "Select a PDF file.")
    content = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    document, duplicate = enqueue(db, content, parsed)
    return {"document": document_json(db, document), "duplicate": duplicate}


@app.get("/api/documents")
def documents(db: Session = Depends(get_db)):
    return [
        document_json(db, d)
        for d in db.scalars(select(Document).order_by(Document.period_end.desc(), Document.company))
    ]


@app.get("/api/documents/{document_id}")
def document_detail(document_id: str, db: Session = Depends(get_db)):
    return document_json(db, require_document(db, document_id))


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: str, db: Session = Depends(get_db)):
    doc = require_document(db, document_id)
    return FileResponse(
        doc.path, media_type="application/pdf", filename=f"{doc.id}.pdf", content_disposition_type="inline"
    )


@app.get("/api/documents/{document_id}/pages/{page_index}")
def document_page(document_id: str, page_index: int, db: Session = Depends(get_db)):
    require_document(db, document_id)
    page = db.scalar(select(Page).where(Page.document_id == document_id, Page.page_index == page_index))
    if not page:
        raise HTTPException(404, "Page not found. Wait for indexing to complete.")
    tables = db.scalars(
        select(ExtractedTable).where(
            ExtractedTable.document_id == document_id, ExtractedTable.page_index == page_index
        )
    ).all()
    return {
        "page_index": page_index,
        "printed_label": page.printed_label,
        "text": page.text,
        "tables": [{"id": t.id, "cells": t.cells} for t in tables],
    }


@app.post("/api/documents/{document_id}/retry", status_code=202)
def retry_document(document_id: str, db: Session = Depends(get_db)):
    document = require_document(db, document_id)
    if document.status != "failed":
        raise HTTPException(409, "Only failed documents can be retried.")
    document.status, document.warning = "queued", None
    db.add(Job(document_id=document_id))
    return {"status": "queued"}


@app.post("/api/documents/{document_id}/reindex", status_code=202)
def reindex_document(document_id: str, db: Session = Depends(get_db)):
    document = require_document(db, document_id)
    if document.status not in {"indexed", "failed"}:
        raise HTTPException(409, "Wait for the current processing job to finish.")
    document.status, document.warning = "queued", "Reindexing resets extracted facts and their reviews."
    db.add(Job(document_id=document_id))
    return {"status": "queued", "message": document.warning}


@app.post("/api/demo", status_code=202)
def demo(db: Session = Depends(get_db)):
    return seed_demo(db)


@app.get("/api/facts")
def facts(db: Session = Depends(get_db)):
    verify_demo_facts(db)
    result = []
    for fact, doc, chunk in db.execute(
        select(Fact, Document, Chunk)
        .join(Document, Fact.document_id == Document.id)
        .join(Chunk, Fact.chunk_id == Chunk.id)
    ):
        result.append(
            {
                **{c.name: getattr(fact, c.name) for c in Fact.__table__.columns},
                "company": doc.company,
                "synthetic": doc.synthetic,
                "title": doc.title,
                "page_index": chunk.page_index,
                "source_text": chunk.text,
            }
        )
    return result


@app.patch("/api/facts/{fact_id}")
def review_fact(fact_id: str, review: FactReview, db: Session = Depends(get_db)):
    fact = db.get(Fact, fact_id)
    if not fact:
        raise HTTPException(404, "Fact not found")
    fact.verified, fact.review_note = review.verified, review.note
    if review.revision:
        fact.revision = review.revision
    return {"id": fact.id, "verified": fact.verified}


@app.post("/api/search")
def search(request: SearchRequest, db: Session = Depends(get_db)):
    evidence, usage = retrieve(db, request)
    return {"evidence": evidence, "usage": usage, "mode": request.mode}


@app.post("/api/questions")
def question(request: SearchRequest, db: Session = Depends(get_db)):
    verify_demo_facts(db)
    return answer(db, request)


@app.post("/api/compare")
def compare(request: CompareRequest, db: Session = Depends(get_db)):
    verify_demo_facts(db)
    return compare_facts(db, request)
