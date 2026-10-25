from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str = Field(min_length=1, max_length=100, pattern=r"^[\w .&()-]+$")
    title: str = Field(min_length=1, max_length=240)
    document_type: Literal["quarterly_results", "annual_report", "presentation", "transcript"]
    period_start: date
    period_end: date
    publication_date: date | None = None
    source_url: HttpUrl | None = None
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    units: Literal["unit", "lakh", "crore", "million", "billion"] | None = None
    basis: Literal["consolidated", "standalone"]

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_start > self.period_end:
            raise ValueError("Reporting period start must be before end")
        return self


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companies: list[str] = Field(default_factory=list, max_length=20)
    document_types: list[str] = Field(default_factory=list, max_length=4)
    period_ends: list[date] = Field(default_factory=list, max_length=16)
    publication_cutoff: date | None = None
    synthetic: bool | None = None


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2000, examples=["What affected operating margin?"])
    mode: Literal["keyword", "vector", "hybrid"] = "keyword"
    filters: Filters = Field(default_factory=Filters)
    k: int = Field(default=6, ge=1, le=20)


class CompareRequest(BaseModel):
    fact_ids: list[str] = Field(min_length=2, max_length=2)
    operation: Literal["percentage_change", "percentage_points", "basis_points", "difference"]


class FactReview(BaseModel):
    verified: bool
    note: str = Field(min_length=12, max_length=500)
    revision: Literal["original", "restated"] | None = None


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ErrorResponse(BaseModel):
    detail: str | list[dict]
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(ApiModel):
    database: str
    worker: str
    answer_provider: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    max_upload_mb: int
    max_pdf_pages: int
    mode: str


class DocumentResponse(DocumentMetadata):
    model_config = ConfigDict(extra="allow")
    id: str
    synthetic: bool
    sha256: str
    status: str
    warning: str | None
    page_count: int
    created_at: datetime
    job: dict | None


DocumentListResponse = list[DocumentResponse]


class UploadResponse(BaseModel):
    document: DocumentResponse
    duplicate: bool


class FactResponse(ApiModel):
    id: str
    document_id: str
    chunk_id: str
    metric: str
    value: str
    currency: str
    units: str
    verified: bool
    company: str
    page_index: int
    source_text: str
    synthetic: bool
    title: str
    period_start: date
    period_end: date
    basis: str
    revision: str
    review_note: str | None


FactListResponse = list[FactResponse]


class EvidenceResponse(ApiModel):
    id: str
    document_id: str
    title: str
    company: str
    page_index: int
    text: str
    synthetic: bool


class ClaimResponse(BaseModel):
    text: str
    citation_ids: list[str]
    supporting_quote: str
    kind: str


class AnswerResponse(ApiModel):
    run_id: str
    mode: str
    answer_kind: str
    summary: str
    report_overviews: list[dict]
    suggestions: list[str]
    claims: list[ClaimResponse]
    evidence: list[EvidenceResponse]
    calculations: list[dict]
    abstained: bool
    limitation: str
    configuration: dict
    latency_ms: float
    usage: dict
    cost_usd: float | None
    confidence: float | None


class AnalyticsResponse(BaseModel):
    summary: dict[str, int]
    revenue_trends: list[dict]
    margin_trends: list[dict]
    company_profiles: list[dict]
    excluded_ambiguous_facts: int


class PageResponse(BaseModel):
    page_index: int
    printed_label: str | None
    text: str
    tables: list[dict]


class SearchResponse(BaseModel):
    evidence: list[EvidenceResponse]
    usage: dict
    mode: str


class ActionResponse(ApiModel):
    """Action-specific JSON fields described by the endpoint."""


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime
    user: UserResponse


class NoteResponse(BaseModel):
    id: str
    document_id: str
    page_index: int
    selected_text: str
    note: str
    created_at: datetime


class TaskResponse(BaseModel):
    id: str
    status: str
