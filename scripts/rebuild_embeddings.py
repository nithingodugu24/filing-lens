"""Rebuild vectors with the configured provider, preserving pages, facts, reviews and notes."""

import argparse
import json
import time

from sqlalchemy import bindparam, select

from app.db import init_db, session_scope
from app.models import Chunk, Document
from app.providers import embed, fingerprint


def rebuild(document_id=None):
    started = time.perf_counter()
    init_db()
    with session_scope() as db:
        query = select(Document.id).where(Document.status == "indexed")
        if document_id:
            query = query.where(Document.id == document_id)
        ids = list(db.scalars(query))
    total = 0
    for doc_id in ids:
        with session_scope() as db:
            rows = db.execute(
                select(Chunk.id, Chunk.text)
                .where(Chunk.document_id == doc_id)
                .order_by(Chunk.id)
            ).all()
            statement = (
                Chunk.__table__.update()
                .where(Chunk.id == bindparam("chunk_key"))
                .values(
                    embedding=bindparam("vector_value"), embedding_config=fingerprint()
                )
            )
            for start in range(0, len(rows), 32):
                batch = rows[start : start + 32]
                vectors, _ = embed([row.text for row in batch])
                # Core updates avoid numpy array equality when changing vector dimensions.
                db.execute(
                    statement,
                    [
                        {"chunk_key": row.id, "vector_value": vector}
                        for row, vector in zip(batch, vectors, strict=True)
                    ],
                )
                print(
                    json.dumps(
                        {
                            "document_id": doc_id,
                            "completed": start + len(batch),
                            "total": len(rows),
                        }
                    ),
                    flush=True,
                )
            total += len(rows)
    return {
        "documents": len(ids),
        "chunks": total,
        "embedding": fingerprint(),
        "seconds": round(time.perf_counter() - started, 2),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id")
    args = parser.parse_args()
    print(json.dumps(rebuild(args.document_id)))
