"""Small local routes for orientation/help; never invent financial answers."""

import re
from sqlalchemy import func, select

from .models import Chunk, Document, Page
from .retrieval import content_tokens, filtered_statement

OVERVIEW_QUESTIONS = {
    "what is this",
    "whats this",
    "what s this",
    "what s this report",
    "whats this report",
    "what is it",
    "what is this about",
    "what is this report",
    "what is this document",
    "what is this file",
    "what are these reports",
    "what am i looking at",
    "explain this",
    "explain this report",
    "explain this document",
    "tell me about this report",
    "tell me about this document",
    "describe this report",
    "give me an overview",
    "give me an overview of this report",
    "overview of this report",
}
HELP_QUESTIONS = {
    "help",
    "help me",
    "hi",
    "hello",
    "hey",
    "what can you do",
    "how do i use this",
    "how does this work",
    "how do i use filinglens",
    "what is filinglens",
}
SUGGESTIONS = [
    "What is this report?",
    "What did management say about operating margin?",
    "What is the company's business model?",
]
REPORT_TYPES = {
    "annual_report": "annual report",
    "quarterly_results": "quarterly results",
    "presentation": "investor presentation",
    "transcript": "earnings-call transcript",
}


def question_kind(question):
    text = re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()
    text = re.sub(r"^(?:(?:please|can you|could you|would you)\s+)+", "", text).strip()
    if text in OVERVIEW_QUESTIONS:
        return "report_overview"
    if text in HELP_QUESTIONS:
        return "help"
    if re.fullmatch(r"(?:hi+|hey+|hello+)(?: there| filinglens)?|how are you", text):
        return "help"
    if not content_tokens(question):
        return "clarification"
    return "answer"


def context_answer(db, request, kind):
    result = {
        "summary": "",
        "report_overviews": [],
        "suggestions": SUGGESTIONS,
        "claims": [],
        "evidence": [],
        "calculations": [],
        "abstained": False,
        "limitation": "",
    }
    if kind == "help":
        result["summary"] = (
            "FilingLens helps you read company reports. Upload a PDF, ask about the business or financial commentary, "
            "then open the source page beside a result. You can also compare two checked figures in Compare numbers. "
            "Offline mode reads the selected reports and copies relevant passages."
        )
        return result
    if kind == "clarification":
        result.update(
            summary="What would you like to understand? You can ask what the report is, what management said, or how a specific financial figure changed.",
            abstained=True,
        )
        return result

    result["suggestions"] = [
        "What did management say about operating margin?",
        "What is the company's business model?",
        "What does the report say about revenue?",
    ]

    documents = filtered_statement(request.filters).with_only_columns(Document).distinct()
    total = db.scalar(select(func.count()).select_from(documents.subquery()))
    selected = db.scalars(
        documents.order_by(Document.company, Document.period_end.desc(), Document.id).limit(request.k)
    ).all()
    for doc in selected:
        chunk = db.scalar(
            select(Chunk)
            .where(Chunk.document_id == doc.id, Chunk.kind == "passage")
            .order_by(Chunk.page_index, Chunk.id)
            .limit(1)
        )
        if chunk is None:
            continue
        page = db.get(Page, f"{doc.id}:p{chunk.page_index}")
        result["report_overviews"].append(
            {
                "document_id": doc.id,
                "title": doc.title,
                "company": doc.company,
                "document_type": doc.document_type,
                "period_start": str(doc.period_start),
                "period_end": str(doc.period_end),
                "page_count": doc.page_count,
                "synthetic": doc.synthetic,
                "citation_id": chunk.id,
            }
        )
        result["evidence"].append(
            {
                "id": chunk.id,
                "document_id": doc.id,
                "title": doc.title,
                "company": doc.company,
                "document_type": doc.document_type,
                "period_start": str(doc.period_start),
                "period_end": str(doc.period_end),
                "publication_date": str(doc.publication_date) if doc.publication_date else None,
                "basis": doc.basis,
                "page_index": chunk.page_index,
                "printed_label": page.printed_label if page else None,
                "kind": chunk.kind,
                "text": chunk.text,
                "score": None,
                "synthetic": doc.synthetic,
                "source_url": doc.source_url,
            }
        )
        result["claims"].append(
            {
                "text": chunk.text,
                "supporting_quote": chunk.text,
                "citation_ids": [chunk.id],
                "kind": "source excerpt",
            }
        )
    if not selected or not result["report_overviews"]:
        result.update(
            summary="No ready report matches your current selection. Choose a different company or period, or wait for your uploaded PDF to finish processing.",
            abstained=True,
        )
    elif total == 1:
        doc = selected[0]
        start, end = (
            doc.period_start.strftime("%d %B %Y").lstrip("0"),
            doc.period_end.strftime("%d %B %Y").lstrip("0"),
        )
        result["summary"] = (
            f"This is {doc.company}'s {REPORT_TYPES.get(doc.document_type, 'report')}, covering {start} to {end}. "
            f"It has {doc.page_count} pages. You can open the report below or ask a more specific question."
        )
        if doc.synthetic:
            result["summary"] += " This is a made-up sample, not a real company disclosure."
    else:
        result["summary"] = (
            f"You have {total} reports selected. Showing {len(result['report_overviews'])} report overviews below. "
            "Choose a company or period above if you want to focus on one report."
        )
    result["limitation"] = (
        "Company and reporting dates come from the saved report details. Open the PDF to verify them."
    )
    return result
