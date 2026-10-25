import pytest

from app.answers import validate_claims
from app.config import get_settings


@pytest.mark.parametrize(
    "question",
    ["what is this?", "What's this report?", "Please explain this report.", "Tell me about this document."],
)
def test_overview_uses_selected_report_and_real_source(client, corpus, question):
    response = client.post(
        "/api/questions",
        json={
            "question": question,
            "filters": {"companies": ["TCS"], "period_ends": ["2025-09-30"], "synthetic": True},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["answer_kind"] == "report_overview" and not result["abstained"]
    assert "TCS" in result["summary"] and "quarterly results" in result["summary"]
    assert "2 pages" in result["summary"] and "made-up sample" in result["summary"]
    assert len(result["report_overviews"]) == 1
    overview = result["report_overviews"][0]
    assert overview["period_end"] == "2025-09-30"
    assert overview["citation_id"] in {e["id"] for e in result["evidence"]}
    assert all(e["company"] == "TCS" and e["page_index"] == 0 for e in result["evidence"])
    validate_claims(result["claims"], result["evidence"])
    assert result["suggestions"] and result["run_id"]


def test_overview_respects_cutoff_and_does_not_use_excluded_documents(client, corpus):
    result = client.post(
        "/api/questions",
        json={
            "question": "What is this?",
            "filters": {
                "companies": ["TCS"],
                "period_ends": ["2025-09-30"],
                "publication_cutoff": "2025-08-01",
            },
        },
    ).json()
    assert result["abstained"] and result["report_overviews"] == [] and result["evidence"] == []
    assert "No ready report matches" in result["summary"]


def test_overview_is_available_without_provider_or_matching_embeddings(client, corpus, monkeypatch):
    settings = get_settings()
    settings.answer_provider, settings.answer_model = "openai", "not-configured"
    settings.embedding_model = "changed-config"

    def forbidden(*args, **kwargs):
        raise AssertionError("An overview must not call a model provider or vector embedder")

    monkeypatch.setattr("app.answers.request_provider", forbidden)
    monkeypatch.setattr("app.retrieval.embed", forbidden)
    result = client.post("/api/questions", json={"question": "what is this?", "mode": "vector"})
    assert result.status_code == 200, result.text
    assert result.json()["configuration"]["answer_provider"] == "local_context"
    assert result.json()["usage"] == {"embedding": {}, "generation": {}}


def test_help_and_vague_questions_are_not_report_missing_errors(client):
    help_result = client.post("/api/questions", json={"question": "What can you do?"}).json()
    assert help_result["answer_kind"] == "help" and not help_result["abstained"]
    assert "Upload a PDF" in help_result["summary"]
    vague = client.post("/api/questions", json={"question": "why?"}).json()
    assert vague["answer_kind"] == "clarification" and vague["abstained"]
    assert "What would you like to understand?" in vague["summary"]
    assert vague["suggestions"] and not vague["claims"]


def test_specific_financial_question_does_not_become_a_generic_overview(client, corpus):
    result = client.post(
        "/api/questions",
        json={"question": "What is this company's revenue growth?", "filters": {"companies": ["TCS"]}},
    ).json()
    assert result["answer_kind"] == "answer" and not result["abstained"]
    assert result["calculations"][0]["result"] == "2.5000"


def test_multiple_reports_are_not_silently_presented_as_one(client, corpus):
    result = client.post("/api/questions", json={"question": "What is this?", "k": 1}).json()
    assert "4 reports selected" in result["summary"] and "Showing 1" in result["summary"]
    assert len(result["report_overviews"]) == len(result["evidence"]) == 1
