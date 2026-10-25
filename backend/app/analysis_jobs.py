from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, session_scope
from .models import (
    AnalysisTask,
    Document,
    Entity,
    Relationship,
    SentimentResult,
    StatusEvent,
    WorkerState,
    now,
)
from .providers import ProviderError

router = APIRouter(tags=["Analysis"])


def document_or_404(db, document_id):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


def enqueue_analysis(db, document_id, kind):
    existing = db.scalar(
        select(AnalysisTask).where(
            AnalysisTask.document_id == document_id,
            AnalysisTask.job_type == kind,
            AnalysisTask.status.in_(["queued", "processing"]),
        )
    )
    if existing:
        return existing
    task = AnalysisTask(document_id=document_id, job_type=kind)
    db.add(task)
    db.flush()
    return task


@router.post("/api/documents/{document_id}/analyze-sentiment", status_code=202)
def queue_sentiment(document_id: str, db: Session = Depends(get_db)):
    doc = document_or_404(db, document_id)
    if doc.status != "indexed":
        raise HTTPException(409, "Wait for the report to be ready")
    if not get_settings().sentiment_enabled:
        raise HTTPException(
            503, "Sentiment analysis is optional. Enable SENTIMENT_ENABLED and install [ml] on the worker."
        )
    task = enqueue_analysis(db, document_id, "sentiment")
    db.commit()
    return {"id": task.id, "status": task.status}


@router.post("/api/documents/{document_id}/extract-entities", status_code=202)
def queue_entities(document_id: str, db: Session = Depends(get_db)):
    doc = document_or_404(db, document_id)
    if doc.status != "indexed":
        raise HTTPException(409, "Wait for the report to be ready")
    if not get_settings().ner_enabled:
        raise HTTPException(
            503,
            "Entity extraction is optional. Enable NER_ENABLED and install spaCy's English model on the worker.",
        )
    task = enqueue_analysis(db, document_id, "entities")
    db.commit()
    return {"id": task.id, "status": task.status}


@router.get("/api/documents/{document_id}/sentiment")
def sentiment_result(document_id: str, db: Session = Depends(get_db)):
    document_or_404(db, document_id)
    result = db.scalar(select(SentimentResult).where(SentimentResult.document_id == document_id))
    task = db.scalar(
        select(AnalysisTask)
        .where(AnalysisTask.document_id == document_id, AnalysisTask.job_type == "sentiment")
        .order_by(AnalysisTask.created_at.desc())
    )
    return {
        "enabled": get_settings().sentiment_enabled,
        "status": task.status if task else "not_requested",
        "error": task.error if task else None,
        "result": {
            "overall_sentiment": result.overall_sentiment,
            "confidence": result.overall_confidence,
            "section_sentiments": result.section_results,
            "analyzed_at": result.analyzed_at,
        }
        if result
        else None,
    }


@router.get("/api/documents/{document_id}/entities")
def entity_list(document_id: str, db: Session = Depends(get_db)):
    document_or_404(db, document_id)
    return [
        {
            "id": e.id,
            "type": e.entity_type,
            "text": e.text,
            "page_index": e.page_index,
            "count": e.count,
            "mentions": e.details["mentions"],
        }
        for e in db.scalars(
            select(Entity).where(Entity.document_id == document_id).order_by(Entity.count.desc())
        )
    ]


@router.get("/api/documents/{document_id}/knowledge-graph")
def knowledge_graph(document_id: str, db: Session = Depends(get_db)):
    nodes = entity_list(document_id, db)
    edges = [
        {"id": r.id, "from": r.source_entity_id, "to": r.target_entity_id, "label": r.relationship_type}
        for r in db.scalars(select(Relationship).where(Relationship.document_id == document_id))
    ]
    task = db.scalar(
        select(AnalysisTask)
        .where(AnalysisTask.document_id == document_id, AnalysisTask.job_type == "entities")
        .order_by(AnalysisTask.created_at.desc())
    )
    return {
        "nodes": nodes,
        "edges": edges,
        "status": task.status if task else "not_requested",
        "error": task.error if task else None,
        "enabled": get_settings().ner_enabled,
        "limitation": "Edges mean mentioned in the same sentence. They do not establish a financial or executive relationship.",
    }


@router.get("/api/sentiment", tags=["Analytics"])
def sentiment_timeline(synthetic: bool | None = None, db: Session = Depends(get_db)):
    return [
        {
            "document_id": d.id,
            "company": d.company,
            "period_end": str(d.period_end),
            "sentiment": s.overall_sentiment,
            "confidence": s.overall_confidence,
            "score": sum(x["scores"]["positive"] - x["scores"]["negative"] for x in s.section_results)
            / len(s.section_results),
        }
        for s, d in db.execute(
            select(SentimentResult, Document)
            .join(Document, Document.id == SentimentResult.document_id)
            .order_by(Document.period_end)
        )
        if synthetic is None or d.synthetic == synthetic
    ]


def run_analysis_one():
    with session_scope() as db:
        for expired in db.scalars(
            select(AnalysisTask).where(AnalysisTask.status == "processing", AnalysisTask.lease_until < now())
        ):
            expired.status, expired.error = "failed", "Analysis worker stopped. Request analysis again."
        task = db.scalar(
            select(AnalysisTask)
            .where(AnalysisTask.status == "queued")
            .order_by(AnalysisTask.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if task is None:
            return False
        claimed = db.execute(
            update(AnalysisTask)
            .where(AnalysisTask.id == task.id, AnalysisTask.status == "queued")
            .values(status="processing", lease_until=now() + timedelta(minutes=30))
        )
        if claimed.rowcount != 1:
            return False
        task_id, document_id, kind = task.id, task.document_id, task.job_type
    try:
        with session_scope() as db:
            if kind == "sentiment":
                from .sentiment import analyze_document

                analyze_document(db, document_id)
            else:
                from .ner import extract_entities

                extract_entities(db, document_id)
            task = db.get(AnalysisTask, task_id)
            task.status, task.error = "complete", None
            db.add(
                StatusEvent(
                    document_id=document_id, payload={"type": kind + "_complete", "document_id": document_id}
                )
            )
    except Exception as error:
        with session_scope() as db:
            task = db.get(AnalysisTask, task_id)
            task.status = "failed"
            task.error = (
                str(error)
                if isinstance(error, (ValueError, ProviderError))
                else "Analysis failed. Check the worker logs."
            )
    finally:
        with session_scope() as db:
            state = db.get(WorkerState, "main")
            if state:
                state.last_seen = now()
    return True
