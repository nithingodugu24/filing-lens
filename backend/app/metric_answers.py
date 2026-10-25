"""Financial questions resolve typed source rows before generic text retrieval."""

import re
from decimal import Decimal

from sqlalchemy import select

from .financial_metrics import LABELS
from .finance import SCALE, calculate
from .models import Chunk, Document, Fact, Page
from .retrieval import filtered_statement


def requested_metric(question):
    text = question.casefold()
    if re.search(r"\b(?:total\s+income|total\s+revenue\s+and\s+other\s+income)\b", text) and not re.search(
        r"total\s+income\s+tax", text
    ):
        return "total_income"
    if re.search(r"\b(?:revenue|turnover|net\s+sales)\b", text):
        return "revenue"
    if re.search(r"\b(?:net\s+profit|profit\s+after\s+tax|profit\s+for\s+the\s+year)\b", text):
        return "net_profit"
    if re.search(r"\b(?:other\s+income)\b", text):
        return "other_income"
    if re.search(r"\b(?:operating\s+margin)\b", text):
        return "operating_margin"
    return None


def fiscal_year(question):
    match = re.search(r"\b(?:fy\s*)?(20\d{2})\s*[-–/]\s*(20\d{2}|\d{2})(?!\d)", question, re.I)
    if match:
        return int(match[2]) if len(match[2]) == 4 else 2000 + int(match[2])
    match = re.search(r"\bfy\s*(20\d{2}|\d{2})\b", question, re.I)
    if match:
        return int(match[1]) if len(match[1]) == 4 else 2000 + int(match[1])
    match = re.search(r"\b(20\d{2})\b", question)
    return int(match[1]) if match else None


def fact_evidence(db, fact, doc, chunk):
    page = db.get(Page, f"{doc.id}:p{chunk.page_index}")
    return {
        "id": chunk.id,
        "document_id": doc.id,
        "title": doc.title,
        "company": doc.company,
        "page_index": chunk.page_index,
        "text": chunk.text,
        "synthetic": doc.synthetic,
        "kind": chunk.kind,
        "period_start": str(fact.period_start),
        "period_end": str(fact.period_end),
        "basis": fact.basis,
        "printed_label": page.printed_label if page else None,
        "source_url": doc.source_url,
    }


def metric_card(fact, doc, chunk, previous=None, target_units=None):
    units = target_units or fact.units
    value = Decimal(fact.value)
    if units != fact.units:
        value = value * SCALE[fact.units] / SCALE[units]
    change = None
    if (
        previous is not None
        and Decimal(previous.value) != 0
        and (previous.currency, previous.units, previous.basis, previous.revision)
        == (fact.currency, fact.units, fact.basis, fact.revision)
    ):
        change = str(
            ((Decimal(fact.value) - Decimal(previous.value)) / abs(Decimal(previous.value)) * 100).quantize(
                Decimal(".01")
            )
        )
    return {
        "fact_id": fact.id,
        "document_id": doc.id,
        "company": doc.company,
        "metric": fact.metric,
        "label": (fact.source_details or {}).get("source_label", LABELS.get(fact.metric, fact.metric)),
        "value": str(value),
        "currency": fact.currency,
        "units": units,
        "period_start": str(fact.period_start),
        "period_end": str(fact.period_end),
        "basis": fact.basis,
        "revision": fact.revision,
        "source_page": chunk.page_index + 1,
        "citation_id": chunk.id,
        "verification_method": fact.verification_method,
        "previous_value": str(Decimal(previous.value) * SCALE[previous.units] / SCALE[units])
        if previous and previous.units in SCALE and units in SCALE
        else previous.value
        if previous
        else None,
        "previous_period_end": str(previous.period_end) if previous else None,
        "change_percent": change,
        "source_details": fact.source_details or {},
        "synthetic": doc.synthetic,
    }


