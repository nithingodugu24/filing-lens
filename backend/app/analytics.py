"""Charts only use checked facts, keeping incompatible measurement series apart."""

from collections import Counter
from decimal import Decimal

from sqlalchemy import select

from .models import Document, Fact


def analytics(db, synthetic=None):
    docs = db.scalars(select(Document).where(Document.status == "indexed")).all()
    docs = [d for d in docs if synthetic is None or d.synthetic == synthetic]
    by_id = {d.id: d for d in docs}
    facts = [f for f in db.scalars(select(Fact).where(Fact.verified.is_(True))) if f.document_id in by_id]
    counts = Counter(
        (
            by_id[f.document_id].company,
            f.metric,
            f.period_start,
            f.period_end,
            f.basis,
            f.currency,
            f.revision,
        )
        for f in facts
    )
    revenue, margin = [], []
    fact_counts = Counter(by_id[f.document_id].company for f in facts)
    factors = {"unit": 1, "lakh": 100000, "crore": 10000000, "million": 1000000, "billion": 1000000000}
    for f in sorted(facts, key=lambda f: (f.period_end, by_id[f.document_id].company)):
        doc = by_id[f.document_id]
        key = (doc.company, f.metric, f.period_start, f.period_end, f.basis, f.currency, f.revision)
        if counts[key] != 1:
            continue
        row = {
            "company": doc.company,
            "document_id": doc.id,
            "fact_id": f.id,
            "period": f"{f.period_start} to {f.period_end}",
            "period_start": str(f.period_start),
            "period_end": str(f.period_end),
            "value": f.value,
            "currency": f.currency,
            "units": f.units,
            "basis": f.basis,
            "revision": f.revision,
            "synthetic": doc.synthetic,
        }
        if f.metric == "revenue" and f.units in factors:
            row["normalised_value"] = str(Decimal(f.value) * factors[f.units] / Decimal(10000000))
            row["series"] = (
                f"{doc.company} · {f.currency} crore · {f.basis} · {f.revision} · {'annual' if (f.period_end - f.period_start).days > 300 else 'quarterly' if 80 <= (f.period_end - f.period_start).days <= 100 else str((f.period_end - f.period_start).days) + ' days'}"
            )
            revenue.append(row)
        elif f.metric == "operating_margin" and f.units == "percent":
            row["series"] = f"{doc.company} · {f.basis} · {f.revision} · {f.period_start}"
            margin.append(row)
    profiles = []
    for company in sorted({d.company for d in docs}):
        rev = [r for r in revenue if r["company"] == company]
        margins = [r for r in margin if r["company"] == company]
        growth = None
        if (
            len(rev) >= 2
            and rev[-1]["series"] == rev[-2]["series"]
            and Decimal(rev[-2]["normalised_value"]) != 0
        ):
            growth = str(
                (Decimal(rev[-1]["normalised_value"]) / Decimal(rev[-2]["normalised_value"]) - 1) * 100
            )
        profiles.append(
            {
                "company": company,
                "document_count": sum(d.company == company for d in docs),
                "fact_count": fact_counts[company],
                "latest_revenue": rev[-1]["value"] if rev else None,
                "latest_margin": margins[-1]["value"] if margins else None,
                "revenue_growth": growth,
                "metric_coverage": len({f.metric for f in facts if by_id[f.document_id].company == company})
                / 2
                * 100,
            }
        )
    return {
        "summary": {"document_count": len(docs), "company_count": len(profiles), "fact_count": len(facts)},
        "revenue_trends": revenue,
        "margin_trends": margin,
        "company_profiles": profiles,
        "excluded_ambiguous_facts": sum(
            1
            for f in facts
            if counts[
                (
                    by_id[f.document_id].company,
                    f.metric,
                    f.period_start,
                    f.period_end,
                    f.basis,
                    f.currency,
                    f.revision,
                )
            ]
            > 1
        ),
    }
