"""spaCy entities and conservative, sentence-level co-occurrence relationships."""

import re
from functools import lru_cache

from sqlalchemy import delete, select

from .models import Entity, Page, Relationship
from .providers import ProviderError


@lru_cache(maxsize=1)
def load_ner_model():
    try:
        import spacy

        nlp = spacy.load("en_core_web_sm")
        ruler = nlp.add_pipe("entity_ruler", before="ner")
        ruler.add_patterns(
            [
                {
                    "label": "METRIC",
                    "pattern": [{"LOWER": {"IN": ["revenue", "ebitda", "ebit", "margin", "profit"]}}],
                },
                {"label": "DATE", "pattern": [{"TEXT": {"REGEX": "^FY[0-9]{2,4}$"}}]},
                {
                    "label": "MONEY",
                    "pattern": [{"LIKE_NUM": True}, {"LOWER": {"IN": ["crore", "crores", "lakh", "lakhs"]}}],
                },
            ]
        )
        return nlp
    except ImportError:
        raise ProviderError("Entity extraction needs spaCy from the optional [ml] packages.") from None
    except OSError:
        raise ProviderError(
            "Install the English model with: python -m spacy download en_core_web_sm"
        ) from None


class FinancialNER:
    def __init__(self, nlp=None):
        self.nlp = nlp or load_ner_model()

    def extract(self, text):
        labels = {
            "ORG": "COMPANY",
            "PERSON": "PERSON",
            "MONEY": "MONEY",
            "DATE": "DATE",
            "PERCENT": "PERCENTAGE",
            "METRIC": "METRIC",
        }
        doc = self.nlp(text)
        return [
            {
                "text": e.text,
                "entity_type": labels[e.label_],
                "start": e.start_char,
                "end": e.end_char,
                "sentence": e.sent.text,
                "sentence_start": e.sent.start_char,
            }
            for e in doc.ents
            if e.label_ in labels and len(e.text.strip()) > 1
        ]


def extract_entities(db, document_id, recognizer=None):
    recognizer = recognizer or FinancialNER()
    db.execute(delete(Relationship).where(Relationship.document_id == document_id))
    db.execute(delete(Entity).where(Entity.document_id == document_id))
    entities, sentences = {}, {}
    for page in db.scalars(select(Page).where(Page.document_id == document_id).order_by(Page.page_index)):
        for item in recognizer.extract(page.text):
            normalized = re.sub(r"\s+", " ", item["text"]).strip().casefold()
            key = (item["entity_type"], normalized)
            mention = {
                "page_index": page.page_index,
                "start": item["start"],
                "end": item["end"],
                "sentence": item["sentence"][:1000],
            }
            if key not in entities:
                entities[key] = Entity(
                    document_id=document_id,
                    entity_type=item["entity_type"],
                    text=item["text"],
                    normalized_text=normalized,
                    page_index=page.page_index,
                    count=0,
                    details={"mentions": []},
                )
                db.add(entities[key])
            entity = entities[key]
            entity.count += 1
            entity.details = {"mentions": [*entity.details["mentions"], mention]}
            sentences.setdefault((page.page_index, item["sentence_start"]), set()).add(key)
    db.flush()
    pairs = set()
    for keys in sentences.values():
        keys = sorted(keys)[:12]
        for i, source in enumerate(keys):
            for target in keys[i + 1 :]:
                pair = (entities[source].id, entities[target].id)
                if pair not in pairs:
                    pairs.add(pair)
                    db.add(
                        Relationship(
                            document_id=document_id,
                            source_entity_id=pair[0],
                            target_entity_id=pair[1],
                            relationship_type="mentioned_together",
                        )
                    )
    return len(entities)
