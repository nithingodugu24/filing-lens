"""Optional FinBERT management-tone analysis. Tone is not investment advice."""

import re
from functools import lru_cache

from sqlalchemy import select

from .models import Page, SentimentResult
from .providers import ProviderError

HEADINGS = re.compile(
    r"management discussion|management.s discussion|MD&A|chairman.s (?:statement|message)|CEO (?:letter|message)|chief executive officer.s (?:message|letter)",
    re.I,
)


@lru_cache(maxsize=1)
def load_sentiment_model():
    try:
        from transformers import pipeline

        return pipeline("text-classification", model="ProsusAI/finbert", device=-1)
    except ImportError:
        raise ProviderError("Sentiment analysis needs the optional [ml] packages.") from None
    except Exception:
        raise ProviderError(
            "Could not load FinBERT. Check internet access and the local model cache."
        ) from None


class SentimentAnalyzer:
    def __init__(self, classifier=None):
        self.classifier = classifier or load_sentiment_model()

    def analyze(self, text):
        tokenizer = self.classifier.tokenizer
        tokens = tokenizer.encode(text, add_special_tokens=False, verbose=False)
        limit = 512 - tokenizer.num_special_tokens_to_add(pair=False)
        pieces = [tokens[start : start + limit] for start in range(0, len(tokens), limit)]
        if not pieces:
            raise ValueError("No commentary text available")
        scores = dict.fromkeys(["positive", "negative", "neutral"], 0.0)
        predictions = self.classifier(
            [tokenizer.decode(piece, skip_special_tokens=True) for piece in pieces],
            top_k=None,
            truncation=True,
            max_length=512,
            batch_size=8,
        )
        for piece, predictions_for_piece in zip(pieces, predictions, strict=True):
            for prediction in predictions_for_piece:
                scores[prediction["label"].lower()] += float(prediction["score"]) * len(piece) / len(tokens)
        label = max(scores, key=scores.get)
        return {
            "sentiment": label,
            "confidence": scores[label],
            "scores": scores,
            "token_count": len(tokens),
            "chunk_count": len(pieces),
        }


def analyze_document(db, document_id, analyzer=None):
    analyzer = analyzer or SentimentAnalyzer()
    pages = db.scalars(select(Page).where(Page.document_id == document_id).order_by(Page.page_index)).all()
    sections = []
    for page in pages:
        heading = HEADINGS.search(page.text)
        if not heading:
            continue
        text = page.text[heading.start() :]
        # Ignore contents pages: short heading listings provide no management tone.
        if len(text.split()) < 70 or len(re.findall(r"\.{3,}", text)) > 3:
            continue
        result = analyzer.analyze(text)
        sections.append(
            {
                "section": heading.group(),
                "page_index": page.page_index,
                **result,
                "key_phrases": [
                    sentence.strip()[:180]
                    for sentence in re.split(r"(?<=[.!?])\s+", text)
                    if len(sentence.split()) > 8
                ][:2],
            }
        )
    if not sections:
        raise ValueError("No management-commentary section was identified. No sentiment score was inferred.")
    total = sum(s["token_count"] for s in sections)
    scores = {
        label: sum(s["scores"][label] * s["token_count"] / total for s in sections)
        for label in ["positive", "negative", "neutral"]
    }
    label = max(scores, key=scores.get)
    stored = db.scalar(select(SentimentResult).where(SentimentResult.document_id == document_id))
    if stored is None:
        stored = SentimentResult(document_id=document_id)
        db.add(stored)
    from .models import now

    stored.overall_sentiment, stored.overall_confidence, stored.section_results, stored.analyzed_at = (
        label,
        scores[label],
        sections,
        now(),
    )
    return stored
