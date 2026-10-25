# Embedding comparison

Isolated SQLite synthetic fixtures; not the private annual report or an independent real-world benchmark

Agent-authored relevance labels; original held-out questions have been inspected. FinBERT mean pooling is not retrieval fine-tuned. Quote matching does not establish semantic faithfulness. Confidence is not calibrated. BERTScore is optional; null means unmeasured.

The local models run on CPU. Request latency excludes corpus indexing and initial model downloads. Original held-out labels have been inspected; new questions are regression cases. This is not a blind evaluation.

| Provider | Mode | MRR@6 | NDCG@6 | Recall@6 | Precision@6 | MAP@6 |
|---|---|---:|---:|---:|---:|---:|
| hash | vector | 0.905 | 0.924 | 1.000 | 0.262 | 0.893 |
| MiniLM | vector | 0.938 | 0.944 | 0.976 | 0.246 | 0.926 |
| FinBERT-mean-pooling | vector | 0.881 | 0.917 | 1.000 | 0.262 | 0.888 |

Relevance is binary at the (company, period, PDF page) level, with duplicate pages removed. Empty gold sets are excluded from IR averages. Precision uses k=6 as the denominator. Citation precision/recall use gold relevant pages; quote support checks literal traceability, not semantic entailment.

| Provider | Mode | ROUGE-L | BERTScore F1 | Numerical exact | Abstention accuracy | Citation precision | Quote support |
|---|---|---:|---:|---:|---:|---:|---:|
| hash | vector | 0.149 | unmeasured | 1.000 | 0.867 | 0.647 | 1.000 |
| MiniLM | vector | 0.145 | unmeasured | 0.833 | 0.867 | 0.633 | 1.000 |
| FinBERT-mean-pooling | vector | 0.147 | unmeasured | 1.000 | 0.867 | 0.656 | 1.000 |

BERTScore uses distilbert-base-uncased, without baseline rescaling. Similarity scores do not establish correctness. Numerical exact match compares Decimal calculation results, not natural-language number extraction. Semantic faithfulness is unmeasured: an independent assessor must label whether each claim follows from its quote.

| Provider / mode | Correct abstention | Wrong abstention | Answerable accepted | Unanswerable accepted | p50 / p90 / p99 ms |
|---|---:|---:|---:|---:|---|
| hash / vector | 7 | 0 | 19 | 4 | 2.1 / 5.2 / 11.6 |
| MiniLM / vector | 7 | 0 | 19 | 4 | 14.8 / 18.5 / 25.9 |
| FinBERT-mean-pooling / vector | 7 | 0 | 19 | 4 | 48.0 / 54.2 / 61.1 |

These confusion counts concern the answerability decision only; 'answerable accepted' does not mean the answer is fully correct. The raw per-question results expose remaining extractive failures, including overlapping unsupported questions.

## Paired bootstrap: hybrid minus keyword MRR

Exploratory paired resampling of the same questions, 5,000 iterations, fixed seed. No multiple-comparison correction; small synthetic samples do not support claims of broad superiority.

| Provider | Pairs | Mean difference | 95% interval | Two-sided p |
|---|---:|---:|---|---:|

Not applicable to this vector-only embedding comparison. See FULL_REPORT.md for paired retrieval-mode tests.

Skipped/unavailable configurations: []

Question-set SHA-256: `2c2328ac477ecb6183778d77cccf58df45a12f817c342d7ee6d8826cca9f75ff`.

The corpus is made up. The private annual-report workflow/NLP checks are reported separately in docs/VERIFICATION.md and are not a labelled real-world retrieval benchmark.
