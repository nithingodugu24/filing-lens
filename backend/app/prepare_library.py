"""Operator command: prepare pinned issuer PDFs, preserving existing uploads and reviews."""

import hashlib
from datetime import date

import httpx
import pymupdf
from sqlalchemy import select

from .analysis_jobs import enqueue_analysis
from .config import get_settings
from .db import init_db, session_scope
from .financial_layout import financial_layout
from .financial_metrics import extract_financial_metrics
from .ingestion import enqueue, split_text
from .library import CATALOG
from .models import Chunk, ExtractedTable, LibraryReport, ReportBrief
from .providers import embed, fingerprint
from .schemas import DocumentMetadata


def backfill_layout(db, doc):
    """Only adds coordinate-derived financial rows. Does not delete old evidence or reviews."""
    with pymupdf.open(doc.path) as pdf:
        for page in pdf:
            text = page.get_text(sort=True).lower()
            if "total income" not in text or "other income" not in text:
                continue
            table_id = f"{doc.id}:p{page.number}:t10001"
            if db.get(ExtractedTable, table_id):
                continue
            cells = financial_layout(page)
            if not cells:
                continue
            db.add(ExtractedTable(id=table_id, document_id=doc.id, page_index=page.number, cells=cells))
            rendered = "\n".join(" | ".join(row) for row in cells)
            parts = list(split_text(rendered))
            vectors, _ = embed(parts)
            for i, (part, vector) in enumerate(zip(parts, vectors, strict=True)):
                db.add(
                    Chunk(
                        id=table_id if i == 0 else f"{table_id}:c{i}",
                        document_id=doc.id,
                        page_index=page.number,
                        kind="table",
                        text=part,
                        embedding=vector,
                        embedding_config=fingerprint(),
                    )
                )
    db.flush()
    return extract_financial_metrics(db, doc)


def main():
    init_db()
    cache = get_settings().storage_dir.parent / "issuer-library"
    cache.mkdir(parents=True, exist_ok=True)
    for item in CATALOG:
        path = cache / (item["id"] + ".pdf")
        if not path.exists():
            print(f"Downloading {item['id']} from the issuer", flush=True)
            response = httpx.get(
                item["url"],
                timeout=120,
                follow_redirects=True,
                headers={"User-Agent": "FilingLens/0.2 (financial-report-reader)"},
            )
            response.raise_for_status()
            path.write_bytes(response.content)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(
                f"Issuer PDF changed for {item['id']}. Review and update the manifest before importing."
            )
        with session_scope() as db:
            doc, _ = enqueue(
                db,
                content,
                DocumentMetadata(
                    company=item["company"],
                    title=f"{item['company']} Annual Report {item['year'] - 1}–{str(item['year'])[-2:]}",
                    document_type="annual_report",
                    period_start=date(item["year"] - 1, 4, 1),
                    period_end=date(item["year"], 3, 31),
                    currency="INR",
                    basis="consolidated",
                    source_url=item["url"],
                ),
            )
            record = db.get(LibraryReport, item["id"])
            if record is None:
                db.add(LibraryReport(id=item["id"], document_id=doc.id))
            else:
                record.document_id = doc.id
            if doc.status == "indexed":
                result = backfill_layout(db, doc)
                brief = db.scalar(select(ReportBrief).where(ReportBrief.document_id == doc.id))
                if not brief or brief.version != "report-brief-v3":
                    enqueue_analysis(db, doc.id, "brief")
                print(item["id"], doc.status, result, flush=True)
            else:
                print(item["id"], doc.status, "Worker will prepare figures and brief", flush=True)


if __name__ == "__main__":
    main()
