"""Small invented fixtures. These figures and statements are NOT real disclosures."""
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy import select

from .ingestion import enqueue, run_one
from .models import Document, Fact
from .schemas import DocumentMetadata


FIXTURES = [
    {"company": "TCS", "quarter": "Q1 FY26", "start": "2025-04-01", "end": "2025-06-30",
     "published": "2025-07-10", "revenue": "64000", "margin": "24.0",
     "commentary": "Management stated that operating margin was affected by annual salary increases and investment in training. Cost discipline partly offset these pressures.",
     "detail": "Management discussed demand for cloud migration. Revenue from cloud services was not separately disclosed."},
    {"company": "TCS", "quarter": "Q2 FY26", "start": "2025-07-01", "end": "2025-09-30",
     "published": "2025-10-10", "revenue": "65600", "margin": "25.0",
     "commentary": "Management stated that operating margin improved due to better utilisation and lower subcontractor costs. Salary headwinds moderated compared with the previous quarter.",
     "detail": "Management discussed European banking demand and contract renewals. No segment forecast was provided."},
    {"company": "Infosys", "quarter": "Q1 FY26", "start": "2025-04-01", "end": "2025-06-30",
     "published": "2025-07-23", "revenue": "42000", "margin": "20.0",
     "commentary": "Management stated that operating margin reflected project ramp-up costs and higher travel costs. Automation provided a partial offset.",
     "detail": "Management discussed large deal execution. No standalone financial metrics are supplied in this fixture."},
    {"company": "Infosys", "quarter": "Q2 FY26", "start": "2025-07-01", "end": "2025-09-30",
     "published": "2025-10-16", "revenue": "43680", "margin": "21.5",
     "commentary": "Management stated that operating margin improved because of automation and a favourable project mix. Travel costs remained elevated.",
     "detail": "Conflicting draft commentary: one draft says discretionary demand improved, while another draft says discretionary demand weakened. These drafts cannot establish the direction of demand."},
]


def make_pdf(item):
    out = BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(out, pagesize=A4)
    story = [Paragraph("SYNTHETIC DEMO - NOT A REAL DISCLOSURE", styles["Heading2"]),
             Paragraph(f"{item['company']} | {item['quarter']}", styles["Title"]),
             Paragraph("Quarterly results | Consolidated | Invented training data", styles["Normal"]), Spacer(1, 30)]
    rows = [["Metric", "Value", "Currency", "Units"],
            ["Revenue", item["revenue"], "INR", "crore"],
            ["Operating margin", item["margin"], "PCT", "percent"]]
    table = Table(rows, colWidths=[180, 90, 90, 90])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.grey),
                              ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6efe9")),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
                              ("TOPPADDING", (0, 0), (-1, -1), 15)]))
    story += [table, Spacer(1, 24), Paragraph("Figures are invented for software testing. Do not use for investment decisions.", styles["Normal"]),
              PageBreak(), Paragraph("SYNTHETIC DEMO - Management commentary", styles["Heading2"]),
              Paragraph(item["commentary"], styles["Normal"]), Spacer(1, 20),
              Paragraph(item["detail"], styles["Normal"])]
    doc.build(story)
    return out.getvalue()


def seed_demo(db):
    if db.scalar(select(Document.id).where(Document.synthetic.is_(True))):
        return {"message": "Synthetic demo is already loaded."}
    for item in FIXTURES:
        meta = DocumentMetadata(company=item["company"], title=f"{item['company']} {item['quarter']} · Synthetic results",
                                document_type="quarterly_results", period_start=date.fromisoformat(item["start"]),
                                period_end=date.fromisoformat(item["end"]), publication_date=date.fromisoformat(item["published"]),
                                currency="INR", units="crore", basis="consolidated")
        enqueue(db, make_pdf(item), meta, synthetic=True)
    db.commit()
    return {"message": "Four synthetic PDFs queued. Start the worker to index them."}


def verify_demo_facts(db):
    documents = db.scalars(select(Document).where(Document.synthetic.is_(True), Document.status == "indexed")).all()
    for document in documents:
        item = next(x for x in FIXTURES if x["company"] == document.company and x["end"] == str(document.period_end))
        for fact in db.scalars(select(Fact).where(Fact.document_id == document.id)):
            expected = item["revenue"] if fact.metric == "revenue" else item["margin"]
            if fact.value == expected:
                fact.verified = True
                fact.review_note = "Verified against invented fixture specification in app/demo.py. Synthetic only."


if __name__ == "__main__":
    from .db import init_db, session_scope
    init_db()
    with session_scope() as db:
        print(seed_demo(db))
    while run_one():
        pass
    with session_scope() as db:
        verify_demo_facts(db)
    print("Synthetic demo ready.")
