# Verification record — 25 October 2026

The application was implemented and exercised in this workspace. All measurements below came from actual local commands and browser sessions. GitHub publishing/deployment and a remote Actions run were not performed.

## Observed checks

| Check | Observed outcome |
|---|---|
| Isolated SQLite backend suite | 32 passed |
| Dedicated PostgreSQL + pgvector backend suite | 32 passed |
| Python lint | Passed for backend, evaluation and scripts |
| Frontend TypeScript and production build | Passed on Windows and in Linux Docker build |
| Browser workflows on host app | 4 passed |
| Browser workflows on full Docker app | 4 passed |
| Mobile viewport | 390 × 844, no horizontal document overflow in the tested library view; research screenshot saved |
| Python dependency audit | No known vulnerabilities in the final installed environment at time of run |
| npm dependency audit | No known vulnerabilities at time of run |
| Clean Docker startup | Database and document volumes created fresh; API became healthy; worker online; library initially empty |
| Fresh fixture workflow | Four synthetic PDFs queued through the running API, worker indexed them, eight facts reviewed against the fixture specification |
| API documentation through frontend proxy | HTTP 200 at `/api/docs` |
| Evaluation | 48 actual question runs, results and failures saved; no model judge or independent human review |
| Official source download checks | Both attempted issuer PDF downloads returned HTTP 403; real PDF extraction remains unverified |

Tests cover damaged/scanned PDFs, header and request limits, duplicate hashes, safe filenames, transactional provider-failure retries, page/table extraction, metadata/cutoff filtering, query-to-source workflows, citation-ID/quotation rejection, provider timeouts/rate limits, incompatible embedding dimensions/configurations, unit/margin/growth calculations, missing/zero values, original/restated conflicts and incompatible bases/currencies/reporting dates.

The browser checks cover question → evidence → PDF page link/preview, filters and unsupported questions, source-linked deterministic comparisons, document preview, upload-form validation and mobile layout. Successful multipart PDF upload and file serving are tested at the API layer; a full user-driven real-document upload and review was not validated in the browser. The live UI was also inspected in the in-app browser.

## Versions actually exercised

| Component | Version |
|---|---|
| Host Python | 3.11.9 |
| Docker Python | 3.11.17 |
| Host Node / npm | 22.19.0 / 10.9.3 |
| PostgreSQL / vector extension | 17.6 / 0.8.0 |
| FastAPI / Starlette | 0.162.0 / 1.10.0 |
| Pydantic / SQLAlchemy | 2.14.1 / 2.0.40 |
| psycopg / pgvector Python adapter | 3.2.6 / 0.4.0 |
| PyMuPDF / HTTPX | 1.25.5 / 0.28.1 |
| React / TypeScript / Vite | 19.1.0 / 5.8.3 / 6.4.5 |
| Playwright / pytest / Ruff | 1.64.1 / 9.1.1 / 0.11.8 |

Exact transitive dependencies are in the Python requirements locks and `frontend/package-lock.json`. Container base tags can receive updates; repeat checks after rebuilding with a changed base image. Non-fatal dependency deprecation warnings were emitted by the test client/PDF bindings; they did not fail tests.

## Inspectable artifacts

- [Desktop research desk](screenshots/research-desk.png)
- [Mobile research desk](screenshots/research-mobile.png)
- [Evaluation report with scoring definitions and failures](../evaluation/REPORT.md)
- [Full baseline answers, configurations and corpus hashes](../evaluation/results/postgres-offline.json)
- [Official-download check results](real-extraction-check.json)
- [Independent review worksheet](../evaluation/HUMAN_REVIEW.md)

No paid provider calls were made. Provider tests use controlled responses, timeouts and rate-limit simulations. Citation checks establish source identity and literal-quote matching; they cannot establish semantic entailment. Synthetic-corpus performance should not be presented as real-disclosure research accuracy.

## Follow-up: larger annual-report uploads

The original 20 MiB limit rejected a user's annual report in the browser. The default is now 100 MiB, configurable from 1–100 via `MAX_UPLOAD_MB`. The proxy permits 101 MiB including multipart overhead; the API publishes its payload limit through readiness, and the interface reads it instead of hard-coding a separate cap. Oversized payloads return HTTP 413; the interface shows selected size and immediate feedback.

