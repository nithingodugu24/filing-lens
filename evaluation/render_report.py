"""Render measured results without rerunning models or inventing missing scores."""

from pathlib import Path


def write_report(report, embedding_only=False):
    root = Path(__file__).resolve().parent
    lines = [
        "# Embedding comparison" if embedding_only else "# Full evaluation",
        "",
        report["corpus"],
        "",
        report["limitations"],
        "",
        "The local models run on CPU. Request latency excludes corpus indexing and initial model downloads. Original held-out labels have been inspected; new questions are regression cases. This is not a blind evaluation.",
        "",
        "| Provider | Mode | MRR@6 | NDCG@6 | Recall@6 | Precision@6 | MAP@6 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    def value(number):
        return "unmeasured" if number is None else f"{number:.3f}"

    for s in report["summaries"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    s["provider"],
                    s["mode"],
                    *[
                        value(s[k])
                        for k in ["mrr", "ndcg", "recall", "precision", "map"]
                    ],
                ]
            )
            + " |"
        )
    lines += [
        "",
        "Relevance is binary at the (company, period, PDF page) level, with duplicate pages removed. Empty gold sets are excluded from IR averages. Precision uses k=6 as the denominator. Citation precision/recall use gold relevant pages; quote support checks literal traceability, not semantic entailment.",
        "",
        "| Provider | Mode | ROUGE-L | BERTScore F1 | Numerical exact | Abstention accuracy | Citation precision | Quote support |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in report["summaries"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    s["provider"],
                    s["mode"],
                    *[
                        value(s[k])
                        for k in [
                            "rougeL",
                            "bertscore",
                            "numerical_exact",
                            "abstention_correct",
                            "citation_precision",
                            "quote_support",
                        ]
                    ],
                ]
            )
            + " |"
        )
    lines += [
        "",
        "BERTScore uses distilbert-base-uncased, without baseline rescaling. Similarity scores do not establish correctness. Numerical exact match compares Decimal calculation results, not natural-language number extraction. Semantic faithfulness is unmeasured: an independent assessor must label whether each claim follows from its quote.",
        "",
        "| Provider / mode | Correct abstention | Wrong abstention | Answerable accepted | Unanswerable accepted | p50 / p90 / p99 ms |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for s in report["summaries"]:
        c = s["abstention_confusion"]
        lines.append(
            f"| {s['provider']} / {s['mode']} | {c['correctly_abstained']} | {c['incorrectly_abstained']} | {c['correctly_answered']} | {c['incorrectly_answered']} | "
            + " / ".join(f"{s['latency_ms'][key]:.1f}" for key in ["p50", "p90", "p99"])
            + " |"
        )
    lines += [
        "",
        "These confusion counts concern the answerability decision only; 'answerable accepted' does not mean the answer is fully correct. The raw per-question results expose remaining extractive failures, including overlapping unsupported questions.",
        "",
        "## Paired bootstrap: hybrid minus keyword MRR",
        "",
        "Exploratory paired resampling of the same questions, 5,000 iterations, fixed seed. No multiple-comparison correction; small synthetic samples do not support claims of broad superiority.",
        "",
        "| Provider | Pairs | Mean difference | 95% interval | Two-sided p |",
        "|---|---:|---:|---|---:|",
    ]
    for row in report.get("statistical_tests", []):
        interval = row["confidence_interval_95"]
        lines.append(
            f"| {row['provider']} | {row['pairs']} | {row['mean_difference']:.4f} | [{interval[0]:.4f}, {interval[1]:.4f}] | {row['p_value_two_sided']:.4f} |"
        )
    if not report.get("statistical_tests"):
        lines.append(
            "\nNot applicable to this vector-only embedding comparison. See FULL_REPORT.md for paired retrieval-mode tests."
        )
    lines += [
        "",
        "Skipped/unavailable configurations: " + str(report["skipped"]),
        "",
        "Question-set SHA-256: `" + report["question_set_sha256"] + "`.",
        "",
        "The corpus is made up. The private annual-report workflow/NLP checks are reported separately in docs/VERIFICATION.md and are not a labelled real-world retrieval benchmark.",
    ]
    (root / ("EMBEDDING_REPORT.md" if embedding_only else "FULL_REPORT.md")).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
