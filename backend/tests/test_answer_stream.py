import asyncio
import json
import time
from contextlib import contextmanager
from threading import Event
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.answer_progress import AnswerProgress, check_cancelled
from app.answer_stream import stream_answer
from app.config import get_settings
from app.db import session_scope
from app.models import QueryRun
from app.providers import ProviderError, stream_provider


def events(response):
    return [
        (
            block.split("\n")[0][7:],
            json.loads(next(line[6:] for line in block.split("\n") if line.startswith("data: "))),
        )
        for block in response.text.split("\n\n")
        if block.startswith("event: ")
    ]


def provider_response(endpoint, payload, on_delta, cancelled=None):
    body = json.loads(payload["messages"][-1]["content"])
    quote = body["evidence"][0]["quote_options"][0]
    text = json.dumps(
        {
            "claims": [
                {
                    "text": "Management describes changes in utilisation.",
                    "quote_id": quote["quote_id"],
                    "kind": "management statement",
                }
            ],
            "abstained": False,
            "limitation": "",
            "confidence": 0.8,
        }
    )
    for i in range(0, len(text), 7):
        check_cancelled(cancelled)
        on_delta(text[i : i + 7])
    return text, {"prompt_tokens": 20, "completion_tokens": 30}


def test_partial_json_becomes_readable_text_with_split_escapes():
    output = []
    progress = AnswerProgress(lambda kind, data: output.append((kind, data)))
    first = 'Revenue in ₹ crore. A "quoted" phrase.\nNext line. 🌏'
    raw = json.dumps({"claims": [{"text": first, "quote_id": "S1Q1"}, {"text": "Second finding."}]})
    for char in raw:
        progress.feed(char, force=True)
    rendered = ""
    for kind, data in output:
        rendered = rendered + data["text"] if kind == "delta" else data["text"]
    # Normalize surrogate pairs introduced by a split escaped Unicode codepoint.
    assert rendered.encode("utf-16", "surrogatepass").decode("utf-16") == first + "\n\nSecond finding."
    assert len(output) > 10


def test_upstream_stream_preserves_deltas_usage_and_end_marker(monkeypatch):
    settings = get_settings()
    settings.provider_api_key = "private-stream-key"
    data = "\n".join(
        [
            "data: " + json.dumps({"choices": [{"delta": {"content": "first"}, "index": 0}]}),
            "",
            "data: " + json.dumps({"choices": [{"delta": {"content": " second"}, "finish_reason": "stop"}]}),
            "",
            "data: " + json.dumps({"choices": [], "usage": {"completion_tokens": 2}}),
            "",
            "data: [DONE]",
            "",
        ]
    )

    def handle(request):
        assert json.loads(request.content)["stream"] is True
        assert request.headers["authorization"] == "Bearer private-stream-key"
        return httpx.Response(200, text=data)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        monkeypatch.setattr("app.providers.httpx.stream", client.stream)
        deltas = []
        text, usage = stream_provider("chat/completions", {}, deltas.append)
    assert deltas == ["first", " second"] and text == "first second" and usage["completion_tokens"] == 2


@pytest.mark.parametrize(
    "status,body",
    [(401, "private-stream-key"), (200, 'data: {"choices":[{"delta":{"content":"unfinished"}}]}\n\n')],
)
def test_failed_or_truncated_upstream_does_not_return_success(monkeypatch, status, body):
    get_settings().provider_api_key = "private-stream-key"
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, text=body))
    ) as client:
        monkeypatch.setattr("app.providers.httpx.stream", client.stream)
        with pytest.raises(ProviderError) as error:
            stream_provider("chat/completions", {}, lambda text: None)
    assert "private-stream-key" not in str(error.value)


def test_streamed_answer_checks_citations_and_saves_final_result(client, corpus, monkeypatch):
    settings = get_settings()
    settings.answer_provider = "openai"
    settings.answer_model = "test-stream"
    monkeypatch.setattr("app.answers.stream_provider", provider_response)
    result = client.post(
        "/api/questions",
        json={"question": "What affected operating margin?", "filters": {"synthetic": True}},
        headers={"Accept": "text/event-stream"},
    )
    assert result.status_code == 200 and result.headers["x-accel-buffering"] == "no"
    frames = events(result)
    assert any(kind == "delta" for kind, _ in frames)
    final = frames[-1][1]
    assert frames[-1][0] == "done" and not final["abstained"]
    assert final["usage"]["generation"]["completion_tokens"] == 30
    assert final["claims"][0]["supporting_quote"] in next(
        e["text"] for e in final["evidence"] if e["id"] == final["claims"][0]["citation_ids"][0]
    )
    assert client.get("/api/history").json()[0]["id"] == final["run_id"]


