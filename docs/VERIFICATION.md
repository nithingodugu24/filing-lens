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
