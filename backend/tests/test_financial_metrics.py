from datetime import date

import pytest
from sqlalchemy import select

from app.answers import answer
from app.financial_metrics import extract_financial_metrics, source_number
from app.models import Chunk, Document, ExtractedTable, Fact, Page
from app.schemas import SearchRequest


@pytest.fixture
def report(db):
    doc = Document(
        id="real",
        title="Annual report",
        company="TCS",
        document_type="annual_report",
        period_start=date(2025, 4, 1),
        period_end=date(2026, 3, 31),
        basis="consolidated",
        currency="INR",
        units="crore",
        synthetic=False,
        sha256="a" * 64,
        path="test.pdf",
        status="indexed",
    )
    db.add(doc)
    cells = [
        ["Particulars", "Standalone", "", "Consolidated", ""],
        ["Year", "2026", "2025", "2026", "2025"],
        ["Revenue from operations", "2,20,938", "2,14,853", "2,67,021", "2,55,324"],
        ["Other income", "10,036", "9,642", "4,402", "3,962"],
        ["Total income", "2,30,974", "2,24,495", "2, 7 1, 423", "2,59,286"],
        ["Profit before tax", "62,806", "62,648", "65,487", "65,331"],
        ["Tax expense", "13,710", "14,591", "16,033", "16,534"],
        ["Profit for the year", "49,096", "48,057", "49,454", "48,797"],
        ["Total income tax expense", "999", "999", "999", "999"],
    ]
    text = "\n".join(" | ".join(row) for row in cells)
    db.add(
        Page(id="real:p34", document_id=doc.id, page_index=34, text="Financial results (INR crore)\n" + text)
    )
    db.add(ExtractedTable(id="real:p34:t0", document_id=doc.id, page_index=34, cells=cells))
    db.add(
        Chunk(
            id="real:p34:t0",
            document_id=doc.id,
            page_index=34,
            kind="table",
            text=text,
            embedding=[],
            embedding_config="test",
        )
    )
    db.flush()
    return doc


def test_exact_income_year_basis_and_growth(db, report):
    assert extract_financial_metrics(db, report) == {"published": 24, "conflicts": 0}
    for question, expected, basis in [
        ("what is the total income in crores this year", "271423", "consolidated"),
        ("total income last year", "259286", "consolidated"),
        ("standalone total income FY2025-26", "230974", "standalone"),
    ]:
        result = answer(db, SearchRequest(question=question, filters={"document_ids": [report.id]}))
        card = result["metric_answers"][0]
        assert result["mode"] == "financial" and not result["abstained"]
        assert (card["value"], card["basis"], card["source_page"]) == (expected, basis, 35)
        assert result["claims"][0]["supporting_quote"] in result["evidence"][0]["text"]
        assert result["usage"]["generation"] == {}
    growth = answer(db, SearchRequest(question="TCS revenue growth this year"))
    assert growth["calculations"][0]["result"] == "4.5812"
    assert "FY 2025–26" in growth["calculations"][0]["input_values"][1]["period"]["fiscal"]


def test_wrong_total_and_missing_context_are_not_published(db, report):
    table = db.get(ExtractedTable, "real:p34:t0")
    table.cells = [row if row[0] != "Total income" else [row[0], "1", "1", "1", "1"] for row in table.cells]
    db.flush()
    assert extract_financial_metrics(db, report)["published"] == 0
    assert db.scalars(select(Fact)).all() == []


def test_conflicts_revoke_automatic_facts_and_scope(db, report):
    extract_financial_metrics(db, report)
    table = db.get(ExtractedTable, "real:p34:t0")
    conflicting = [row[:] for row in table.cells]
    conflicting[2][3], conflicting[4][3] = "267022", "271424"
    db.add(ExtractedTable(id="real:p35:t0", document_id=report.id, page_index=34, cells=conflicting))
    db.flush()
    assert extract_financial_metrics(db, report)["conflicts"] == 2
    total = db.scalar(
        select(Fact).where(
            Fact.metric == "total_income", Fact.basis == "consolidated", Fact.period_end == report.period_end
        )
    )
    assert not total.verified
    from app.metric_answers import resolve_metric_answer

    assert resolve_metric_answer(db, SearchRequest(question="total income FY2026")) is None
    assert (
        resolve_metric_answer(
            db, SearchRequest(question="revenue", filters={"document_ids": ["another-user"]})
        )
        is None
    )
    assert resolve_metric_answer(db, SearchRequest(question="total income this quarter")) is None


@pytest.mark.parametrize(
    "text,expected", [("2, 7 1, 423", "271423"), ("2,7,423", None), ("(16,033)", "-16033"), ("N/A", None)]
)
def test_pdf_numbers_do_not_invent_digits(text, expected):
    value = source_number(text)
    assert (str(value) if value is not None else None) == expected
