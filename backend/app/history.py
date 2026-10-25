"""Saved questions and answers, scoped to the signed-in account and visible reports."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis_jobs import document_or_404
from .db import get_db
from .models import Document, QueryRun

router = APIRouter(prefix="/api/history", tags=["Answer history"])


@router.get("")
def history(document_id: str | None = None, db: Session = Depends(get_db)):
    if document_id:
        document_or_404(db, document_id)
    visible = set(db.scalars(select(Document.id)))
    result = []
    for run in db.scalars(
        select(QueryRun).where(QueryRun.response.is_not(None)).order_by(QueryRun.created_at.desc()).limit(200)
    ):
        if run.configuration.get("purpose") == "report_brief" or (run.question or "").startswith(
            "Summarise the business performance"
        ):
            continue
        ids = {e["document_id"] for e in run.response.get("evidence", [])}
        if ids and ids <= visible and (not document_id or document_id in ids):
            result.append(
                {
                    "id": run.id,
                    "question": run.question,
                    "created_at": run.created_at,
                    "response": run.response,
                }
            )
        if len(result) == 20:
            break
    return result


@router.delete("/{run_id}")
def remove_answer(run_id: str, db: Session = Depends(get_db)):
    run = db.get(QueryRun, run_id)
    if run is None:
        raise HTTPException(404, "Saved answer not found")
    db.delete(run)
    db.commit()
    return {"status": "removed"}
