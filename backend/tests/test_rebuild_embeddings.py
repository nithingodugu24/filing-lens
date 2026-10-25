import sys
from pathlib import Path
from sqlalchemy import select
from app.models import Chunk, Fact

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import rebuild_embeddings  # noqa:E402


def test_dimension_change_preserves_reviewed_facts(corpus, monkeypatch):
    before = {f.id: (f.value, f.verified, f.review_note) for f in corpus.scalars(select(Fact))}
    monkeypatch.setattr(rebuild_embeddings, "embed", lambda texts: ([[0.125] * 64 for _ in texts], {}))
    monkeypatch.setattr(rebuild_embeddings, "fingerprint", lambda: "test:64")
    result = rebuild_embeddings.rebuild()
    assert result["chunks"] > 0
    corpus.expire_all()
    assert all(len(c.embedding) == 64 for c in corpus.scalars(select(Chunk)))
    assert {f.id: (f.value, f.verified, f.review_note) for f in corpus.scalars(select(Fact))} == before
