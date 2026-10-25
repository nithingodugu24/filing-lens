"""Credential-free baseline and optional OpenAI-compatible adapters. No provider SDK lock-in."""

import hashlib
import math
import re
import time

import httpx

from .config import get_settings


class ProviderError(ValueError):
    pass


def tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def stream_provider(endpoint, payload, on_delta, cancelled=None):
    """Real upstream SSE; never replay a partially delivered generation on failure."""
    import json
    from .answer_progress import check_cancelled

    settings = get_settings()
    if not settings.provider_api_key:
        raise ProviderError("Provider API key is missing. Configure the AI service on the server.")
    text, usage, finish, done = [], {}, None, False
    try:
        with httpx.stream(
            "POST",
            f"{settings.provider_base_url.rstrip('/')}/{endpoint}",
            json={**payload, "stream": True, "stream_options": {"include_usage": True}},
            headers={"Authorization": f"Bearer {settings.provider_api_key}"},
            timeout=settings.provider_timeout,
        ) as response:
            if response.status_code >= 400:
                reason = {
                    401: "The AI service rejected the API key.",
                    429: "The AI service rate limit or quota was reached.",
                }.get(response.status_code, "Check the AI model, service availability and streaming support.")
                raise ProviderError(f"AI stream failed ({response.status_code}). {reason}")
            for line in response.iter_lines():
                check_cancelled(cancelled)
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                event = json.loads(data)
                if event.get("error"):
                    raise ProviderError("The AI service interrupted the answer. Please try again.")
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices", []):
                    if choice.get("index", 0) != 0:
                        continue
                    delta = choice.get("delta", {}).get("content") or ""
                    if not isinstance(delta, str):
                        raise ValueError()
                    if delta:
                        text.append(delta)
                        on_delta(delta)
                    finish = choice.get("finish_reason") or finish
            check_cancelled(cancelled)
    except httpx.TimeoutException:
        raise ProviderError("The AI stream timed out. Please try again.") from None
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise ProviderError(
            "The AI connection was interrupted or returned an invalid stream. Please try again."
        ) from None
    if finish == "length":
        raise ProviderError("The AI answer reached its length limit. Ask a more specific question.")
    if not done and finish is None:
        raise ProviderError("The AI stream stopped before the answer finished. Please try again.")
    return "".join(text), usage


def fingerprint():
    s = get_settings()
    return f"{s.embedding_provider}:{s.embedding_model}:{s.embedding_dimensions}"


def request_provider(endpoint, payload):
    s = get_settings()
    if not s.provider_api_key:
        raise ProviderError("Provider API key is missing. Use the offline demo or configure credentials.")
    for attempt in range(3):
        try:
            response = httpx.post(
                f"{s.provider_base_url.rstrip('/')}/{endpoint}",
                json=payload,
                headers={"Authorization": f"Bearer {s.provider_api_key}"},
                timeout=s.provider_timeout,
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    time.sleep(0.5 * 2**attempt)
                    continue
            if response.status_code >= 400:
                reason = {
                    400: "The model rejected the request settings.",
                    401: "The AI service rejected the API key.",
                    402: "The AI account needs credits or billing access.",
                    403: "The API key does not have access to this model.",
                    404: "The AI endpoint or selected model was not found.",
                    429: "The AI service rate limit or quota was reached. Try again later.",
                }.get(response.status_code, "The AI service is temporarily unavailable.")
                raise ProviderError(f"Provider request failed ({response.status_code}). {reason}")
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            if attempt == 2:
                raise ProviderError("Provider timed out after three attempts.") from None
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError):
            raise ProviderError(
                "Provider request failed. Check credentials, model and provider status."
            ) from None
    raise ProviderError("Provider is unavailable.")


def embed(texts: list[str]):
    s = get_settings()
    if s.embedding_provider == "sentence-transformer":
        from .semantic import semantic_embed

        return semantic_embed(texts), {}
    if s.embedding_provider == "local":
        vectors = []
        for text in texts:
            vector = [0.0] * s.embedding_dimensions
            for token in tokens(text):
                h = hashlib.sha256(token.encode()).digest()
                vector[int.from_bytes(h[:4], "big") % len(vector)] += 1 if h[4] % 2 else -1
            norm = math.sqrt(sum(x * x for x in vector)) or 1
            vectors.append([x / norm for x in vector])
        return vectors, {}
    if s.embedding_provider != "openai":
        raise ProviderError("Unknown embedding provider. Choose local, sentence-transformer or openai.")
    result = request_provider(
        "embeddings", {"model": s.embedding_model, "input": texts, "dimensions": s.embedding_dimensions}
    )
    try:
        vectors = [row["embedding"] for row in sorted(result["data"], key=lambda x: x["index"])]
        if len(vectors) != len(texts) or any(len(v) != s.embedding_dimensions for v in vectors):
            raise ValueError()
        if any(not math.isfinite(x) for v in vectors for x in v):
            raise ValueError()
        return vectors, result.get("usage", {})
    except (KeyError, TypeError, ValueError):
        raise ProviderError(
            "Provider returned incompatible embeddings. Check model and dimensions."
        ) from None
