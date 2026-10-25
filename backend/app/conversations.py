from uuid import UUID
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .answers import answer
from .db import get_db
from .models import ConversationHistory, now
from .schemas import SearchRequest, AnswerResponse

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


class ConversationRequest(SearchRequest):
    session_id: UUID


@router.post("", response_model=AnswerResponse)
def converse(request: ConversationRequest, connection: Request, db: Session = Depends(get_db)):
    if "text/event-stream" in connection.headers.get("accept", ""):
        from .answer_stream import stream_answer

        owner = dict(db.info)
        db.rollback()
        return stream_answer(
            lambda session, emit, cancelled: run_conversation(request, session, emit, cancelled), owner
        )
    response = run_conversation(request, db)
    db.commit()
    return response


def run_conversation(request, db, on_event=None, cancelled=None):
    session_id = str(request.session_id)
    # Serialise turns for a session on the primary PostgreSQL deployment.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        import hashlib

        lock = int.from_bytes(hashlib.sha256(session_id.encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": lock})
    previous = list(
        reversed(
            db.scalars(
                select(ConversationHistory)
                .where(ConversationHistory.session_id == session_id)
                .order_by(ConversationHistory.created_at.desc(), ConversationHistory.id.desc())
                .limit(5)
            ).all()
        )
    )
    filters = request.filters.model_dump(mode="json")
    if previous and previous[-1].filters != filters:
        raise HTTPException(409, "The selected reports changed. Start a new conversation.")
    history = [{"role": m.role, "content": m.content[:3000]} for m in previous]
    query = SearchRequest(**request.model_dump(exclude={"session_id"}))
    # Short follow-ups inherit the recent topic for retrieval. Previous model statements are never evidence.
    if previous and any(
        word in request.question.lower().split() for word in ["it", "that", "those", "they", "this", "and"]
    ):
        topic = next((m.content for m in reversed(previous) if m.role == "user"), "")
        query = query.model_copy(
            update={"question": (request.question + " (Previous question: " + topic + ")")[:2000]}
        )
    response = answer(
        db, query, history=history, **({"on_event": on_event, "cancelled": cancelled} if on_event else {})
    )
    count = db.scalar(
        select(func.count())
        .select_from(ConversationHistory)
        .where(ConversationHistory.session_id == session_id, ConversationHistory.role == "user")
    )
    response.update(session_id=session_id, turn_number=count + 1)
    turn_time = now()
    db.add(
        ConversationHistory(
            session_id=session_id,
            role="user",
            created_at=turn_time,
            content=request.question,
            evidence_ids=[],
            filters=filters,
            user_id=db.info.get("user_id"),
        )
    )
    db.add(
        ConversationHistory(
            session_id=session_id,
            role="assistant",
            created_at=turn_time + timedelta(microseconds=1),
            content=response.get("summary")
            or " ".join(c["text"] for c in response["claims"])
            or response["limitation"],
            evidence_ids=[e["id"] for e in response["evidence"]],
            response=response,
            filters=filters,
            user_id=db.info.get("user_id"),
        )
    )
    return response


@router.get("/{session_id}", response_model=list[dict])
def conversation_history(session_id: UUID, db: Session = Depends(get_db)):
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "evidence_ids": m.evidence_ids,
            "created_at": m.created_at,
            "response": m.response,
        }
        for m in db.scalars(
            select(ConversationHistory)
            .where(ConversationHistory.session_id == str(session_id))
            .order_by(ConversationHistory.created_at, ConversationHistory.id)
        )
    ]
