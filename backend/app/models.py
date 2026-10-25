from datetime import date, datetime, timezone
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid():
    return uuid4().hex


def now():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(240))
    company: Mapped[str] = mapped_column(String(100), index=True)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    publication_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    units: Mapped[str | None] = mapped_column(String(20))
    basis: Mapped[str] = mapped_column(String(20))
    synthetic: Mapped[bool] = mapped_column(default=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    dedup_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    warning: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)


class Page(Base):
    __tablename__ = "pages"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_index: Mapped[int] = mapped_column(Integer)  # zero based, distinct from printed labels
    printed_label: Mapped[str | None] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_index: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20), default="passage")
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON().with_variant(Vector(), "postgresql"))
    embedding_config: Mapped[str] = mapped_column(String(240))


class ExtractedTable(Base):
    __tablename__ = "extracted_tables"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_index: Mapped[int] = mapped_column(Integer)
    cells: Mapped[list] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Fact(Base):
    __tablename__ = "facts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"))
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(String(80))  # Decimal serialised without floating point loss
    currency: Mapped[str] = mapped_column(String(8))
    units: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    basis: Mapped[str] = mapped_column(String(20))
    verified: Mapped[bool] = mapped_column(default=False)
    review_note: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[str] = mapped_column(String(20), default="original")
    verification_method: Mapped[str] = mapped_column(String(24), default="manual")
    source_details: Mapped[dict | None] = mapped_column(JSON)


class ReportBrief(Base):
    __tablename__ = "report_briefs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="preparing")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(40), default="report-brief-v1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QueryRun(Base):
    __tablename__ = "query_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    configuration: Mapped[dict] = mapped_column(JSON)
    citation_ids: Mapped[list] = mapped_column(JSON)
    latency_ms: Mapped[float] = mapped_column(Float)
    usage: Mapped[dict] = mapped_column(JSON)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    question: Mapped[str | None] = mapped_column(Text)
    response: Mapped[dict | None] = mapped_column(JSON)


class WorkerState(Base):
    __tablename__ = "worker_state"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    is_active: Mapped[bool] = mapped_column(default=True)


class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    response: Mapped[dict | None] = mapped_column(JSON)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Annotation(Base):
    __tablename__ = "annotations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    page_index: Mapped[int] = mapped_column(Integer)
    selected_text: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SentimentResult(Base):
    __tablename__ = "sentiment_results"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    overall_sentiment: Mapped[str] = mapped_column(String(16))
    overall_confidence: Mapped[float] = mapped_column(Float)
    section_results: Mapped[list] = mapped_column(JSON)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(24))
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    page_index: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(default=1)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Relationship(Base):
    __tablename__ = "relationships"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    relationship_type: Mapped[str] = mapped_column(String(64))
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))


class StatusEvent(Base):
    __tablename__ = "status_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
