import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from framework import AnswerEvaluator, EmbeddingEvaluator, RetrievalEvaluator
from statistical_significance import paired_bootstrap

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = [
    ("hash", "local", "hash-v1", 256),
    ("MiniLM", "sentence-transformer", "sentence-transformers/all-MiniLM-L6-v2", 384),
    ("FinBERT-mean-pooling", "sentence-transformer", "ProsusAI/finbert", 768),
]


def main(embedding_only=False):
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", default="hash,MiniLM,FinBERT-mean-pooling")
    parser.add_argument(
        "--bert-score",
        action="store_true",
        help="Downloads DistilBERT; expensive and explicitly opt-in",
    )
    args = parser.parse_args()
    from app.answers import answer
    from app.config import get_settings
    from app.db import engine, init_db, session_scope
    from app.demo import seed_demo, verify_demo_facts
    from app.ingestion import process_document
    from app.models import Document
    from app.schemas import SearchRequest
    from sqlalchemy import select

    questions_path = ROOT / "evaluation/questions.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus": "Isolated SQLite synthetic fixtures; not the private annual report or an independent real-world benchmark",
        "question_set_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
        "k": 6,
        "limitations": "Agent-authored relevance labels; original held-out questions have been inspected. FinBERT mean pooling is not retrieval fine-tuned. Quote matching does not establish semantic faithfulness. Confidence is not calibrated. BERTScore is optional; null means unmeasured.",
        "summaries": [],
        "rows": [],
        "skipped": [],
    }
    for label, provider, model, dimensions in PROVIDERS:
        if label not in args.providers.split(","):
            report["skipped"].append({"provider": label, "reason": "Not requested"})
            continue
        with tempfile.TemporaryDirectory(prefix="filinglens_benchmark_") as folder:
            os.environ.update(
                DATABASE_URL=f"sqlite:///{Path(folder) / 'benchmark.db'}",
                STORAGE_DIR=str(Path(folder) / "pdfs"),
                EMBEDDING_PROVIDER=provider,
                EMBEDDING_MODEL=model,
                EMBEDDING_DIMENSIONS=str(dimensions),
                ANSWER_PROVIDER="extractive",
            )
            engine.cache_clear()
            get_settings.cache_clear()
            try:
                init_db()
                with session_scope() as db:
                    seed_demo(db)
                    for doc in db.scalars(select(Document)):
                        process_document(db, doc)
                    db.flush()
                    verify_demo_facts(db)
                    for mode in (
                        ["vector"]
                        if embedding_only
                        else ["keyword", "vector", "hybrid"]
                    ):
                        group = []
                        for q in questions:
                            result = answer(
                                db,
                                SearchRequest(
                                    question=q["question"],
                                    filters={**q["filters"], "synthetic": True},
                                    mode=mode,
                                ),
                            )
                            ranked = [
                                (e["company"], e["period_end"], e["page_index"])
                                for e in result["evidence"]
                            ]
                            row = {
                                "id": q["id"],
                                "provider": label,
                                "mode": mode,
                                "category": q["category"],
                                **RetrievalEvaluator.score(
                                    ranked, [tuple(x) for x in q["evidence"]]
                                ),
                                **AnswerEvaluator.score(result, q, args.bert_score),
                                "latency_ms": result["latency_ms"],
                                "expected_abstention": q["abstain"],
                                "actual_abstention": result["abstained"],
                            }
                            group.append(row)
                        confusion = {
                            "correctly_abstained": 0,
                            "incorrectly_abstained": 0,
                            "correctly_answered": 0,
                            "incorrectly_answered": 0,
                        }
                        for r in group:
                            key = (
                                (
                                    "correctly_abstained"
                                    if r["expected_abstention"]
                                    else "incorrectly_abstained"
                                )
                                if r["actual_abstention"]
                                else (
                                    "incorrectly_answered"
                                    if r["expected_abstention"]
                                    else "correctly_answered"
                                )
                            )
                            confusion[key] += 1
                        report["summaries"].append(
                            {
                                "provider": label,
                                "mode": mode,
                                "count": len(group),
                                **EmbeddingEvaluator.aggregate(group),
                                "latency_ms": RetrievalEvaluator.latency(
                                    [r["latency_ms"] for r in group]
                                ),
                                "abstention_confusion": confusion,
                            }
                        )
                        report["rows"].extend(group)
            except Exception as error:
                report["skipped"].append({"provider": label, "reason": str(error)})
            finally:
                engine().dispose()
    report["statistical_tests"] = []
    for provider in {s["provider"] for s in report["summaries"]}:
        groups = {
            mode: {
                r["id"]: r["mrr"]
                for r in report["rows"]
                if r["provider"] == provider
                and r["mode"] == mode
                and r["mrr"] is not None
            }
            for mode in ["keyword", "hybrid"]
        }
        common = sorted(groups["keyword"].keys() & groups["hybrid"].keys())
        if common:
            report["statistical_tests"].append(
                {
                    "provider": provider,
                    "comparison": "hybrid minus keyword MRR; exploratory, no multiplicity correction",
                    **paired_bootstrap(
                        [groups["keyword"][q] for q in common],
                        [groups["hybrid"][q] for q in common],
                    ),
                }
            )
    name = "embedding-comparison" if embedding_only else "full-evaluation"
    results = ROOT / "evaluation/results"
    results.mkdir(exist_ok=True)
    (results / f"{name}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        charts = results / "charts"
        charts.mkdir(exist_ok=True)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(
            [s["provider"] + "\n" + s["mode"] for s in report["summaries"]],
            [s["mrr"] for s in report["summaries"]],
            color="#14634b",
        )
        ax.set(
            ylabel="MRR@6",
            ylim=(0, 1),
            title="Synthetic corpus retrieval; exploratory comparison",
        )
        fig.tight_layout()
        fig.savefig(charts / f"{name}.png", dpi=150)
        plt.close(fig)
    except ImportError:
        pass
    print(json.dumps({"runs": len(report["rows"]), "skipped": report["skipped"]}))
    from render_report import write_report

    write_report(report, embedding_only)


if __name__ == "__main__":
    main()
