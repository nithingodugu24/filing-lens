from unittest.mock import Mock
from sqlalchemy import select

from app.models import Document, Entity, Relationship
from app.ner import extract_entities


def test_ner_deduplicates_mentions_and_labels_edges(corpus):
    doc = corpus.scalar(select(Document))
    recognizer = Mock()
    recognizer.extract.return_value = [
        {
            "text": "TCS",
            "entity_type": "COMPANY",
            "start": 0,
            "end": 3,
            "sentence": "TCS revenue increased.",
            "sentence_start": 0,
        },
        {
            "text": "revenue",
            "entity_type": "METRIC",
            "start": 4,
            "end": 11,
            "sentence": "TCS revenue increased.",
            "sentence_start": 0,
        },
    ]
    assert extract_entities(corpus, doc.id, recognizer) == 2
    corpus.flush()
    entities = corpus.scalars(select(Entity).where(Entity.document_id == doc.id)).all()
    assert all(e.count == 2 for e in entities)
    assert {e.entity_type for e in entities} == {"COMPANY", "METRIC"}
    assert (
        corpus.scalar(select(Relationship).where(Relationship.document_id == doc.id)).relationship_type
        == "mentioned_together"
    )
    extract_entities(corpus, doc.id, recognizer)
    corpus.flush()
    assert len(corpus.scalars(select(Entity).where(Entity.document_id == doc.id)).all()) == 2
