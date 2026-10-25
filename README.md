# FilingLens

**Indian Financial Filings Intelligence** — a portfolio application for asking evidence-backed questions, inspecting source pages and comparing reviewed financial metrics.

FastAPI · React + TypeScript · PostgreSQL full-text search · pgvector · PDF worker · Docker Compose

> **The included TCS and Infosys PDFs are synthetic.** Every figure and management statement in them is invented for software testing. No real issuer PDFs are redistributed. Offline answers are verbatim extracts, not generated financial analysis.

## Run the complete application

Start Docker Desktop, then run from this folder:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Open [http://localhost:5173](http://localhost:5173). Choose **Load synthetic demo** and wait until the four PDFs are indexed. The worker extracts pages, tables and metric candidates. No API key or embedding-model download is required. Fonts are bundled locally. Initial dependency/image downloads require internet access.

- Interface: [localhost:5173](http://localhost:5173)
- Interactive API: [localhost:5173/api/docs](http://localhost:5173/api/docs)
- API directly: [localhost:8000/api/docs](http://localhost:8000/api/docs)
- Readiness: [localhost:8000/api/ready](http://localhost:8000/api/ready)
- PostgreSQL: `127.0.0.1:5438`, local demo database/user `filinglens`

If `.env` already exists, retain your values. The defaults work without copying it. Ports bind to localhost. `docker compose stop` stops the app; `docker compose up -d` resumes it with the same data. Database and PDFs persist in separate named volumes. Do not remove volumes unless you intend to discard your local corpus.

## What works

- Upload digital PDFs up to 100 MB / 500 pages, with explicit company, type, reporting dates, publication date, currency, units, basis and optional official URL. The interface reads the configured limit from the API and shows selected file size.
- SHA-256 duplicate detection, retryable background jobs, page-bounded text extraction and grid-table extraction. Scanned, empty, encrypted, damaged and poorly extracted PDFs fail clearly.
- Company/type/period/publication-cutoff filtering **before** keyword, cosine-vector or reciprocal-rank-fusion retrieval. Unknown publication dates are excluded by cutoff queries.
- Extractive answers with clickable evidence, original PDF preview at the cited page, separate printed page labels and run diagnostics.
- Optional OpenAI-compatible embedding/generation adapters with bounded retries, timeouts, configuration fingerprints, citation-ID checks and literal supporting-quote checks.
- Source-review workflow for narrowly recognised financial candidates. Deterministic `Decimal` calculations handle lakh/crore/million conversions, revenue percentage change, margin percentage-point/basis-point changes, basis/revision/currency/duration compatibility and zero denominators.
- Responsive research desk, document library, empty/failure/loading states, metric comparisons and a method/evaluation page showing actual recorded measurements.
- 34 backend tests, six browser checks, fixed evaluation labels/results and GitHub Actions configuration.

The app accepts additional companies and reporting periods through metadata without code changes. Document types are quarterly results, annual report, investor presentation and transcript. This describes digital text/table ingestion, not universal extraction of correct financial facts from all layouts.

## Try it

1. Select **TCS**, both periods. Ask **What changed in operating margin between these quarters?**
2. Inspect the invented 24% and 25% inputs and the +1 percentage-point result. Click a citation and open PDF page 1.
3. Select both companies. Ask **Compare revenue growth for TCS and Infosys.** The fixture results are +2.5% and +4%.
4. In **Compare metrics**, compare TCS margins in basis points: +100 bps.
5. Ask **What is the share price?** The corpus cannot answer. Inspect harder failure cases in the evaluation report.

Full [demo walkthrough](docs/DEMO.md) · [architecture and tradeoffs](docs/ARCHITECTURE.md) · [API guide](docs/API.md) · [source provenance](docs/PROVENANCE.md).

## Evaluation: actual runs, including failures

The checked-in run contains **48 question runs**: 6 development + 10 initial held-out questions, each tested with all 3 retrieval modes on the same four synthetic PDFs. PostgreSQL, local 256-dimensional hash embeddings, extractive answers, k=6. The interface uses k=8 for exploratory research.

| Initial held-out metric | Keyword | Vector baseline | Hybrid |
|---|---:|---:|---:|
| Page recall@6 | 96.43% | 100% | 100% |
| Numerical cases correct | 2/3 | 3/3 | 3/3 |
| Citation IDs valid / literal quote matches | 100% / 100% | 100% / 100% | 100% / 100% |
| Appropriate abstention on unsupported questions | 2/4 | 2/4 | 2/4 |

Matching quotations do **not** prove semantic support. Forecast and cloud-segment questions expose answerability failures; keyword retrieval also misses a needed metric page in one case at k=6. Latency values, raw answers, question/PDF hashes and scoring denominators are in [the recorded report](evaluation/REPORT.md) and [raw results](evaluation/results/postgres-offline.json).

Labels were authored and inspected by the implementation agent. Independent human review is pending; no human answer-quality score or model judge is claimed. These tiny synthetic-corpus results do not establish real-filings accuracy. No paid provider calls were made; provider token usage is unavailable and cost is null without supplied pricing.

Reproduce without overwriting the baseline:

```powershell
# With the Compose database running, install the local Python environment below first.
.\.venv\Scripts\python evaluation/run.py --output evaluation/results/your-run.json
```

For a new benchmark, preserve the split before tuning. Once failures inform changes, use a new untouched question set for an independent held-out claim. [Review worksheet](evaluation/HUMAN_REVIEW.md).

## Local development

Tested host: Python 3.11.9, Node 22.19.0, npm 10.9.3. Exact transitive Python and frontend dependencies are locked. Use Python 3.11 for these locks; Python 3.14 is not supported by the pinned binary dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.lock
.\.venv\Scripts\python -m pip install --no-deps -e backend
Copy-Item .env.example .env
docker compose up -d db
.\.venv\Scripts\python -m app.demo
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In separate terminals from the repository root:

```powershell
.\.venv\Scripts\python -m app.worker
```

```powershell
cd frontend
npm ci
npm run dev
```

Choose either the complete Compose application or host development servers, to avoid port conflicts. Do not reuse the same PDF paths across a host server and container server: each deployment should own its corpus/storage location. The full Compose path was tested from fresh volumes.

For a lightweight convenience demo without PostgreSQL, omit `.env` or set `DATABASE_URL=sqlite:///./data/filinglens.db`, then run the host API/worker and `python -m app.demo`. SQLite uses a Python lexical scorer and JSON vector scan; it is not PostgreSQL FTS. PostgreSQL is the primary deployment and published evaluation backend.

## Tests and checks

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
.\.venv\Scripts\python -m ruff check backend evaluation scripts
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests expect a running app with the four indexed synthetic documents. Set `DEMO_URL` to test another frontend URL. Backend tests use isolated temporary SQLite databases by default. To run PostgreSQL integration tests, create a **dedicated** database named `filinglens_test` and set `TEST_DATABASE_URL`; tests drop/recreate tables there and refuse other database-name prefixes. Never point integration tests at your research database. CI uses a disposable pgvector service.

GitHub Actions runs lint, PostgreSQL tests, a frontend build, evaluation and browser workflows. The workflow is configured but has not been run on GitHub in this local session. See [verification details and tested versions](docs/VERIFICATION.md).

## Optional provider configuration

Default `ANSWER_PROVIDER=extractive`, `EMBEDDING_PROVIDER=local` keeps all research offline. To opt into a provider, set the following in `.env` and restart the API/worker:

```dotenv
ANSWER_PROVIDER=openai
ANSWER_MODEL=your-enabled-chat-completions-model
PROVIDER_API_KEY=your-key
PROVIDER_BASE_URL=https://api.openai.com/v1
# Optionally use provider embeddings as well:
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=256
```

Model names are configurable; check your provider's supported models and JSON-output capabilities. These adapters use the documented [embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create) and [Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create). Setting a provider sends the selected question/evidence or chunk text to that provider. Keep credentials in environment variables, not Git. No live provider generation is claimed as tested.

Changing embedding provider/model/dimensions requires reindexing through `POST /api/documents/{id}/reindex`; this clears fact reviews. Keyword search remains available with an old embedding configuration. Optional `INPUT_COST_PER_MILLION` and `OUTPUT_COST_PER_MILLION` values enable configured USD estimates using provider-reported usage. Supply your own verified pricing; no price is assumed by the app.

## Limitations and deployment boundary

- Unsupported questions with overlapping vocabulary can return related historical excerpts. This is a documented answerability failure, even when citation and quote checks pass. Always inspect sources.
- Local hash embeddings are a lexical baseline, not a trained semantic model. No OCR, multilingual quality guarantee or arbitrary-table fact extraction is included.
- Real uploads are not automatically trusted. Recognised candidates require review, and many real tables produce no metric candidates at all. Adjusted figures and mixed revisions need manual reconciliation; currency FX conversion is not implemented.
- Synthetic data is the only validated corpus. Automated retrieval attempts for the two official PDFs returned HTTP 403; see [record](docs/real-extraction-check.json). Official URLs and manual retrieval instructions are in the [manifest](sources/official-manifest.json).
- This localhost demo has no login, tenant isolation, role-based fact approval, public rate limiter or production migration system. It is not ready for public financial-data use. The PDFs are untrusted data; stronger worker resource/process isolation is needed for hostile uploads at scale.
- The queue uses a 15-minute lease without renewal. Run one worker for this demo; large jobs or multiple workers need lease extension and stronger ownership control.
- Future work: independently reviewed real corpus, stronger answerability, semantic embedding benchmarks, OCR, robust table schemas, production authentication/migrations and operational load tests. These are not completed capabilities.

Built in six Git milestones with simple English commit messages. [Stages](docs/MILESTONES.md) · [Resume bullets based on observed work](docs/RESUME_BULLETS.md).
