"""A report opens with sourced figures and a prepared, cited qualitative brief."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis_jobs import document_or_404, enqueue_analysis
from .config import get_settings
from .db import get_db
from .financial_metrics import extract_financial_metrics
from .metric_answers import fact_evidence, metric_card
from .models import Chunk, Document, Fact, QueryRun, ReportBrief, now

router = APIRouter(tags=["Report workspace"])


def report_financials(db, doc, basis=None):
    rows = db.execute(
        select(Fact, Chunk)
        .join(Chunk, Chunk.id == Fact.chunk_id)
        .where(Fact.document_id == doc.id, Fact.verified.is_(True), Fact.basis == (basis or doc.basis))
        .order_by(Fact.period_end.desc())
    ).all()
    cards, evidence = [], {}
    for fact, chunk in rows:
        prior = next(
            (
                p
                for p, _ in rows
                if p.metric == fact.metric
                and p.period_end.year == fact.period_end.year - 1
                and (p.currency, p.units, p.basis, p.revision)
                == (fact.currency, fact.units, fact.basis, fact.revision)
            ),
            None,
        )
        cards.append(metric_card(fact, doc, chunk, prior, "crore" if fact.currency == "INR" else None))
        evidence[chunk.id] = fact_evidence(db, fact, doc, chunk)
    return cards, list(evidence.values())


def prepare_brief(db, document_id):
    from .answers import answer
    from .schemas import SearchRequest

    doc = document_or_404(db, document_id)
    extract_financial_metrics(db, doc)
    brief = db.scalar(select(ReportBrief).where(ReportBrief.document_id == doc.id))
    if brief is None:
        brief = ReportBrief(document_id=doc.id)
        db.add(brief)
    brief.updated_at = now()
    brief.version = "report-brief-v2"
    if get_settings().answer_provider == "extractive":
        brief.status, brief.content = "metrics_only", {}
        return
    try:
        topics = [
            (
                "Business performance",
                "How did the company's business perform during this reporting year? Describe demand, business segments and major achievements from management's discussion. Give two key findings without repeating financial amounts.",
            ),
            (
                "Management explanation",
                "What explanation did management give for changes in revenue, profitability or demand during this reporting year? Use only explicitly stated reasons; do not calculate or repeat financial amounts.",
            ),
            (
                "Business risks",
                "What principal business risks did management identify for this reporting year? Give material risks described, rather than describing the risk governance process.",
            ),
        ]
        claims, sources, sections = [], {}, []
        response = {}
        searches = [
            "business performance demand growth large deal wins management outlook",
            "management discussion revenue growth profitability margins demand explanation",
            "business outlook geopolitical demand cybersecurity risks",
        ]
        for (label, question), search in zip(topics, searches, strict=True):
            response = answer(
                db,
                SearchRequest(question=question, mode="hybrid", k=8, filters={"document_ids": [doc.id]}),
                retrieval_request=SearchRequest(
                    question=search, mode="hybrid", k=12, filters={"document_ids": [doc.id]}
                ),
            )
            run = db.get(QueryRun, response["run_id"])
            run.configuration = {**run.configuration, "purpose": "report_brief"}
            accepted = response["claims"][:2] if not response["abstained"] else []
            claims.extend({**c, "kind": label} for c in accepted)
            sources.update({e["id"]: e for e in response["evidence"]})
            sections.append(
                {
                    "label": label,
                    "available": bool(accepted),
                    "limitation": response["limitation"] if not accepted else None,
                }
            )
        brief.content = {
            **response,
            "run_id": None,
            "claims": claims,
            "evidence": list(sources.values()),
            "sections": sections,
            "abstained": not claims,
            "confidence": None,
            "summary": "",
        }
        brief.status = "ready" if all(s["available"] for s in sections) else "limited"
        brief.error = None
    except Exception:
        # Figures remain available when the AI service is unavailable. No secret/provider body leaks.
        brief.status, brief.error = (
            "unavailable",
            "The report brief could not be prepared. You can still use the source figures and ask a question.",
        )


@router.get("/api/documents/{document_id}/workspace")
def workspace(document_id: str, basis: str | None = None, db: Session = Depends(get_db)):
    doc = document_or_404(db, document_id)
    db.scalar(select(Document).where(Document.id == doc.id).with_for_update())
    if basis is not None and basis not in {"consolidated", "standalone"}:
        raise HTTPException(422, "Choose consolidated or standalone")
    cards, evidence = report_financials(db, doc, basis)
    brief = db.scalar(select(ReportBrief).where(ReportBrief.document_id == doc.id))
    if brief is None and doc.status == "indexed":
        brief = ReportBrief(document_id=doc.id, status="preparing", content={})
        db.add(brief)
        enqueue_analysis(db, doc.id, "brief")
        db.commit()
    return {
        "document_id": doc.id,
        "financials": cards,
        "evidence": evidence,
        "brief": {"status": brief.status, "content": brief.content, "error": brief.error}
        if brief
        else {"status": "preparing", "content": {}, "error": None},
        "coverage": {
            "metric_count": len({m["metric"] for m in cards}),
            "period_count": len({m["period_end"] for m in cards}),
        },
        "checks_explained": "Automatic checks confirm the source row, accounting basis, period, units and row totals. They are not an independent audit.",
    }


@router.post("/api/documents/{document_id}/brief", status_code=202)
def refresh_brief(document_id: str, db: Session = Depends(get_db)):
    doc = document_or_404(db, document_id)
    if doc.status != "indexed":
        raise HTTPException(409, "Wait for the report to finish processing")
    task = enqueue_analysis(db, doc.id, "brief")
    brief = db.scalar(select(ReportBrief).where(ReportBrief.document_id == doc.id))
    if brief:
        brief.status, brief.error = "preparing", None
    db.commit()
    return {"status": task.status, "id": task.id}
