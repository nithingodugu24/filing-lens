"""Source-row financial extraction. Column context and accounting identities gate publication."""

import re
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from .models import Chunk, ExtractedTable, Fact, Page

METRICS = {
    "revenue": {"revenue", "revenue from operations", "revenue from operation", "revenues", "net sales"},
    "other_income": {"other income", "other income, net"},
    "total_income": {"total income", "total revenue and other income"},
    "net_profit": {
        "profit for the year",
        "profit for the period",
        "net profit",
        "profit after tax",
        "profit after taxes",
        "net profit for the year",
        "net profit for the period",
    },
    "profit_before_tax": {"profit before tax", "profit before taxes"},
    "tax_expense": {"tax expense", "total tax expense", "income tax expense"},
    "operating_margin": {"operating margin", "operating margin %", "operating profit margin"},
}
LABELS = {
    "revenue": "Revenue from operations",
    "other_income": "Other income",
    "total_income": "Total income",
    "net_profit": "Profit for the year",
    "profit_before_tax": "Profit before tax",
    "tax_expense": "Tax expense",
    "operating_margin": "Operating margin",
}


def clean_label(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    text = re.sub(r"^\s*(?:\(?[ivx]+\)?[.)]?|\d+[.)])\s+", "", text)
    text = re.sub(r"^\s*(?:\([a-z]\)|[a-z][.)])\s*", "", text)
    text = re.sub(r"\s+\d[\d,\s]*$", "", text)
    text = re.sub(r"\s*\((?:[ivx+\-\s]+|[0-9+\-\s]+)\)\s*$", "", text)
    return text.strip(" :.*†")


def row_metric(row):
    for index, cell in enumerate(row[:3]):
        label = clean_label(cell)
        for metric, aliases in METRICS.items():
            if label in aliases:
                return metric, index
    return None, None


def source_number(value):
    text = str(value or "").strip()
    if not text or text.lower() in {"na", "n/a"}:
        return None
    if text.lower() in {"nil", "–", "—", "-"}:
        return Decimal(0)
    text = re.sub(r"\s+", "", text)
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    # Grouping repairs remove spacing, never add a missing digit.
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?%?", text):
        return None
    try:
        result = Decimal(text.replace(",", "").rstrip("%"))
        return -result if negative else result
    except InvalidOperation:
        return None


def header_year(text):
    text = str(text or "")
    match = re.search(r"(?:20\d{2})\s*[-–/]\s*(20\d{2}|\d{2})(?!\d)", text)
    if match:
        return int(match[1]) if len(match[1]) == 4 else 2000 + int(match[1])
    years = set(int(year) for year in re.findall(r"\b20\d{2}\b", text))
    return next(iter(years)) if len(years) == 1 else None


def column_context(headers, column, page_text, document):
    basis = None
    for row in headers:
        carried = None
        for cell in row[: column + 1]:
            label = clean_label(cell)
            if "consolidated" in label and "standalone" in label:
                return None
            if re.search(r"\bconsolidated\b", label):
                carried = "consolidated"
            elif re.search(r"\bstandalone\b", label):
                carried = "standalone"
        if carried:
            basis = carried
    if basis is None:
        # Only explicit statement titles establish a whole-page basis.
        title = page_text[:650] + " " + page_text[-300:]
        standalone = bool(re.search(r"standalone\s+(?:financial|statement)", title, re.I))
        consolidated = bool(re.search(r"consolidated\s+(?:financial|statement)", title, re.I))
        if standalone != consolidated:
            basis = "standalone" if standalone else "consolidated"
    header = " ".join(str(row[column] or "") for row in headers if column < len(row))
    year = header_year(header)
    if basis is None or year not in {document.period_end.year, document.period_end.year - 1}:
        return None
    # Annual statements only: quarterly/YTD headers require their own explicit duration mapping.
    if (
        document.document_type != "annual_report"
        or not 300 <= (document.period_end - document.period_start).days <= 370
    ):
        return None
    try:
        end = document.period_end.replace(year=year)
        start = document.period_start.replace(
            year=document.period_start.year + year - document.period_end.year
        )
    except ValueError:
        return None
    return basis, start, end, header


def table_candidates(table, page, document):
    rows = table.cells
    first = next((i for i, row in enumerate(rows) if row_metric(row)[0]), None)
    if first is None:
        return []
    headers = rows[:first]
    # A missing/ambiguous currency unit blocks automatic publication.
    units = re.findall(r"\b(crore|crores|lakh|lakhs|million|millions)\b", page.text[:1500], re.I)
    units = {u.lower().rstrip("s") for u in units}
    if len(units) != 1 or document.currency != "INR":
        return []
    unit = next(iter(units))
    contexts = {
        i: column_context(headers, i, page.text, document) for i in range(1, max(map(len, rows), default=0))
    }
    candidates = []
    for row in rows[first:]:
        metric, label_column = row_metric(row)
        if not metric:
            continue
        for column in range(label_column + 1, len(row)):
            context = contexts.get(column)
            value = source_number(row[column])
            if not context or value is None:
                continue
            basis, start, end, header = context
            candidates.append(
                {
                    "metric": metric,
                    "value": value,
                    "basis": basis,
                    "period_start": start,
                    "period_end": end,
                    "currency": "PCT" if metric == "operating_margin" else "INR",
                    "units": "percent" if metric == "operating_margin" else unit,
                    "row": row,
                    "row_text": " | ".join(str(c or "") for c in row),
                    "source_label": str(row[label_column]),
                    "column": column,
                    "header": header,
                    "table_id": table.id,
                    "page_index": table.page_index,
                }
            )
    by_column = {}
    for candidate in candidates:
        by_column.setdefault(candidate["column"], {})[candidate["metric"]] = candidate
    published = []
    for group in by_column.values():
        income = all(metric in group for metric in ["revenue", "other_income", "total_income"])
        income_ok = income and abs(
            group["revenue"]["value"] + group["other_income"]["value"] - group["total_income"]["value"]
        ) <= Decimal("1")
        if not income_ok:
            continue
        for metric, candidate in group.items():
            checks = [
                "explicit_annual_period",
                "explicit_accounting_basis",
                "explicit_currency_unit",
                "literal_table_cell",
                "revenue_plus_other_income_matches_total",
            ]
            if metric in {"net_profit", "profit_before_tax", "tax_expense"} and all(
                m in group for m in ["net_profit", "profit_before_tax", "tax_expense"]
            ):
                if abs(
                    group["profit_before_tax"]["value"]
                    - group["tax_expense"]["value"]
                    - group["net_profit"]["value"]
                ) > Decimal("1"):
                    continue
                checks.append("profit_before_tax_minus_tax_matches_profit")
            candidate["checks"] = checks
            published.append(candidate)
    return published


def extract_financial_metrics(db, document):
    if document.synthetic:
        return {"published": 0, "conflicts": 0}
    pages = {p.page_index: p for p in db.scalars(select(Page).where(Page.document_id == document.id))}
    chunks = db.scalars(select(Chunk).where(Chunk.document_id == document.id, Chunk.kind == "table")).all()
    candidates = []
    for table in db.scalars(
        select(ExtractedTable)
        .where(ExtractedTable.document_id == document.id)
        .order_by(ExtractedTable.page_index)
    ):
        if table.page_index in pages:
            candidates.extend(table_candidates(table, pages[table.page_index], document))
    groups = {}
    for item in candidates:
        key = (
            item["metric"],
            item["basis"],
            item["period_start"],
            item["period_end"],
            item["currency"],
            item["units"],
        )
        groups.setdefault(key, []).append(item)
    existing = {
        (f.metric, f.basis, f.period_start, f.period_end, f.currency, f.units): f
        for f in db.scalars(select(Fact).where(Fact.document_id == document.id))
    }
    added, conflicts = 0, 0
    for key, items in groups.items():
        if len({item["value"] for item in items}) != 1:
            conflicts += 1
            old = existing.get(key)
            if old is not None and old.verification_method == "automatic":
                old.verified = False
                old.review_note = "Conflicting source rows require review."
                old.source_details = {**(old.source_details or {}), "conflict": True}
            continue
        item = items[0]
        chunk = next(
            (
                c
                for c in chunks
                if (c.id == item["table_id"] or c.id.startswith(item["table_id"] + ":c"))
                and item["row_text"] in c.text
            ),
            None,
        )
        if chunk is None:
            continue
        fact = existing.get(key)
        if fact and fact.verification_method != "automatic":
            continue
        if fact is None:
            fact = Fact(
                document_id=document.id,
                chunk_id=chunk.id,
                metric=item["metric"],
                period_start=item["period_start"],
                period_end=item["period_end"],
                basis=item["basis"],
                currency=item["currency"],
                units=item["units"],
                revision="original",
            )
            db.add(fact)
        fact.value = str(item["value"])
        fact.verified = True
        fact.verification_method = "automatic"
        fact.review_note = "Automatic source checks: explicit row/period/basis/unit and accounting identities. Not a human audit."
        fact.source_details = {
            "source_label": item["source_label"],
            "table_id": item["table_id"],
            "row": item["row"],
            "row_text": item["row_text"],
            "column_index": item["column"],
            "period_header": item["header"],
            "checks": item["checks"],
        }
        added += 1
    db.flush()
    return {"published": added, "conflicts": conflicts}
