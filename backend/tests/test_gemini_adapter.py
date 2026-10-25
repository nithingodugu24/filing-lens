from types import SimpleNamespace

from app.config import get_settings
from app.gemini import gemini_generate


def test_gemini_adapter_timeout_and_rate_limit_retry(monkeypatch):
    from google import genai
    from google.genai.errors import APIError
    from app import gemini

    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    get_settings.cache_clear()
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["http_options"].timeout == 30000
            self.models = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def generate_content(self, **kwargs):
            calls.append(kwargs)
            if len(calls) < 3:
                raise APIError(429, {"error": {"message": "rate limited", "code": 429}})
            return SimpleNamespace(
                text='{"claims":[],"abstained":true,"limitation":"Insufficient evidence"}',
                usage_metadata=None,
            )

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setattr(gemini.time, "sleep", lambda _: None)
    text, usage = gemini_generate("system", "question", [{"id": "source", "text": "evidence"}])
    assert len(calls) == 3 and "claims" in text and usage == {}