- 34 backend tests passed on SQLite and PostgreSQL. A valid PDF with a metadata stream above 20 MiB was uploaded through the API and indexed; a configured 1 MiB cap rejected an oversized PDF with HTTP 413.
- Six browser checks passed against the rebuilt Docker app. The new browser tests confirm a 21 MiB selection reaches the upload endpoint (intercepted response, no test document added to the user's library) and that a controlled 1 MiB limit produces immediate feedback and disables upload.
- TypeScript/production builds and Python lint passed. The running service reports `max_upload_mb: 100`; the running proxy reports `client_max_body_size 101m`.
- This verifies the size-limit fix using synthetic files. The user's actual annual-report PDF was not attached or processed in this follow-up.

## Follow-up: simpler interface

The interface now centres on Ask a question, My reports and Compare numbers. Decorative overview panels were removed, text and controls enlarged, technical options moved behind disclosures, and source-page actions made explicit. Uploads default to real user reports; sample data is a separate selection and is always marked as made up. Question requests set the corresponding synthetic-data filter, so the two corpora are not mixed by the UI.

The shorter upload form derives the report name from the filename and offers financial-year/quarter presets, an editable date range, and optional metadata. An annual 2025–26 report gets 1 April 2025 to 31 March 2026. Annual and custom periods are displayed as a financial year or actual date range instead of being shown as a quarter. Dialogs support Escape, focus trapping and focus restoration. Changing the selected reports clears old answers.

Ten browser checks cover uploads above 20 MiB, the configured size cap, annual/quarter/custom dates, first-time onboarding, failed-report guidance, questions and source pages, filters, calculations, mobile navigation, keyboard interaction and sample/uploaded-data separation. Upload and isolation checks use intercepted responses; no test reports were added to the user's library. The TypeScript and production builds passed. Backend code and the recorded evaluation algorithm were not changed by this interface revision.

## Follow-up: long annual reports and real source checks

The user's 360-page report failed the original two-million-character guard because sorted extraction inserted layout padding. The raw result contained 2,275,803 characters; normalising horizontal spacing produced 1,060,077 characters without removing words, numbers or page boundaries. Budgets now apply to normalised text and are configurable; a separate raw-page guard remains. Processing progress and total page count are visible, the extraction checkpoints extend the lease, and large tables have bounded retrieval chunks.

The existing PDF was retried without reuploading and successfully indexed into **360 pages, 1,511 chunks and 490 extracted tables**. Its cover identified FY 2025–26, and its incorrect quarterly/October metadata was corrected after retaining a local backup. No extracted financial facts were automatically verified.

Real-report question checks exposed an extractive-quotation bug: concatenating separated relevant sentences produced a quote absent from the source. Excerpts now preserve a contiguous sentence window and still pass the same citation/quotation checks. Two actual API questions about the business model and operating margin returned HTTP 200; every retrieved page was fetched and passage quotations validated. A browser check also opened the uploaded PDF cover, confirmed Ready/FY 2025–26/360 pages, submitted a question and opened its cited source page. [Ready report screenshot](screenshots/annual-report-ready.png).

The final backend suite passed **41 tests on SQLite and PostgreSQL**, including spacing regression, retained text limits, bounded table chunks, duplicate-fact prevention, visible progress and contiguous quotations. **Eleven browser checks** passed, including a processing-progress case. Frontend production builds and Python lint passed. Upload/retry/reindex jobs are committed before returning HTTP 202 so an immediate status check sees the new job.

The fixed synthetic evaluation was repeated without replacing the initial baseline: [repeat results](../evaluation/results/after-report-processing.json). Recall/numeric/abstention outcomes remained unchanged, including the known unsupported-question failures. This reuses already-seen labels and is a regression run, not a new independent held-out benchmark. The uploaded report has no manually reviewed financial-answer benchmark. Real PDFs and full local verification outputs remain outside Git.

## Follow-up: report context for simple questions

The exact user question “what is this?” previously lost every token during keyword filtering and returned a misleading missing-evidence message. A narrow local question router now handles report orientation, app help and questions that need clarification before financial retrieval. An overview uses the saved company/type/dates/page count and a real opening-page passage, with the same metadata filters, cutoff and source-set isolation as normal search. Metadata descriptions and literal source quotations remain distinct. No provider credentials or matching vector configuration are required for an overview, and the strategy is recorded in the query run.

Both SQLite and PostgreSQL suites passed **50 tests**. Coverage includes prompt variants, opening-page citation identity, cutoff exclusion, multiple-report limits, no provider calls, clarification/help and preserving numerical questions. **Thirteen browser checks** passed, including report overview → source page → follow-up question and clarification → useful next question. The application and Docker frontend production builds passed.

A separate browser check against the user's real upload entered “what is this?”, received TCS's annual-report period (1 April 2025–31 March 2026) and 360-page count, then opened its actual cover-page citation. [Verified report overview](screenshots/report-overview.png). The original synthetic financial benchmark remains historical; these context routes are usability checks, not evidence of improved semantic-answer accuracy or generative summarisation.

## Final-year upgrade verification — 25 October 2026

- Backend: **70 tests passed on SQLite and 70 on dedicated PostgreSQL/pgvector**, including owner isolation/roles, legacy SQLite migration, vector-dimension changes preserving reviewed facts, Gemini SDK timeout/retry and answer validation, conversation filters, annotation quotation checks, exports, sentiment token windows, entity deduplication and cross-session WebSocket events.
- Browser: **20 workflows passed** against the Docker application. Added dashboard/filter charts, multi-turn/source navigation, actual PDF canvas and quote highlights, note creation/deletion, real file downloads, persistent dark/mobile layout, account/header handling, graph-to-source navigation and a deliberately failed PDF-worker fallback. Account/graph UI scenarios use controlled responses where stated in their tests; API role isolation and actual model inference are checked separately.
- The final browser pass exposed and resolved a read-after-write race: notes, fact reviews, question runs and conversations now commit before returning a response, so immediate refresh/export sees the saved record. A mismatched PDF.js worker and nginx `.mjs` MIME handling were also corrected; the renderer fallback was explicitly exercised.
- Real embedding benchmark: **90 vector-only runs**, hash/MiniLM/experimental FinBERT. Full evaluation: **270 runs**, 30 questions × 3 retrieval modes × 3 local embedding configurations, with actual ROUGE and DistilBERT BERTScore. Recorded IR metrics, numerical exact match, citation precision/recall, quote traceability, abstention confusion counts, latency percentiles and bootstrap intervals are in evaluation/FULL_REPORT.md and JSON. Tiny synthetic/agent-authored labels are a regression set, not an independent blind benchmark; semantic faithfulness is unmeasured.
- This local installation uses **MiniLM, 384 dimensions**, with the CPU ML image and persistent model cache enabled. **1,523 chunks across five indexed PDFs** were re-embedded without deleting document pages, reviewed facts or notes. The real annual report remains **360 pages, 1,511 chunks and 490 extracted tables**. It still has no automatically checked real financial facts.
- Actual real-report question checks ran keyword, vector and hybrid retrieval. Each returned source-backed excerpts, and every returned quotation was found in its cited evidence. This verifies source workflow, not independent financial correctness or retrieval relevance.
- Actual FinBERT inference on the uploaded report identified **seven heading-containing commentary pages**, with an aggregate neutral label (about 0.934 model probability). Heuristic section coverage and model probability are not an assessment of the company's financial health. Actual spaCy inference extracted **4,377 distinct entities and 14,484 sentence-co-occurrence edges**; these are detections, not verified relationships or ground truth.
- Packaged Linux worker verification: POSTing analysis jobs through the live API completed real-report FinBERT analysis and sample-report spaCy extraction, with **7 entities / 15 co-occurrence edges** for the chosen sample. Both completed in about **15.2 seconds combined**, the worker remained online and no jobs remained pending. This checks the separate API/worker runtime, not only mocked unit adapters.
- PDF/Excel downloads were generated through the API. The two-page sample PDF was rendered and visually inspected; the revised layout uses checked-metric tables, readable source references and a revenue chart. Excel has source/fact sheets and application-built numerical formulas. No private PDF or model weights are committed.
- Frontend production build, Python lint, Docker Compose startup and container health checks passed. The Postman collection is generated from OpenAPI and includes **34 requests**, bearer-token handling and documented JSON schema checks.
- Gemini credentials and a JWT deployment secret are **not configured** in this local instance. No live/paid Gemini answer, public authentication deployment, independent human labels or remote CI execution is claimed. Optional setup is documented in UPGRADE_GUIDE.md; the first administrator is left for the owner to create.