def test_invalid_streamed_quote_is_discarded_without_history(client, corpus, monkeypatch):
    settings = get_settings()
    settings.answer_provider = "openai"
    settings.answer_model = "test-stream"

    def invalid(endpoint, payload, on_delta, cancelled=None):
        text = json.dumps(
            {
                "claims": [{"text": "Unverified draft text.", "quote_id": "invented"}],
                "abstained": False,
                "limitation": "",
                "confidence": 0.9,
            }
        )
        on_delta(text)
        return text, {}

    monkeypatch.setattr("app.answers.stream_provider", invalid)
    before = corpus.scalar(select(func.count()).select_from(QueryRun))
    result = client.post(
        "/api/questions",
        json={"question": "What affected operating margin?", "filters": {"synthetic": True}},
        headers={"Accept": "text/event-stream"},
    )
    frames = events(result)
    assert frames[-1][0] == "error" and not any(kind == "done" for kind, _ in frames)
    assert corpus.scalar(select(func.count()).select_from(QueryRun)) == before


def test_streamed_conversation_preserves_turn_order(client, corpus, monkeypatch):
    settings = get_settings()
    settings.answer_provider = "openai"
    settings.answer_model = "test-stream"
    histories = []

    def generated(endpoint, payload, on_delta, cancelled=None):
        histories.append(json.loads(payload["messages"][-1]["content"])["conversation_context_untrusted"])
        return provider_response(endpoint, payload, on_delta, cancelled)

    monkeypatch.setattr("app.answers.stream_provider", generated)
    sid = str(uuid4())
    for q in ["What affected operating margin?", "Why did it change?"]:
        response = client.post(
            "/api/conversations",
            json={"session_id": sid, "question": q, "filters": {"synthetic": True}},
            headers={"Accept": "text/event-stream"},
        )
        assert events(response)[-1][0] == "done"
    assert histories[0] == [] and [m["role"] for m in histories[1]] == ["user", "assistant"]
    assert len(client.get("/api/conversations/" + sid).json()) == 4


def test_disconnect_rolls_back_in_progress_answer(db, monkeypatch):
    from app import answer_stream

    finished = Event()

    @contextmanager
    def scoped():
        try:
            with session_scope() as session:
                yield session
        finally:
            finished.set()

    monkeypatch.setattr(answer_stream, "session_scope", scoped)

    def operation(session, emit, cancelled):
        session.add(
            QueryRun(configuration={}, citation_ids=[], latency_ms=0, usage={}, question="must not persist")
        )
        session.flush()
        emit("delta", {"text": "A provisional answer"})
        while True:
            check_cancelled(cancelled)
            time.sleep(0.005)

    async def exercise():
        response = stream_answer(operation, {})
        iterator = response.body_iterator
        assert "connected" in await anext(iterator)
        assert "event: delta" in await asyncio.wait_for(anext(iterator), 2)
        assert not finished.is_set()  # preview is delivered before work completes
        await iterator.aclose()
        assert await asyncio.to_thread(finished.wait, 2)

    asyncio.run(exercise())
    assert db.scalar(select(func.count()).select_from(QueryRun)) == 0


def test_streaming_request_still_requires_authentication(client):
    get_settings().jwt_secret_key = "test-secret-for-authentication-only-1234567890"
    result = client.post(
        "/api/questions", json={"question": "What is this report?"}, headers={"Accept": "text/event-stream"}
    )
    assert result.status_code == 401


def test_streamed_owner_scope_is_preserved(client, corpus):
    settings = get_settings()
    settings.jwt_secret_key = "test-secret-for-authentication-only-1234567890"
    for email in ["admin-stream@example.test", "reader-stream@example.test"]:
        registration = client.post(
            "/api/auth/register",
            json={"email": email, "password": "test-long-password", "full_name": "Stream Reader"},
        )
        assert registration.status_code == 201
    headers = {
        "Authorization": "Bearer " + registration.json()["access_token"],
        "Accept": "text/event-stream",
    }
    response = client.post(
        "/api/questions",
        json={"question": "What affected operating margin?", "filters": {"synthetic": True}},
        headers=headers,
    )
    final = events(response)[-1]
    assert final[0] == "done" and final[1]["evidence"] == [] and final[1]["abstained"]


def test_gemini_uses_real_stream_iterator(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    from app.gemini import gemini_generate

    get_settings().gemini_api_key = "private-gemini-test-key"

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def generate_content_stream(self, **kwargs):
            yield SimpleNamespace(text="first", usage_metadata=None)
            yield SimpleNamespace(
                text=" second", usage_metadata=SimpleNamespace(prompt_token_count=2, candidates_token_count=3)
            )

    monkeypatch.setattr(genai, "Client", FakeClient)
    deltas = []
    text, usage = gemini_generate("system", "question", [], on_delta=deltas.append)
    assert text == "first second" and deltas == ["first", " second"] and usage["completion_tokens"] == 3
