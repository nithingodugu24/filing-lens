from datetime import date

import pytest
from sqlalchemy import select

from app.answers import answer
from app.config import Settings, get_settings
from app.financial_metrics import extract_financial_metrics, source_number
from app.models import Chunk, Document, ExtractedTable, Fact, Page, LibraryReport, ReportBrief
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
    db.flush()
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
            embedding=[0.0] * 256,
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


def test_workspace_and_source_metric_api(client, db, report):
    from app.financial_metrics import extract_financial_metrics

    extract_financial_metrics(db, report)
    db.commit()
    result = client.get("/api/documents/real/workspace").json()
    assert result["coverage"] == {"metric_count": 6, "period_count": 2}
    assert len(result["financials"]) == 12
    assert result["brief"]["status"] == "preparing"
    assert client.get("/api/documents/real/workspace?basis=invalid").status_code == 422
    answer = client.post(
        "/api/questions",
        json={
            "question": "what is the total income in crores this year",
            "filters": {"document_ids": ["real"]},
        },
    ).json()
    assert answer["metric_answers"][0]["value"] == "271423"
    unavailable = client.post(
        "/api/questions", json={"question": "total income FY2030", "filters": {"document_ids": ["real"]}}
    ).json()
    assert unavailable["abstained"] and unavailable["claims"] == []
    assert unavailable["usage"]["generation"] == {}
    assert (
        client.get("/api/history?document_id=real").json()[0]["response"]["metric_answers"][0]["value"]
        == "271423"
    )
    assert client.delete("/api/history/" + answer["run_id"]).status_code == 200
    assert client.get("/api/history?document_id=real").json() == []


def test_library_copy_is_owned_and_private_uploads_are_not_templates(client, db, report, monkeypatch):
    import app.library as library
    from app.financial_metrics import extract_financial_metrics

    report.source_url = "https://issuer.example/report.pdf"
    extract_financial_metrics(db, report)
    db.add(LibraryReport(id="test-issuer", document_id=report.id))
    db.add(
        ReportBrief(
            document_id=report.id,
            status="ready",
            content={"claims": [], "evidence": [{"document_id": report.id}], "run_id": "private-run"},
        )
    )
    db.commit()
    monkeypatch.setattr(
        library,
        "CATALOG",
        [
            {
                "id": "test-issuer",
                "company": report.company,
                "year": 2026,
                "pages": 35,
                "sha256": report.sha256,
                "url": report.source_url,
            }
        ],
    )
    get_settings().jwt_secret_key = "test-secret-for-authentication-only-1234567890"

    def register(email):
        r = client.post(
            "/api/auth/register",
            json={"email": email, "password": "test-long-password", "full_name": "Library reader"},
        )
        assert r.status_code == 201
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    register("admin@example.test")
    headers = register("reader@example.test")
    assert client.get("/api/documents/real/workspace", headers=headers).status_code == 404
    assert client.get("/api/library", headers=headers).json()[0]["document_id"] is None
    assert client.post("/api/library/private-upload/open", json={}, headers=headers).status_code == 404
    result = client.post("/api/library/test-issuer/open", json={}, headers=headers)
    assert result.status_code == 200, result.text
    copy_id = result.json()["document_id"]
    assert copy_id != "real"
    workspace = client.get(f"/api/documents/{copy_id}/workspace", headers=headers).json()
    assert all(
        m["document_id"] == copy_id and m["citation_id"].startswith(copy_id) for m in workspace["financials"]
    )
    assert all(e["document_id"] == copy_id for e in workspace["brief"]["content"]["evidence"])
    assert client.get("/api/history?document_id=real", headers=headers).status_code == 404
    assert (
        client.post("/api/library/test-issuer/open", json={}, headers=headers).json()["document_id"]
        == copy_id
    )


