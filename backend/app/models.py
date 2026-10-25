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
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    warning: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


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


class QueryRun(Base):
    __tablename__ = "query_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    configuration: Mapped[dict] = mapped_column(JSON)
    citation_ids: Mapped[list] = mapped_column(JSON)
    latency_ms: Mapped[float] = mapped_column(Float)
    usage: Mapped[dict] = mapped_column(JSON)
    cost_usd: Mapped[float | None] = mapped_column(Float)


class WorkerState(Base):
    __tablename__ = "worker_state"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
