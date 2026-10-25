"""Derive reviewable summaries from a recorded run; never run inference here."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
result = json.loads(
    (root / "evaluation/results/postgres-offline.json").read_text(encoding="utf-8")
)
summaries = [s for s in result["summaries"] if s["split"] == "held_out"]
public = root / "frontend/public"
public.mkdir(exist_ok=True)
(public / "evaluation-summary.json").write_text(
    json.dumps(
        {
            "run_at_utc": result["run_at_utc"],
            "k": result["k"],
            "database": result["database"],
            "embedding": result["embedding"],
            "summaries": summaries,
            "limitations": "10 synthetic held-out questions; agent-authored labels, no independent human review. Exact quotation support is not semantic entailment. Unsupported-question abstention is only 50%.",
        },
        indent=2,
    ),
    encoding="utf-8",
)
lines = [
    "# Recorded evaluation",
    "",
    f"Run: {result['run_at_utc']}. Database: {result['database']}. "
    f"Retrieval k={result['k']}. Embeddings: `{result['embedding']}`. Answer mode: {result['answer_provider']}.",
    "",
    "16 fixed questions (6 development, 10 initial held-out), 3 retrieval modes, 48 actual question runs. "
    "All modes use the same corpus, filters and questions. The PDF and question hashes are in the raw report.",
    "",
    "## Initial held-out results",
    "",
    "| Mode | Page recall@6 | Citation IDs valid | Quotes match | Numeric cases correct | Abstention decisions correct | Unsupported abstention | Median / p95 ms |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
]
for s in summaries:

    def pct(key):
        return f"{100 * s[key]:.1f}%" if s[key] is not None else "N/A"

    lines.append(
        f"| {s['mode']} | {pct('recall_at_k')} | {pct('citation_valid')} | {pct('quote_support')} | "
        f"{pct('numerical_correct')} | {pct('abstention_correct')} | {pct('unsupported_abstention_rate')} | "
        f"{s['latency_median_ms']} / {s['latency_p95_ms']} |"
    )
lines += [
    "",
    "Recall is a macro average over questions with expected evidence, using document/company/period/PDF-page identity. "
    "Citation validity and quote support exclude abstentions with no claims. Numerical accuracy is per question "
    "(all expected company values within 0.0001), across 3 held-out numerical cases. Abstention accuracy uses "
    "all 10 questions; unsupported abstention uses only the 4 unsupported questions. p95 is the nearest-rank "
    "95th percentile. Latency is one local run per case, excluding HTTP transport, not a load benchmark.",
    "",
    "All six development questions retrieved expected pages in every mode, and their numeric/abstention checks passed. "
    "These are development measurements, not independent evidence of generalisation.",
    "",
    "## Failures and limits",
    "",
    "- `hold-05`: historical total revenue is returned for a next-year forecast request. All three modes fail appropriate abstention.",
    "- `hold-07`: the answer quotes that cloud revenue is not separately disclosed, but also returns company revenue and fails to abstain. All three modes fail this answerability check.",
    "- `hold-09`: keyword retrieval at k=6 misses one required metric page, so a complete cross-company margin calculation is unavailable. Vector and hybrid retrieve the required pages.",
    "- Citation IDs and literal quotes pass automated checks. No human semantic-support score has been assigned. These checks do not prove that a response answers the user's question.",
    "- Both conflict questions preserve contradictory draft evidence and flag the conflict; the application does not decide which draft is true.",
    "- The local hash vector baseline is lexical, not a semantic embedding model. Results on eight tiny PDF pages are not representative of real filings.",
    "- No paid generation or embedding calls were made. Provider token usage is unavailable in this run; cost is null because no pricing was configured.",
    "- Labels and expectations are agent-authored. Independent human review is pending. No model judge was used.",
    "",
    "## Reproduce",
    "",
    "```powershell",
    ".\\.venv\\Scripts\\python -m app.demo",
    ".\\.venv\\Scripts\\python evaluation/run.py --output evaluation/results/your-run.json",
    "```",
    "",
    "Keep the checked-in baseline. Later tuning informed by these held-out failures requires a new untouched "
    "question set for a new generalisation claim. [Raw baseline](results/postgres-offline.json) · "
    "[Question labels](questions.json) · [Human review worksheet](HUMAN_REVIEW.md).",
    "",
]
(root / "evaluation/REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("Wrote REPORT.md and the interface summary from the recorded run.")