def test_production_requires_deliberate_setup():
    import pytest

    settings = Settings(_env_file=None, app_env="production")
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        settings.validate_deployment()
    valid = dict(
        app_env="production",
        jwt_secret_key="test-random-enough-ABcDeFgHijklmnOP0123456789-uvwxyz",
        database_url="postgresql+psycopg://operator:private-secret@db/app",
        cors_origins="https://reports.example.com",
        answer_provider="openai",
        provider_api_key="test-only",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    Settings(_env_file=None, **valid).validate_deployment()
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(_env_file=None, **{**valid, "cors_origins": "*"}).validate_deployment()
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(_env_file=None, **{**valid, "database_url": "sqlite:///x.db"}).validate_deployment()


def test_public_first_signup_is_not_admin(client, db, report):
    settings = get_settings()
    settings.jwt_secret_key = "test-secret-for-authentication-only-1234567890"
    settings.app_env = "production"
    db.commit()
    response = client.post(
        "/api/auth/register",
        json={"email": "first@example.test", "password": "test-long-password", "full_name": "First reader"},
    )
    assert response.status_code == 201 and response.json()["user"]["role"] == "analyst"
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert client.get("/api/documents", headers=headers).json() == []


def test_million_to_crore_keeps_previous_period_units_consistent(db, report):
    page = db.get(Page, "real:p34")
    page.text = page.text.replace("INR crore", "INR million")
    extract_financial_metrics(db, report)
    result = answer(db, SearchRequest(question="total income in crores this year"))
    card = result["metric_answers"][0]
    assert card["value"] == "27142.3"
    assert card["previous_value"] == "25928.6"
    assert card["units"] == "crore"
    assert card["change_percent"] == "4.68"


def test_borderless_pdf_ignores_note_and_growth_columns():
    import pymupdf
    from types import SimpleNamespace
    from app.financial_layout import financial_layout
    from app.financial_metrics import table_candidates

    pdf = pymupdf.open()
    page = pdf.new_page(width=600, height=600)
    page.insert_text((20, 22), "Software test fixture (INR crore)")
    page.insert_text((210, 48), "Standalone")
    page.insert_text((420, 48), "Consolidated")

    def right(text, edge, y):
        page.insert_text((edge - pymupdf.get_text_length(text, fontsize=10), y), text, fontsize=10)

    for edge, year in [(200, "2026"), (270, "2025"), (410, "2026"), (480, "2025")]:
        right(year, edge, 75)
    rows = [
        ("Revenue from operations", ["100", "90", "200", "180"]),
        ("Other income", ["10", "9", "20", "18"]),
        ("Total income", ["110", "99", "220", "198"]),
        ("Profit before tax", ["50", "40", "100", "80"]),
        ("Tax expense", ["10", "8", "20", "16"]),
        ("Profit for the year", ["40", "32", "80", "64"]),
    ]
    for i, (label, values) in enumerate(rows):
        y = 105 + i * 24
        page.insert_text((20, y), label, fontsize=10)
        if i < 2:
            right("22", 164, y)
        for edge, value in zip([200, 270, 410, 480], values, strict=True):
            right(value, edge, y)
        right("11.1", 340, y)
    cells = financial_layout(page)
    document = SimpleNamespace(
        period_start=date(2025, 4, 1),
        period_end=date(2026, 3, 31),
        document_type="annual_report",
        currency="INR",
    )
    candidates = table_candidates(
        SimpleNamespace(cells=cells, id="fixture", page_index=0),
        SimpleNamespace(text=page.get_text(sort=True)),
        document,
    )
    assert len(candidates) == 24
    assert {str(c["value"]) for c in candidates if c["metric"] == "total_income"} == {
        "110",
        "99",
        "220",
        "198",
    }
    assert {c["basis"] for c in candidates} == {"standalone", "consolidated"}
    pdf.close()


def test_brief_export_uses_selected_basis_and_hides_internal_generation_tasks(client, db, report):
    from app.models import QueryRun

    extract_financial_metrics(db, report)
    evidence = {
        "id": "real:p34:t0",
        "document_id": report.id,
        "company": report.company,
        "title": report.title,
        "page_index": 34,
    }
    db.add(
        ReportBrief(
            document_id=report.id,
            status="ready",
            content={
                "claims": [{"text": "A sourced finding.", "citation_ids": ["real:p34:t0"]}],
                "evidence": [evidence],
                "run_id": None,
            },
        )
    )
    db.add(
        QueryRun(
            configuration={"purpose": "report_brief"},
            citation_ids=["real:p34:t0"],
            latency_ms=0,
            usage={},
            question="Private internal task prompt",
            response={"claims": [], "evidence": [evidence], "calculations": []},
        )
    )
    db.commit()
    response = client.post(
        "/api/export/report",
        json={"document_ids": [report.id], "format": "md", "include_qa": True, "basis": "consolidated"},
    )
    assert response.status_code == 200
    assert "Private internal task prompt" not in response.text
    assert response.text.count("total_income:") == 2
    assert "standalone" not in response.text
    assert "A sourced finding. [TCS, PDF page 35]" in response.text


def test_management_explanation_is_not_replaced_by_a_number(db, report):
    from app.metric_answers import resolve_metric_answer, unsupported_metric_answer

    extract_financial_metrics(db, report)
    request = SearchRequest(question="What explanation did management give for changes in revenue?")
    assert resolve_metric_answer(db, request) is None
    assert unsupported_metric_answer(db, request) is None
