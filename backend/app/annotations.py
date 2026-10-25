from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis_jobs import document_or_404
from .db import get_db
from .models import Annotation, Page
from .schemas import NoteResponse

router = APIRouter(tags=["Annotations"])


class NoteRequest(BaseModel):
    page_index: int = Field(ge=0, le=999)
    selected_text: str = Field(min_length=3, max_length=4000)
    note: str = Field(min_length=1, max_length=2000)


def note_json(note):
    return {
        key: getattr(note, key)
        for key in ["id", "document_id", "page_index", "selected_text", "note", "created_at"]
    }


@router.post("/api/documents/{document_id}/annotations", status_code=201, response_model=NoteResponse)
def create_note(document_id: str, data: NoteRequest, db: Session = Depends(get_db)):
    document_or_404(db, document_id)
    page = db.scalar(select(Page).where(Page.document_id == document_id, Page.page_index == data.page_index))
    if page is None:
        raise HTTPException(404, "Page not found")
    if " ".join(data.selected_text.split()) not in " ".join(page.text.split()):
        raise HTTPException(
            422, "The selected text could not be found on this page. Select text from the report."
        )
    note = Annotation(document_id=document_id, user_id=db.info.get("user_id"), **data.model_dump())
    db.add(note)
    db.flush()
    db.commit()
    return note_json(note)


@router.get("/api/documents/{document_id}/annotations", response_model=list[NoteResponse])
def notes(document_id: str, db: Session = Depends(get_db)):
    document_or_404(db, document_id)
    return [
        note_json(note)
        for note in db.scalars(
            select(Annotation)
            .where(Annotation.document_id == document_id)
            .order_by(Annotation.page_index, Annotation.created_at)
        )
    ]


@router.delete("/api/annotations/{annotation_id}", response_model=dict[str, bool])
def delete_note(annotation_id: str, db: Session = Depends(get_db)):
    note = db.get(Annotation, annotation_id)
    if note is None:
        raise HTTPException(404, "Note not found")
    document_or_404(db, note.document_id)
    db.delete(note)
    db.commit()
    return {"deleted": True}
