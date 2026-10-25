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
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            if attempt == 2:
                raise ProviderError("Provider timed out after three attempts.") from None
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
