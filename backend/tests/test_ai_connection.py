import json

import httpx
import pytest

from app.answers import generation_sources, parse_generated_answer, validate_claims
from app.config import get_settings
from app.providers import ProviderError, request_provider


def test_model_selects_exact_source_text_without_retyping_it():
    evidence = [
        {"id": "real-chunk", "text": "Revenue increased. The report uses a purpose-driven delivery model."}
    ]
    sources, quotes = generation_sources(evidence)
    quote_id = sources[0]["quote_options"][0]["quote_id"]
    result = parse_generated_answer(
        json.dumps(
            {
                "claims": [
                    {
                        "text": "The report describes its delivery model.",
                        "quote_id": quote_id,
                        "supporting_quote": "incorrectly reformatted by model",
                        "citation_ids": ["model-typo"],
                    }
                ],
                "abstained": False,
                "limitation": "",
                "confidence": 0.8,
            }
        ),
        quotes,
    )
    claim = result.claims[0].model_dump()
    assert claim["supporting_quote"] == evidence[0]["text"]
    assert claim["citation_ids"] == ["real-chunk"]
    validate_claims([claim], evidence)
    with pytest.raises(ProviderError, match="unknown source"):
        parse_generated_answer(json.dumps({"claims": [{"quote_id": "invented"}]}), quotes)


def test_ready_shows_service_configuration_without_secrets(client, monkeypatch):
    settings = get_settings()
    assert client.get("/api/ready").json()["answer_status"] == "offline"
    settings.answer_provider = "openai"
    settings.answer_model = "test-model"
    settings.provider_base_url = "https://api.river.ai/v1"
    settings.provider_api_key = "private-test-key"
    result = client.get("/api/ready")
    assert result.json()["answer_service"] == "River AI"
    assert result.json()["answer_status"] == "configured"
    assert "private-test-key" not in result.text
    settings.answer_model = ""
    assert client.get("/api/ready").json()["answer_status"] == "needs_setup"


def test_greeting_variant_and_model_clarification(client, corpus, monkeypatch):
    result = client.post("/api/questions", json={"question": "hii", "filters": {"synthetic": True}}).json()
    assert result["answer_kind"] == "help" and not result["abstained"]
    settings = get_settings()
    settings.answer_provider, settings.answer_model = "openai", "test-model"

    def respond(endpoint, payload):
        body = json.loads(payload["messages"][-1]["content"])
        assert body["conversation_context_untrusted"] == []
        assert body["evidence"][0]["quote_options"]
        assert payload["max_tokens"] == 2048
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "claims": [],
                                "abstained": True,
                                "limitation": "Do you mean total income or other income?",
                                "confidence": 0.4,
                                "needs_clarification": True,
                            }
                        )
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    monkeypatch.setattr("app.answers.request_provider", respond)
    answer = client.post(
        "/api/questions", json={"question": "income revenue", "filters": {"synthetic": True}}
    ).json()
    assert answer["abstained"] and answer["limitation"] == "Do you mean total income or other income?"
    assert answer["answer_kind"] == "clarification"


def test_provider_errors_explain_authentication_failure_without_echoing_key(monkeypatch):
    get_settings().provider_api_key = "private-test-key"
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(401))
    with pytest.raises(ProviderError, match="rejected the API key") as error:
        request_provider("chat/completions", {})
    assert "private-test-key" not in str(error.value)


def test_compatible_ai_provider_receives_conversation_context(client, corpus, monkeypatch):
    from uuid import uuid4

    settings = get_settings()
    settings.answer_provider, settings.answer_model = "openai", "test-model"
    histories = []

    def respond(endpoint, payload):
        body = json.loads(payload["messages"][-1]["content"])
        histories.append(body["conversation_context_untrusted"])
        quote = body["evidence"][0]["quote_options"][0]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "claims": [
                                    {
                                        "text": "The selected report discusses operating margin.",
                                        "quote_id": quote["quote_id"],
                                    }
                                ],
                                "abstained": False,
                                "limitation": "",
                                "confidence": 0.8,
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("app.answers.request_provider", respond)
    payload = {
        "session_id": str(uuid4()),
        "question": "What affected operating margin?",
        "filters": {"synthetic": True},
    }
    assert client.post("/api/conversations", json=payload).status_code == 200
    assert (
        client.post("/api/conversations", json={**payload, "question": "Why did it change?"}).status_code
        == 200
    )
    assert histories[0] == []
    assert [message["role"] for message in histories[1]] == ["user", "assistant"]
