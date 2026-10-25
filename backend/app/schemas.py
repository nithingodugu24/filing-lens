from datetime import date
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
    question: str = Field(min_length=3, max_length=2000)
    mode: Literal["keyword", "vector", "hybrid"] = "keyword"
    filters: Filters = Field(default_factory=Filters)
    k: int = Field(default=6, ge=1, le=20)


class CompareRequest(BaseModel):
    fact_ids: list[str] = Field(min_length=2, max_length=2)
    operation: Literal["percentage_change", "percentage_points", "basis_points", "difference"]


class FactReview(BaseModel):
    verified: bool
    note: str = Field(min_length=12, max_length=500)
