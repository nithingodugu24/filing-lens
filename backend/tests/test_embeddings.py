import math
from unittest.mock import Mock

import pytest

from app.config import get_settings
from app.providers import ProviderError, embed, fingerprint


def test_semantic_dimensions_and_normalisation(monkeypatch):
    from app import semantic

    encoder = Mock()
    encoder.get_sentence_embedding_dimension.return_value = 384
    encoder.encode.return_value = [[float(i + 1) for i in range(384)]]
    monkeypatch.setattr(semantic, "load_encoder", lambda _: encoder)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "sentence-transformer")
    monkeypatch.setenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "128")
    get_settings.cache_clear()
    vectors, _ = embed(["Revenue grew"])
    assert len(vectors[0]) == 128
    assert math.isclose(sum(x * x for x in vectors[0]), 1)
    assert fingerprint() == "sentence-transformer:all-MiniLM-L6-v2:128"
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "768")
    get_settings.cache_clear()
    with pytest.raises(ProviderError, match="384 dimensions"):
        embed(["test"])


def test_model_changes_fingerprint(monkeypatch):
    original = fingerprint()
    monkeypatch.setenv("EMBEDDING_MODEL", "ProsusAI/finbert")
    get_settings.cache_clear()
    assert fingerprint() != original


def test_model_load_error_is_actionable(monkeypatch):
    from app import semantic

    monkeypatch.setenv("EMBEDDING_PROVIDER", "sentence-transformer")
    get_settings.cache_clear()
    monkeypatch.setattr(semantic, "load_encoder", Mock(side_effect=ProviderError("Install [ml]")))
    with pytest.raises(ProviderError, match="Install"):
        embed(["Revenue"])
