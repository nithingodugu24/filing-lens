# Resume bullets grounded in implemented work

- Built FilingLens, an evidence-first financial-filings application using FastAPI, React/TypeScript, PostgreSQL full-text search and pgvector, with a background PDF-processing worker, document provenance and page-linked citations.
- Implemented keyword, exact-vector and reciprocal-rank-fusion retrieval, configurable AI-provider adapters, citation/quotation validation and deterministic Decimal calculations for revenue and operating-margin comparisons.
- Evaluated 48 actual question runs across three retrieval modes on four clearly labelled synthetic PDFs; hybrid retrieval achieved 100% page recall@6 and passed all three held-out numerical cases, while exposing a 50% unsupported-question abstention rate.
- Added cached MiniLM semantic retrieval, experimental FinBERT retrieval/sentiment, spaCy financial entities, source-highlighted PDF notes, checked financial charts and optional Gemini conversations.
- Implemented optional JWT accounts with tenant-scoped source/query/export access, role checks, a durable worker-event outbox with WebSockets, and PDF/Excel/CSV/Markdown reporting.
- Ran a 270-case synthetic regression comparison across three embedding configurations and three retrieval modes, with MRR/NDCG/MAP, ROUGE, BERTScore, numerical/citation/abstention metrics and paired bootstrap tests; reported limitations and failures.
- Verified 70 backend checks and 20 browser workflows, a frontend production build and Docker Compose startup; added GitHub Actions checks and reproducible evaluation artifacts. See the verification record for database-specific runs.
- Processed a real user-uploaded 360-page annual report into 1,511 searchable chunks and 490 extracted tables, then checked source-linked extractive questions and cited PDF pages. This is a workflow result, not a financial-fact accuracy benchmark.

Use the last bullet only together with the verification record. GitHub Actions is configured, but no remote workflow run is claimed. The 10 initial held-out questions and expected labels were agent-authored and not independently human reviewed. These are synthetic-corpus measurements, not real-company research or production performance. No paid model generation was tested.
