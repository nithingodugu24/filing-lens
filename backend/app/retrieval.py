import math
from collections import Counter

from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, func, literal_column, select

from .models import Chunk, Document, Page
from .providers import ProviderError, embed, fingerprint, tokens

# Natural-language glue and company names should not make an unsupported question answerable.
STOP = set("a an the of to in on for and or is are was were be been has have had do does did what which who how why "
           "when where this that these those it its with from by as at between than selected disclosures disclosure "
           "company companies quarter quarters reporting period periods tcs infosys fy26 fy2026 q1 q2 q3 q4 "
           "compare comparison change changed give given get tell me about can you please stated statement "
           "management explanation explain commentary result results report reports financial latest current".split())


def content_tokens(question):
    aliases = {"margins": "margin", "revenues": "revenue", "utilization": "utilisation"}
    return [aliases.get(t, t) for t in tokens(question) if t not in STOP and not t.isdigit()]


def filtered_statement(filters):
    stmt = select(Chunk, Document).join(Document, Chunk.document_id == Document.id).where(Document.status == "indexed")
    if filters.companies:
        stmt = stmt.where(Document.company.in_(filters.companies))
    if filters.document_types:
        stmt = stmt.where(Document.document_type.in_(filters.document_types))
    if filters.period_ends:
        stmt = stmt.where(Document.period_end.in_(filters.period_ends))
    if filters.publication_cutoff:
        # Unknown publication dates cannot establish what was knowable at the cutoff.
        stmt = stmt.where(Document.publication_date.is_not(None), Document.publication_date <= filters.publication_cutoff)
    if filters.synthetic is not None:
        stmt = stmt.where(Document.synthetic == filters.synthetic)
    return stmt


def retrieve(db, request):
    stmt = filtered_statement(request.filters)
    terms = content_tokens(request.question)
    embedding_usage = {}
    if not terms:
        return [], embedding_usage
    postgres = db.bind.dialect.name == "postgresql"
    lexical, vector = [], []
    if request.mode in {"keyword", "hybrid"}:
        if postgres:
            tsquery = func.to_tsquery("english", " | ".join(terms))
            ranking = func.ts_rank_cd(literal_column("chunks.search_vector"), tsquery)
            lexical = [(c, d, float(score)) for c, d, score in db.execute(
                stmt.add_columns(ranking).where(literal_column("chunks.search_vector").op("@@")(tsquery))
                .order_by(ranking.desc(), Chunk.id).limit(100))]
        else:
            # SQLite is an explicitly labelled convenience fallback; primary deployment uses PostgreSQL FTS.
            for chunk, document in db.execute(stmt):
                counts = Counter(tokens(chunk.text))
                score = sum(1 + math.log(counts[t]) for t in terms if counts[t]) / math.sqrt(max(len(counts), 1))
                if score:
                    lexical.append((chunk, document, score))
            lexical.sort(key=lambda x: (-x[2], x[0].id))
            lexical = lexical[:100]
    if request.mode in {"vector", "hybrid"}:
        incompatible = db.scalar(select(func.count()).select_from(stmt.where(Chunk.embedding_config != fingerprint()).subquery()))
        if incompatible:
            raise ProviderError("Embedding configuration changed. Reindex documents before vector or hybrid search.")
        query, embedding_usage = embed([request.question])
        if postgres:
            distance = cast(Chunk.embedding, Vector()).cosine_distance(query[0])
            vector = [(c, d, 1-float(dist)) for c, d, dist in db.execute(
                stmt.add_columns(distance).order_by(distance, Chunk.id).limit(100))]
        else:
            vector = [(c, d, sum(a*b for a, b in zip(query[0], c.embedding, strict=True))) for c, d in db.execute(stmt)]
            vector.sort(key=lambda x: (-x[2], x[0].id))
            vector = vector[:100]
    if request.mode == "hybrid":
        fused = {}
        for ranking in [lexical, vector]:
            for rank, (chunk, document, _) in enumerate(ranking, 1):
                old = fused.get(chunk.id, (chunk, document, 0.0))
                fused[chunk.id] = (chunk, document, old[2] + 1/(60+rank))
        ranked = sorted(fused.values(), key=lambda x: (-x[2], x[0].id))
    else:
        ranked = lexical if request.mode == "keyword" else vector
    # One evidence item per PDF page avoids passage/table duplicates consuming the context window.
    evidence, seen = [], set()
    for chunk, document, score in ranked:
        key = (document.id, chunk.page_index)
        if key in seen:
            continue
        seen.add(key)
        page = db.get(Page, f"{document.id}:p{chunk.page_index}")
        evidence.append({"id": chunk.id, "document_id": document.id, "title": document.title,
                         "company": document.company, "document_type": document.document_type,
                         "period_start": str(document.period_start), "period_end": str(document.period_end),
                         "publication_date": str(document.publication_date) if document.publication_date else None,
                         "basis": document.basis, "page_index": chunk.page_index,
                         "printed_label": page.printed_label if page else None,
                         "kind": chunk.kind, "text": chunk.text, "score": round(score, 6),
                         "synthetic": document.synthetic, "source_url": document.source_url})
        if len(evidence) == request.k:
            break
    return evidence, embedding_usage
