# Build stages

1. App setup — complete. API health test and frontend production build passed; frontend audit clean.
2. Document processing — complete. Uploads, duplicate checks, transactional worker jobs, page/table extraction and four synthetic PDFs. Later expanded to 32 backend checks.
3. Research engine — complete. Filtered PostgreSQL FTS, exact-vector and RRF retrieval; optional provider adapters, validated citations and Decimal calculations. Live hybrid question flow checked.
4. Research interface — complete. Responsive document library, evidence reader, questions, comparisons and review flow. Production build passed.
5. Evaluation — complete. Six development and ten initial held-out cases; 48 recorded runs. Thirty-two backend tests pass on SQLite and PostgreSQL; four browser workflows pass. Failures and human-review limits are published.
6. Delivery — complete. Docker startup verified from fresh database/document volumes; application remains running with four indexed synthetic PDFs. API/architecture/provenance/evaluation/setup/walkthrough/resume documentation and desktop/mobile screenshots included.

Each stage is committed separately using simple English commit messages.

Commit messages:

1. `Add basic app setup`
2. `Add PDF upload and document processing`
3. `Add search answers and financial comparison`
4. `Add research desk and document screens`
5. `Add tests and evaluation report`
6. `Add setup guide and final demo checks`

Known boundaries: official PDF downloads returned HTTP 403, real-filings quality and live paid providers are unverified, independent human review is pending, and the extractive baseline fails two overlapping-vocabulary unsupported questions. These are documented limitations, not completed future capabilities.

Follow-up commit: `Allow bigger annual report uploads` — default 100 MiB, consistent UI/API/proxy limits, immediate size feedback, and two additional backend and browser checks. Current verification totals: 34 backend tests and six browser checks.

Interface follow-up: `Make app simple and easy to use` — three clear tabs, larger type, shorter uploads with period presets, separate uploaded/sample reports, source buttons, useful empty/failure states and accessible dialogs. Browser coverage expanded to ten checks.

Processing follow-up: `Fix annual report processing and answers` — normalise PDF column spacing, configurable text budgets, visible progress, bounded table chunks and contiguous source quotations. The previously failed 360-page report is indexed, with its annual reporting label corrected from the cover. Verification: 41 backend tests on SQLite/PostgreSQL, eleven browser checks and actual source-page/question checks on the uploaded report.

Question follow-up: `Explain simple questions about reports` — common orientation prompts return selected-report metadata and real opening-page links; vague prompts clarify, help prompts explain the workflow, and follow-up questions are clickable. Financial queries remain evidence-based. Verification expanded to 50 backend tests and thirteen browser checks, including the exact “what is this?” prompt against the uploaded report.

## Final-year project upgrades

1. `9b78fb9 Add local ML models and proper evaluation tools` — optional cached sentence-transformer provider, real dimension/normalisation checks, 30-question regression set, IR/answer metrics and reproducible isolated benchmark scripts.
2. `5ebad74 Add checked analytics and research APIs` — checked-series analytics, Gemini adapter and persisted conversations, FinBERT/spaCy analysis jobs, JWT ownership/roles, notes, exports, durable live events and actual 270-run evaluation artifacts.
3. `3dcd3f8 Add simple research screens and complete upgrade features` — dashboard, conversations, PDF highlights/notes, entity exploration, dark/mobile layout, account screens, downloads, live notifications, model packaging and API contracts. This installation's five reports were moved to MiniLM vectors without losing facts/reviews/notes.
4. Final verification/documentation — API collection, setup/research guide, screenshots, real model/worker checks, migration and browser regression checks. See VERIFICATION.md for final observed results rather than treating implementation as an independently validated research claim.
