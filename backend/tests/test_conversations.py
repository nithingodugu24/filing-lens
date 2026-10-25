import json
from uuid import uuid4

from app.config import get_settings


def test_conversation_keeps_turns_and_rejects_changed_sources(client, corpus):
    session = str(uuid4())
    payload = {
        "session_id": session,
        "question": "What affected operating margin?",
        "filters": {"synthetic": True},
        "mode": "keyword",
    }
    first = client.post("/api/conversations", json=payload)
    assert first.status_code == 200
    assert first.json()["turn_number"] == 1
    assert (
        client.post("/api/conversations", json={**payload, "question": "Why did it change?"}).json()[
            "turn_number"
        ]
        == 2
    )
    messages = client.get(f"/api/conversations/{session}").json()
    assert len(messages) == 4
    assert {m["role"] for m in messages} == {"user", "assistant"}
    assert (
        client.post("/api/conversations", json={**payload, "filters": {"synthetic": False}}).status_code
        == 409
    )


def test_gemini_citation_validation_and_low_confidence(client, corpus, monkeypatch):
    from app import gemini

    monkeypatch.setenv("ANSWER_PROVIDER", "gemini")
    get_settings.cache_clear()

    def generate(system, question, evidence, history):
        assert "Never fabricate" in system
        item = evidence[0]
        return json.dumps(
            {
                "claims": [
                    {
                        "text": "The source discusses operating margin.",
                        "citation_ids": [item["id"]],
                        "supporting_quote": item["text"][:100],
                    }
                ],
                "abstained": False,
                "limitation": "Model estimate",
                "confidence": 0.9,
            }
        ), {"prompt_tokens": 10}

    monkeypatch.setattr(gemini, "gemini_generate", generate)
    response = client.post(
        "/api/questions", json={"question": "What affected operating margin?", "filters": {"synthetic": True}}
    )
    assert response.status_code == 200
    assert response.json()["confidence"] == 0.9
    monkeypatch.setattr(
        gemini,
        "gemini_generate",
        lambda *args: (
            json.dumps({"claims": [], "abstained": True, "limitation": "uncertain", "confidence": 0.2}),
            {},
        ),
    )
    low = client.post("/api/questions", json={"question": "What affected operating margin?"}).json()
    assert low["abstained"] and not low["claims"]
    monkeypatch.setattr(
        gemini,
        "gemini_generate",
        lambda *args: (
            json.dumps(
                {
                    "claims": [
                        {
                            "text": "Invented",
                            "citation_ids": ["fake"],
                            "supporting_quote": "not a real quotation",
                        }
                    ],
                    "abstained": False,
                    "limitation": "",
                    "confidence": 0.9,
                }
            ),
            {},
        ),
    )
    assert (
        client.post("/api/questions", json={"question": "What affected operating margin?"}).status_code == 503
    )
