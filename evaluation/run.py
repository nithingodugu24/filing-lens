"""Run against the actual configured database. Never fabricates metrics or model judgements."""

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.answers import answer, validate_claims
from app.config import get_settings
from app.db import init_db, session_scope
from app.demo import verify_demo_facts
from app.models import Chunk, Document
from app.schemas import SearchRequest

ROOT = Path(__file__).resolve().parents[1]


def run(split, k, output):
    questions_path = ROOT / "evaluation/questions.json"
    questions = [
        q
        for q in json.loads(questions_path.read_text())
        if split == "all" or q["split"] == split
    ]
    rows = []
    init_db()
    with session_scope() as db:
        documents = db.scalars(
            select(Document).where(Document.status == "indexed")
        ).all()
        if len([d for d in documents if d.synthetic]) != 4:
            raise SystemExit(
                "Load and index the four synthetic fixtures before evaluation."
            )
        verify_demo_facts(db)
        for mode in ["keyword", "vector", "hybrid"]:
            for q in questions:
                request = SearchRequest(
                    question=q["question"],
                    mode=mode,
                    k=k,
                    filters={**q["filters"], "synthetic": True},
                )
                result = answer(db, request)
                got = {
                    (e["company"], e["period_end"], e["page_index"])
                    for e in result["evidence"]
                }
                expected = {tuple(e) for e in q["evidence"]}
                citations = {e["id"] for e in result["evidence"]}
                claims = result["claims"]
                valid = all(
                    cid in citations and db.get(Chunk, cid) is not None
                    for c in claims
                    for cid in c["citation_ids"]
                )
                try:
                    validate_claims(claims, result["evidence"])
                    quote_support = True
                except ValueError:
                    quote_support = False
                numeric = None
                if "numbers" in q:
                    got_numbers = {
                        c["company"]: float(c["result"]) for c in result["calculations"]
                    }
                    numeric = all(
                        company in got_numbers
                        and abs(got_numbers[company] - value) <= q["tolerance"]
                        for company, value in q["numbers"].items()
                    )
                combined = " ".join(c["text"] for c in claims).lower()
                rows.append(
                    {
                        "id": q["id"],
                        "split": q["split"],
                        "category": q["category"],
                        "mode": mode,
                        "recall_at_k": len(got & expected) / len(expected)
                        if expected
                        else None,
                        "citation_valid": valid if claims else None,
                        "quote_support": quote_support if claims else None,
                        "expected_terms_present": all(
                            n.lower() in combined for n in q.get("needles", [])
                        ),
                        "numerical_correct": numeric,
                        "abstention_correct": result["abstained"] == q["abstain"],
                        "expected_abstention": q["abstain"],
                        "actual_abstention": result["abstained"],
                        "conflict_flagged": "conflicting"
                        in result["limitation"].lower()
                        if q.get("conflict")
                        else None,
                        "latency_ms": result["latency_ms"],
                        "usage": result["usage"],
                        "cost_usd": result["cost_usd"],
                        "expected_answer": q["expected_answer"],
                        "actual": result,
                    }
                )
        summaries = []
        for mode in ["keyword", "vector", "hybrid"]:
            for part in sorted({r["split"] for r in rows}):
                group = [r for r in rows if r["mode"] == mode and r["split"] == part]

                def mean(key):
                    values = [r[key] for r in group if r[key] is not None]
                    return round(statistics.mean(values), 4) if values else None

                summaries.append(
                    {
                        "mode": mode,
                        "split": part,
                        "questions": len(group),
                        **{
                            key: mean(key)
                            for key in [
                                "recall_at_k",
                                "citation_valid",
                                "quote_support",
                                "numerical_correct",
                                "abstention_correct",
                                "conflict_flagged",
                            ]
                        },
                        "unsupported_abstention_rate": statistics.mean(
                            [
                                r["actual_abstention"]
                                for r in group
                                if r["expected_abstention"]
                            ]
                        ),
                        "latency_median_ms": round(
                            statistics.median(r["latency_ms"] for r in group), 2
                        ),
                        "latency_p95_ms": sorted(r["latency_ms"] for r in group)[
                            max(0, math.ceil(len(group) * 0.95) - 1)
                        ],
                    }
                )
        report = {
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": db.bind.dialect.name,
            "k": k,
            "answer_provider": get_settings().answer_provider,
            "embedding": f"{get_settings().embedding_provider}:{get_settings().embedding_model}:{get_settings().embedding_dimensions}",
            "question_set_sha256": hashlib.sha256(
                questions_path.read_bytes()
            ).hexdigest(),
            "corpus": [
                {
                    "company": d.company,
                    "period_end": str(d.period_end),
                    "sha256": d.sha256,
                }
                for d in documents
                if d.synthetic
            ],
            "grading": "Automated page recall, retrieved-ID integrity, exact quote matching and Decimal tolerances. No human semantic grading or model judge was performed.",
            "summaries": summaries,
            "rows": rows,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summaries, indent=2))
    print(f"Saved {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split", choices=["all", "development", "held_out"], default="all"
    )
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "evaluation/results/latest.json"
    )
    args = parser.parse_args()
    run(args.split, args.k, args.output)