def resolve_metric_answer(db, request):
    metric = requested_metric(request.question)
    text = request.question.casefold()
    if not metric or re.search(
        r"\b(?:why|drivers?|explain|forecast|predict|next|expect|estimated?|cloud|segment|region)\b", text
    ):
        return None
    change_requested = bool(
        re.search(r"\b(?:growth|change|difference|increased?|decreased?|basis points?)\b", text)
    )
    allowed = filtered_statement(request.filters).with_only_columns(Document.id).distinct()
    rows = db.execute(
        select(Fact, Document, Chunk)
        .join(Document, Document.id == Fact.document_id)
        .join(Chunk, Chunk.id == Fact.chunk_id)
        .where(Fact.verified.is_(True), Fact.metric == metric, Document.id.in_(allowed))
    ).all()
    if not rows:
        return None
    mentioned = {d.company for _, d, _ in rows if re.search(r"\b" + re.escape(d.company) + r"\b", text, re.I)}
    if mentioned:
        rows = [row for row in rows if row[1].company in mentioned]
    explicit_basis = (
        "standalone" if "standalone" in text else "consolidated" if "consolidated" in text else None
    )
    rows = [row for row in rows if row[0].basis == (explicit_basis or row[1].basis)]
    year = fiscal_year(text)
    previous_year = bool(re.search(r"\b(?:last|previous|prior)\s+year\b", text))
    companies = sorted({d.company for _, d, _ in rows})
    if not companies or len(companies) > 5:
        return None
    cards, evidence, claims, calculations = [], {}, [], []
    for company in companies:
        group = [row for row in rows if row[1].company == company]
        years = sorted({f.period_end.year for f, _, _ in group}, reverse=True)
        target = year or (
            years[1] if previous_year and len(years) > 1 else years[0] if not previous_year else None
        )
        candidates = [row for row in group if row[0].period_end.year == target]
        if not candidates:
            continue
        if (
            len(
                {
                    (f.value, f.currency, f.units, f.basis, f.revision, f.period_start, f.period_end)
                    for f, _, _ in candidates
                }
            )
            != 1
        ):
            return None
        fact, doc, chunk = max(candidates, key=lambda row: row[1].period_end)
        if re.search(r"\bquarter\b", text) and (fact.period_end - fact.period_start).days > 300:
            return None
        prior = next(
            (
                f
                for f, d, _ in group
                if d.id == doc.id and f.period_end.year == target - 1 and f.basis == fact.basis
            ),
            None,
        )
        units = "crore" if re.search(r"\bcrores?\b", text) and fact.units != "percent" else fact.units
        if change_requested and prior is None:
            return None
        card = metric_card(fact, doc, chunk, prior, units)
        quote = (fact.source_details or {}).get("row_text")
        if not quote or quote not in chunk.text:
            continue
        cards.append(card)
        evidence[chunk.id] = fact_evidence(db, fact, doc, chunk)
        amount = card["value"]
        message = f"{doc.company}'s {card['label'].lower()} was {amount} {card['currency']} {card['units']} for {fact.period_start} to {fact.period_end} ({fact.basis})."
        if change_requested:
            operation = (
                "basis_points"
                if metric == "operating_margin" and "basis point" in text
                else "percentage_points"
                if metric == "operating_margin"
                else "difference"
                if "difference" in text
                else "percentage_change"
            )
            try:
                calculation = calculate(prior, fact, operation)
            except ValueError:
                return None
            calculation.update(company=doc.company, citation_ids=[chunk.id])
            calculations.append(calculation)
            card["requested_operation"] = operation
            message = f"{doc.company}'s {card['label'].lower()} changed by {calculation['result']} {calculation['units']} between {prior.period_end} and {fact.period_end} ({fact.basis})."
        claims.append(
            {
                "text": message,
                "citation_ids": [chunk.id],
                "supporting_quote": quote,
                "kind": "reported financial figure",
            }
        )
    if not cards:
        return None
    return {
        "claims": claims,
        "evidence": list(evidence.values()),
        "metric_answers": cards,
        "calculations": calculations,
        "abstained": False,
        "limitation": "Using the latest period covered by the selected report."
        if year is None and not previous_year
        else "Reporting period and accounting basis are shown with each figure.",
    }
