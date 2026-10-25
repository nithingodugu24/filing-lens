from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from .models import Chunk, Document, Fact

SCALE = {
    "unit": Decimal(1),
    "lakh": Decimal(100000),
    "crore": Decimal(10000000),
    "million": Decimal(1000000),
    "billion": Decimal(1000000000),
    "percent": Decimal(1),
}


def period_label(start: date, end: date):
    fiscal_end = end.year + 1 if end.month >= 4 else end.year
    quarter = ((end.month - 4) % 12) // 3 + 1
    return {
        "fiscal": f"Q{quarter} FY{str(fiscal_end)[-2:]}",
        "calendar": f"{start.isoformat()} to {end.isoformat()}",
    }


def decimal_value(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError()
        return number
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Missing or invalid financial value.") from None


def calculate(first, second, operation, cross_company=False):
    if not first.verified or not second.verified:
        raise ValueError("Both facts must be reviewed against their source before calculation.")
    if first.metric != second.metric or first.basis != second.basis:
        raise ValueError("Metrics and standalone/consolidated basis must match.")
    if first.revision != second.revision:
        raise ValueError("Original and restated figures require reconciliation. Select matching revisions.")
    if first.currency != second.currency:
        raise ValueError("Currency mismatch. A dated exchange-rate adjustment is required.")
    if cross_company and (first.period_start, first.period_end) != (second.period_start, second.period_end):
        raise ValueError("Cross-company comparisons require the same reporting dates.")
    duration_a, duration_b = (
        (first.period_end - first.period_start).days,
        (second.period_end - second.period_start).days,
    )
    if abs(duration_a - duration_b) > 3:
        raise ValueError(
            "Reporting durations differ. Annual and quarterly figures cannot be compared directly."
        )
    if first.units not in SCALE or second.units not in SCALE:
        raise ValueError("Unknown units. Review the source units.")
    a, b = decimal_value(first.value) * SCALE[first.units], decimal_value(second.value) * SCALE[second.units]
    if first.metric == "operating_margin":
        if first.units != "percent" or second.units != "percent":
            raise ValueError("Operating margin requires percentage units.")
        if operation not in {"percentage_points", "basis_points"}:
            raise ValueError("Choose percentage-point or basis-point change for operating margin.")
        result = (b - a) * (100 if operation == "basis_points" else 1)
        units = "basis points" if operation == "basis_points" else "percentage points"
        formula = "(second − first) × 100" if operation == "basis_points" else "second − first"
    else:
        if first.units == "percent" or second.units == "percent":
            raise ValueError("Revenue requires a currency amount, not percentage units.")
        if operation == "percentage_change":
            if a == 0:
                raise ValueError("Percentage change is undefined when the first value is zero.")
            result, units, formula = (b - a) / abs(a) * 100, "%", "(second − first) / |first| × 100"
        elif operation == "difference":
            result, units, formula = (
                b - a,
                f"{first.currency} units",
                "second − first (after unit conversion)",
            )
        else:
            raise ValueError("Revenue supports percentage change or absolute difference.")
    return {
        "result": str(result.quantize(Decimal("0.0001"))),
        "units": units,
        "formula": formula,
        "normalised_inputs": {"first": str(a), "second": str(b)},
        "operation": operation,
        "input_values": [
            {
                "value": f.value,
                "currency": f.currency,
                "units": f.units,
                "basis": f.basis,
                "revision": f.revision,
                "period": period_label(f.period_start, f.period_end),
            }
            for f in [first, second]
        ],
    }


def compare_facts(db, request):
    rows = [
        db.execute(
            select(Fact, Document, Chunk)
            .join(Document, Fact.document_id == Document.id)
            .join(Chunk, Fact.chunk_id == Chunk.id)
            .where(Fact.id == fact_id)
        ).first()
        for fact_id in request.fact_ids
    ]
    if not all(rows):
        raise ValueError("One or more facts were not found.")
    first, second = rows
    if first[0].id == second[0].id:
        raise ValueError("Select two different facts.")
    if first[1].synthetic != second[1].synthetic:
        raise ValueError("Synthetic and real financial figures cannot be compared.")
    result = calculate(first[0], second[0], request.operation, first[1].company != second[1].company)
    result["citations"] = [
        {
            "id": f.chunk_id,
            "document_id": d.id,
            "title": d.title,
            "company": d.company,
            "page_index": c.page_index,
            "text": c.text,
            "synthetic": d.synthetic,
        }
        for f, d, c in rows
    ]
    return result
