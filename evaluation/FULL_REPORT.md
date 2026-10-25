# Full evaluation

Isolated SQLite synthetic fixtures; not the private annual report or an independent real-world benchmark

Agent-authored relevance labels; original held-out questions have been inspected. FinBERT mean pooling is not retrieval fine-tuned. Quote matching does not establish semantic faithfulness. Confidence is not calibrated. BERTScore is optional; null means unmeasured.

The local models run on CPU. Request latency excludes corpus indexing and initial model downloads. Original held-out labels have been inspected; new questions are regression cases. This is not a blind evaluation.

| Provider | Mode | MRR@6 | NDCG@6 | Recall@6 | Precision@6 | MAP@6 |
|---|---|---:|---:|---:|---:|---:|
| hash | keyword | 0.952 | 0.963 | 1.000 | 0.262 | 0.948 |
| hash | vector | 0.905 | 0.924 | 1.000 | 0.262 | 0.893 |
| hash | hybrid | 0.905 | 0.927 | 1.000 | 0.262 | 0.898 |
| MiniLM | keyword | 0.952 | 0.963 | 1.000 | 0.262 | 0.948 |
| MiniLM | vector | 0.938 | 0.944 | 0.976 | 0.246 | 0.926 |
| MiniLM | hybrid | 0.976 | 0.960 | 0.976 | 0.246 | 0.942 |
| FinBERT-mean-pooling | keyword | 0.952 | 0.963 | 1.000 | 0.262 | 0.948 |
| FinBERT-mean-pooling | vector | 0.881 | 0.917 | 1.000 | 0.262 | 0.888 |
| FinBERT-mean-pooling | hybrid | 0.952 | 0.965 | 0.988 | 0.254 | 0.950 |

Relevance is binary at the (company, period, PDF page) level, with duplicate pages removed. Empty gold sets are excluded from IR averages. Precision uses k=6 as the denominator. Citation precision/recall use gold relevant pages; quote support checks literal traceability, not semantic entailment.

| Provider | Mode | ROUGE-L | BERTScore F1 | Numerical exact | Abstention accuracy | Citation precision | Quote support |
|---|---|---:|---:|---:|---:|---:|---:|
| hash | keyword | 0.150 | 0.762 | 1.000 | 0.867 | 0.647 | 1.000 |
| hash | vector | 0.148 | 0.762 | 1.000 | 0.867 | 0.647 | 1.000 |
| hash | hybrid | 0.149 | 0.762 | 1.000 | 0.867 | 0.647 | 1.000 |
| MiniLM | keyword | 0.149 | 0.762 | 1.000 | 0.867 | 0.647 | 1.000 |
| MiniLM | vector | 0.145 | 0.761 | 0.833 | 0.867 | 0.633 | 1.000 |
| MiniLM | hybrid | 0.148 | 0.761 | 0.833 | 0.867 | 0.633 | 1.000 |
| FinBERT-mean-pooling | keyword | 0.150 | 0.762 | 1.000 | 0.867 | 0.647 | 1.000 |
| FinBERT-mean-pooling | vector | 0.147 | 0.759 | 1.000 | 0.867 | 0.656 | 1.000 |
| FinBERT-mean-pooling | hybrid | 0.150 | 0.761 | 0.833 | 0.867 | 0.640 | 1.000 |

BERTScore uses distilbert-base-uncased, without baseline rescaling. Similarity scores do not establish correctness. Numerical exact match compares Decimal calculation results, not natural-language number extraction. Semantic faithfulness is unmeasured: an independent assessor must label whether each claim follows from its quote.

| Provider / mode | Correct abstention | Wrong abstention | Answerable accepted | Unanswerable accepted | p50 / p90 / p99 ms |
|---|---:|---:|---:|---:|---|
| hash / keyword | 7 | 0 | 19 | 4 | 2.5 / 6.0 / 7.9 |
| hash / vector | 7 | 0 | 19 | 4 | 3.7 / 5.5 / 10.0 |
| hash / hybrid | 7 | 0 | 19 | 4 | 4.5 / 6.4 / 7.0 |
| MiniLM / keyword | 7 | 0 | 19 | 4 | 3.7 / 9.7 / 15.2 |
| MiniLM / vector | 7 | 0 | 19 | 4 | 18.6 / 25.2 / 36.6 |
| MiniLM / hybrid | 7 | 0 | 19 | 4 | 21.4 / 25.8 / 33.0 |
| FinBERT-mean-pooling / keyword | 7 | 0 | 19 | 4 | 6.1 / 13.3 / 17.4 |
| FinBERT-mean-pooling / vector | 7 | 0 | 19 | 4 | 70.6 / 84.8 / 95.6 |
| FinBERT-mean-pooling / hybrid | 7 | 0 | 19 | 4 | 73.0 / 87.3 / 154.4 |

These confusion counts concern the answerability decision only; 'answerable accepted' does not mean the answer is fully correct. The raw per-question results expose remaining extractive failures, including overlapping unsupported questions.

## Paired bootstrap: hybrid minus keyword MRR

Exploratory paired resampling of the same questions, 5,000 iterations, fixed seed. No multiple-comparison correction; small synthetic samples do not support claims of broad superiority.

| Provider | Pairs | Mean difference | 95% interval | Two-sided p |
|---|---:|---:|---|---:|
| MiniLM | 21 | 0.0238 | [0.0000, 0.0714] | 0.6247 |
| hash | 21 | -0.0476 | [-0.1190, 0.0000] | 0.2565 |
| FinBERT-mean-pooling | 21 | 0.0000 | [-0.0952, 0.0952] | 1.0000 |

Skipped/unavailable configurations: []

Question-set SHA-256: `2c2328ac477ecb6183778d77cccf58df45a12f817c342d7ee6d8826cca9f75ff`.

The corpus is made up. The private annual-report workflow/NLP checks are reported separately in docs/VERIFICATION.md and are not a labelled real-world retrieval benchmark.
