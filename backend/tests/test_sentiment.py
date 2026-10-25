from unittest.mock import Mock

import pytest

from app.sentiment import SentimentAnalyzer, analyze_document


def test_token_chunks_respect_model_limit():
    classifier = Mock()
    classifier.tokenizer.encode.return_value = list(range(1100))
    classifier.tokenizer.num_special_tokens_to_add.return_value = 2
    classifier.tokenizer.decode.side_effect = lambda piece, **kwargs: str(len(piece))
    classifier.return_value = [
        [
            {"label": "positive", "score": 0.8},
            {"label": "neutral", "score": 0.15},
            {"label": "negative", "score": 0.05},
        ]
    ] * 3
    result = SentimentAnalyzer(classifier).analyze("Long commentary")
    assert classifier.call_args.args[0] == ["510", "510", "80"]
    assert result["chunk_count"] == 3
    assert result["sentiment"] == "positive"
    assert result["confidence"] == pytest.approx(0.8)


def test_no_commentary_does_not_invent_neutral(corpus):
    from app.models import Document
    from sqlalchemy import select

    doc = corpus.scalar(select(Document))
    with pytest.raises(ValueError, match="No management"):
        analyze_document(corpus, doc.id, analyzer=Mock())
