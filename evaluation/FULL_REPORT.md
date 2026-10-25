# Full evaluation

Isolated SQLite synthetic fixtures; not the private annual report or an independent real-world benchmark

Agent-authored relevance labels; original held-out questions have been inspected. FinBERT mean pooling is not retrieval fine-tuned. Quote matching does not establish semantic faithfulness. Confidence is not calibrated. BERTScore is optional; null means unmeasured.

| Provider | Mode | MRR@6 | NDCG@6 | Recall@6 | Abstention accuracy |
|---|---|---:|---:|---:|---:|
| hash | keyword | 0.952 | 0.963 | 1.000 | 0.867 |
| hash | vector | 0.905 | 0.924 | 1.000 | 0.867 |
| hash | hybrid | 0.905 | 0.927 | 1.000 | 0.867 |
| MiniLM | keyword | 0.952 | 0.963 | 1.000 | 0.867 |
| MiniLM | vector | 0.938 | 0.944 | 0.976 | 0.867 |
| MiniLM | hybrid | 0.976 | 0.960 | 0.976 | 0.867 |
| FinBERT-mean-pooling | keyword | 0.952 | 0.963 | 1.000 | 0.867 |
| FinBERT-mean-pooling | vector | 0.881 | 0.917 | 1.000 | 0.867 |
| FinBERT-mean-pooling | hybrid | 0.952 | 0.965 | 0.988 | 0.867 |

Skipped or unavailable: []

Raw JSON includes per-question results, numerical exact match, ROUGE, citation precision/recall, quote support, latency percentiles, confusion counts, and paired bootstrap intervals. Semantic faithfulness needs independent human annotation and is unmeasured.