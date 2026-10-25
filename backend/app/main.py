import json
import logging
import time
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.responses import Response, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .db import engine, get_db, init_db
from .demo import seed_demo, verify_demo_facts
from .ingestion import UploadTooLarge, enqueue
from .models import Chunk, Document, ExtractedTable, Fact, Job, Page, WorkerState
from .schemas import CompareRequest, DocumentMetadata, FactReview, SearchRequest, ActionResponse
from .schemas import (
    AnalyticsResponse,
    AnswerResponse,
    DocumentResponse,
    ErrorResponse,
    FactResponse,
    HealthResponse,
    PageResponse,
    ReadyResponse,
    SearchResponse,
    UploadResponse,
)
from .answers import answer
from .finance import compare_facts
from .providers import ProviderError
from .retrieval import retrieve
from .conversations import router as conversation_router
from .analysis_jobs import router as analysis_router
from .auth import router as auth_router
from .export import router as export_router
from .annotations import router as annotation_router
from .websocket import router as event_router
from .report_workspace import router as workspace_router
from .library import router as library_router
from .history import router as history_router

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("filinglens")


@asynccontextmanager
async def lifespan(app):
    get_settings().validate_deployment()
    init_db()
    yield


app = FastAPI(
    title="FilingLens",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    contact={"name": "FilingLens project maintainer"},
    terms_of_service="/api/terms",
    swagger_ui_parameters={"displayRequestDuration": True, "filter": True, "docExpansion": "none"},
    description="""![FilingLens](/api/logo.svg)

## FilingLens — Indian financial reports
Upload a digital PDF, wait for **Ready**, ask a question and check the cited source page.

Includes checked financial comparisons, local semantic search, optional Gemini conversations,
management tone, entity exploration, annotations, exports and live progress.

**Accounts:** authentication is optional. When JWT_SECRET_KEY is configured, register or sign in
and use the Authorize button with your bearer token. The first account is the administrator.
**Evidence:** PDF content is untrusted data. Literal quotation validation is not a guarantee of
semantic correctness. Synthetic samples are labelled and are unsuitable for financial decisions.
**Privacy:** uploaded documents stay on this server. Enabling a remote answer/embedding provider
sends the question and/or retrieved passages to that configured provider.

See docs/API.md and docs/UPGRADE_GUIDE.md in the repository for setup and reproducible examples.
""",
    responses={
        code: {
            "model": ErrorResponse,
            "description": message,
            "content": {
                "application/json": {"example": {"detail": message, "request_id": "request identifier"}}
            },
        }
        for code, message in {
            401: "Sign in required",
            403: "Your account cannot perform this action",
            404: "Resource not found",
            409: "The action conflicts with current report state",
            413: "The upload is too large",
            415: "A PDF is required",
            422: "Invalid input",
            429: "Too many requests",
            503: "Database, worker or configured model is unavailable",
        }.items()
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
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

app.include_router(conversation_router)
app.include_router(analysis_router)
app.include_router(auth_router)
app.include_router(export_router)
app.include_router(annotation_router)
app.include_router(event_router)
app.include_router(workspace_router)
app.include_router(library_router)
app.include_router(history_router)


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


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return JSONResponse(
        {"detail": error.detail, "request_id": getattr(request.state, "request_id", None)},
        status_code=error.status_code,
        headers=error.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse(
        {
            "detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in error.errors()],
            "request_id": getattr(request.state, "request_id", None),
        },
        status_code=422,
    )


@app.get("/api/logo.svg", include_in_schema=False)
def logo():
    return Response(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 230 48"><rect width="44" height="44" x="2" y="2" rx="9" fill="#14634b"/><path d="M15 12h10l7 7v15H15z M25 12v8h7 M19 25h9 M19 29h9" fill="none" stroke="white" stroke-width="2"/><text x="57" y="32" font-family="sans-serif" font-size="27" fill="#14634b">FilingLens</text></svg>',
        media_type="image/svg+xml",
    )


@app.get("/api/terms", include_in_schema=False, response_class=PlainTextResponse)
def terms():
    return "FilingLens helps you read and compare company reports using source-linked figures and explanations. Upload documents you are permitted to process. Automatic checks are not an independent audit. Verify cited source pages before making decisions. Remote AI services receive the selected report passages. Prepared library reports identify their issuer sources."


@app.exception_handler(ProviderError)
async def provider_error(request, error):
    return JSONResponse(
        {"detail": str(error), "request_id": getattr(request.state, "request_id", None)}, status_code=503
    )


@app.exception_handler(UploadTooLarge)
async def upload_too_large(request, error):
    return JSONResponse(
        {"detail": str(error), "request_id": getattr(request.state, "request_id", None)}, status_code=413
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


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health():
    """Lightweight liveness probe. Does not contact a model or require an account."""
    return {"status": "ok", "service": "FilingLens"}


@app.get("/docs", include_in_schema=False)
def docs_redirect():
    return RedirectResponse("/api/docs")


@app.get("/api/ready", response_model=ReadyResponse, tags=["Health"])
def ready(db: Session = Depends(get_db)):
    """Check database access and recent worker heartbeat, and report configured providers and upload limits. No credentials are returned."""
    db.execute(text("SELECT 1"))
    state = db.get(WorkerState, "main")
    worker_ok = (
        state is not None
        and (datetime.now(timezone.utc) - state.last_seen.replace(tzinfo=timezone.utc)).total_seconds() < 30
    )
    s = get_settings()
    host = urlsplit(s.provider_base_url).hostname
    answer_service = (
        "Gemini"
        if s.answer_provider == "gemini"
        else (
            "River AI"
            if host == "api.river.ai"
            else "OpenAI"
            if host == "api.openai.com"
            else "Configured AI service"
        )
    )
    answer_model = s.gemini_model if s.answer_provider == "gemini" else s.answer_model
    configured = (
        bool(s.gemini_api_key)
        if s.answer_provider == "gemini"
        else bool(s.provider_api_key and s.answer_model)
    )
    return {
        "database": engine().dialect.name,
        "worker": "online" if worker_ok else "offline",
        "answer_provider": s.answer_provider,
        "answer_service": answer_service if s.answer_provider != "extractive" else "Report excerpts",
        "answer_model": answer_model if s.answer_provider != "extractive" else None,
        "answer_status": "offline"
        if s.answer_provider == "extractive"
        else "configured"
        if configured
        else "needs_setup",
        "embedding_provider": s.embedding_provider,
        "embedding_model": s.embedding_model,
        "embedding_dimensions": s.embedding_dimensions,
        "max_upload_mb": s.max_upload_mb,
        "max_pdf_pages": s.max_pdf_pages,
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
        if column.name not in {"path", "user_id", "dedup_key"}
    }
    job = db.scalar(select(Job).where(Job.document_id == document.id).order_by(Job.created_at.desc()))
    data["job"] = (
        {"id": job.id, "status": job.status, "attempts": job.attempts, "error": job.error} if job else None
    )
    return data


@app.post("/api/documents", status_code=202, response_model=UploadResponse, tags=["Documents"])
async def upload_document(
    metadata: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Accept a digital PDF with a JSON metadata form field. SHA-256 deduplication is scoped to the account. Returns 202 after the queue write commits; inspect document status before asking questions."""
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
    db.commit()
    return {"document": document_json(db, document), "duplicate": duplicate}


@app.get("/api/documents", response_model=list[DocumentResponse], tags=["Documents"])
def documents(db: Session = Depends(get_db)):
    """List visible reports ordered by reporting period and company. Analysts see their own reports; administrators can see all. Storage paths and ownership keys are omitted."""
    return [
        document_json(db, d)
        for d in db.scalars(select(Document).order_by(Document.period_end.desc(), Document.company))
    ]


@app.get("/api/documents/{document_id}", response_model=DocumentResponse, tags=["Documents"])
def document_detail(document_id: str, db: Session = Depends(get_db)):
    """Return saved metadata and the latest indexing job for one visible report. An inaccessible report returns 404."""
    return document_json(db, require_document(db, document_id))


@app.get(
    "/api/documents/{document_id}/file",
    tags=["Documents"],
    response_class=FileResponse,
    responses={200: {"content": {"application/pdf": {}}}},
)
def document_file(document_id: str, db: Session = Depends(get_db)):
    """Stream the original source PDF inline after checking document access. PDF page anchors are one-based browser navigation, not server filters."""
    doc = require_document(db, document_id)
    return FileResponse(
        doc.path, media_type="application/pdf", filename=f"{doc.id}.pdf", content_disposition_type="inline"
    )


@app.get("/api/documents/{document_id}/pages/{page_index}", response_model=PageResponse, tags=["Documents"])
def document_page(document_id: str, page_index: int, db: Session = Depends(get_db)):
    """Return extracted text, printed page label and table cells for a zero-based PDF page. A missing or not-yet-indexed page returns 404."""
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


@app.post(
    "/api/documents/{document_id}/retry", status_code=202, response_model=ActionResponse, tags=["Documents"]
)
def retry_document(document_id: str, db: Session = Depends(get_db)):
    """Queue a failed report for another indexing attempt. Reports in any other state return 409."""
    document = require_document(db, document_id)
    if document.status != "failed":
        raise HTTPException(409, "Only failed documents can be retried.")
    document.status, document.warning = "queued", None
    db.add(Job(document_id=document_id))
    db.commit()
    return {"status": "queued"}


@app.post(
    "/api/documents/{document_id}/reindex", status_code=202, response_model=ActionResponse, tags=["Documents"]
)
def reindex_document(document_id: str, db: Session = Depends(get_db)):
    """Re-extract and re-embed a ready or failed report. This resets extracted fact reviews. Use scripts/rebuild_embeddings.py to change only vectors and preserve reviews."""
    document = require_document(db, document_id)
    if document.status not in {"indexed", "failed"}:
        raise HTTPException(409, "Wait for the current processing job to finish.")
    document.status, document.warning = "queued", "Reindexing resets extracted facts and their reviews."
    db.add(Job(document_id=document_id))
    db.commit()
    return {"status": "queued", "message": document.warning}


@app.post("/api/demo", status_code=202, response_model=ActionResponse, tags=["Documents"])
def demo(db: Session = Depends(get_db)):
    """Queue four made-up financial PDFs, idempotently. Requires administrator role when accounts are enabled."""
    return seed_demo(db)


@app.get("/api/facts", response_model=list[FactResponse], tags=["Facts"])
def facts(db: Session = Depends(get_db)):
    """List visible financial fact candidates with checked status, basis, units, revision and source page. Only synthetic fixtures are automatically checked against their fixture specification."""
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


@app.get("/api/analytics", response_model=AnalyticsResponse, tags=["Analytics"])
def get_analytics(
    synthetic: bool | None = None, document_ids: str | None = None, db: Session = Depends(get_db)
):
    """Return checked financial series; synthetic and uploaded sources can be filtered separately."""
    from .analytics import analytics

    verify_demo_facts(db)
    return analytics(db, synthetic, document_ids.split(",") if document_ids is not None else None)


@app.patch("/api/facts/{fact_id}", response_model=ActionResponse, tags=["Facts"])
def review_fact(fact_id: str, review: FactReview, db: Session = Depends(get_db)):
    """Record an analyst review and optional original/restated revision. A note of at least 12 characters is required. Viewing a source does not automatically verify its figures."""
    fact = db.get(Fact, fact_id)
    if not fact:
        raise HTTPException(404, "Fact not found")
    require_document(db, fact.document_id)
    fact.verified, fact.review_note = review.verified, review.note
    fact.verification_method = "manual"
    if review.revision:
        fact.revision = review.revision
    db.commit()
    return {"id": fact.id, "verified": fact.verified}


@app.post("/api/search", response_model=SearchResponse, tags=["Search"])
def search(request: SearchRequest, db: Session = Depends(get_db)):
    """Retrieve up to k distinct source pages using keyword, vector or hybrid RRF search. All filters apply before ranking. Vector configuration must match the indexed vectors."""
    evidence, usage = retrieve(db, request)
    return {"evidence": evidence, "usage": usage, "mode": request.mode}


@app.post("/api/questions", response_model=AnswerResponse, tags=["Questions"])
def question(request: SearchRequest, db: Session = Depends(get_db)):
    """Answer from scoped source evidence, or return an explicit abstention. Simple report-overview requests use saved metadata. Optional remote generation validates citation IDs and literal quotes; numerical comparisons use Decimal arithmetic."""
    verify_demo_facts(db)
    response = answer(db, request)
    db.commit()
    return response


@app.post("/api/compare", response_model=ActionResponse, tags=["Facts"])
def compare(request: CompareRequest, db: Session = Depends(get_db)):
    """Compare two checked facts. Rejects incompatible currencies, basis, revisions, reporting durations, mixed real/sample inputs and a zero denominator. Returns the formula, converted inputs and source references."""
    verify_demo_facts(db)
    return compare_facts(db, request)


_base_openapi = app.openapi


def documented_openapi():
    spec = _base_openapi()
    spec.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Required only when JWT_SECRET_KEY is configured. Sign in via /api/auth/login.",
    }
    public = {"/api/health", "/api/ready", "/api/auth/config", "/api/auth/register", "/api/auth/login"}
    for path, operations in spec["paths"].items():
        if path not in public:
            for operation in operations.values():
                operation["security"] = [{"BearerAuth": []}]
    return spec


app.openapi = documented_openapi
