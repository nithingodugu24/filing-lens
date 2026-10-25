"""Explicitly prepared issuer reports. Private uploads are never public templates."""

import copy
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import engine, get_db
from .models import Chunk, Document, ExtractedTable, Fact, LibraryReport, Page, ReportBrief, uid

router = APIRouter(prefix="/api/library", tags=["Real report library"])
CATALOG = [
    {
        "id": "infosys-2025",
        "company": "Infosys",
        "year": 2025,
        "pages": 369,
        "sha256": "a2b9acdfbe79586ffdbe1780c4f14e5b2630743a4c81ee626f812f4c2fff1b44",
        "url": "https://www.infosys.com/investors/reports-filings/annual-report/annual/documents/infosys-ar-25.pdf",
    },
    {
        "id": "infosys-2024",
        "company": "Infosys",
        "year": 2024,
        "pages": 352,
        "sha256": "93fcc9d4e549ec623178f36ce3d420ade3b301a1e48ed90e063f167c516746ff",
        "url": "https://www.infosys.com/investors/reports-filings/annual-report/annual/documents/infosys-ar-24.pdf",
    },
    {
        "id": "wipro-2025",
        "company": "Wipro",
        "year": 2025,
        "pages": 520,
        "sha256": "3f1869fbac2da58b369bfc192bf47470b59e804e4105c1be6226c5a3edd6edaf",
        "url": "https://www.wipro.com/content/dam/nexus/en/investor/annual-reports/2024-2025/Integrated-annual-report-2024-25.pdf",
    },
    {
        "id": "wipro-2024",
        "company": "Wipro",
        "year": 2024,
        "pages": 481,
        "sha256": "4c1d713111f82550cfe28cb8d97427ed7a99af95af535d66eb8853684e2f0a38",
        "url": "https://www.wipro.com/content/dam/nexus/en/investor/annual-reports/2023-2024/integrated-annual-report-2023-24.pdf",
    },
]


def template(db, item):
    record = db.get(LibraryReport, item["id"])
    doc = db.get(Document, record.document_id) if record else None
    if doc and doc.sha256 == item["sha256"] and doc.source_url == item["url"] and not doc.synthetic:
        return doc
    return None


@router.get("")
def catalog(db: Session = Depends(get_db)):
    result = []
    # This session can read only manifest-authorised templates, never arbitrary uploads.
    with Session(engine()) as public:
        for item in CATALOG:
            doc = template(public, item)
            owned = db.scalar(select(Document).where(Document.sha256 == item["sha256"]))
            ready = bool(
                doc
                and doc.status == "indexed"
                and public.scalar(
                    select(Fact.id).where(Fact.document_id == doc.id, Fact.verified.is_(True)).limit(1)
                )
            )
            result.append(
                {
                    **{k: v for k, v in item.items() if k != "sha256"},
                    "prepared": ready,
                    "document_id": owned.id if owned else None,
                }
            )
    return result


def remap(value, old, new):
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [remap(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: remap(v, old, new) for k, v in value.items()}
    return value


@router.post("/{library_id}/open")
def open_library(library_id: str, db: Session = Depends(get_db)):
    item = next((i for i in CATALOG if i["id"] == library_id), None)
    if item is None:
        raise HTTPException(404, "Report not found")
    owner = db.info.get("user_id")
    existing = db.scalar(select(Document).where(Document.sha256 == item["sha256"], Document.user_id == owner))
    if existing:
        return {"document_id": existing.id}
    # Copies preserve tenant ownership; users do not gain access to the shared template.
    with Session(engine()) as public:
        source = template(public, item)
        if source is None or source.status != "indexed":
            raise HTTPException(409, "This issuer report is still being prepared")
        new_id = uid()
        fields = [
            "title",
            "company",
            "document_type",
            "period_start",
            "period_end",
            "publication_date",
            "source_url",
            "currency",
            "units",
            "basis",
            "synthetic",
            "sha256",
            "path",
            "status",
            "warning",
            "page_count",
        ]
        doc = Document(
            id=new_id,
            **{f: getattr(source, f) for f in fields},
            user_id=owner,
            dedup_key=hashlib.sha256(f"{owner}|{source.sha256}".encode()).hexdigest()
            if owner
            else source.sha256,
        )
        db.add(doc)
        db.flush()
        for model in [Page, ExtractedTable, Chunk, Fact, ReportBrief]:
            for row in public.scalars(select(model).where(model.document_id == source.id)):
                fields = {
                    c.name: copy.deepcopy(getattr(row, c.name))
                    for c in model.__table__.columns
                    if c.name not in {"id", "document_id"}
                }
                if model == Fact:
                    fields["chunk_id"] = remap(fields["chunk_id"], source.id, new_id)
                    fields["source_details"] = remap(fields["source_details"], source.id, new_id)
                if model == ReportBrief:
                    fields["content"] = remap(fields["content"], source.id, new_id)
                    fields["content"]["run_id"] = None
                db.add(
                    model(
                        id=remap(row.id, source.id, new_id)
                        if model in {Page, Chunk, ExtractedTable}
                        else uid(),
                        document_id=new_id,
                        **fields,
                    )
                )
            db.flush()
    db.commit()
    return {"document_id": new_id}
