# Real-report acceptance checks

The purpose is a useful report-reading workflow, not a feature count. These checks are local acceptance evidence, not independent financial validation or proof of public-launch readiness.

## Source data

The prepared issuer library uses the four fixed URLs and byte hashes in `backend/app/library.py`. Run `docker compose exec -T backend python -m app.prepare_library` after configuring models. The command is repeatable; changed issuer bytes require manifest review. Complete source PDFs remain outside Git.

| Report | Source unit | Financial source PDF page | Checked rows |
| --- | --- | --- | --- |
| Infosys FY 2024–25 | INR crore | 30 | 24 |
| Infosys FY 2023–24 | INR crore | 29 | 24 |
| Wipro FY 2024–25 | INR million | 272 (consolidated), 174 (standalone) | 24 |
| Wipro FY 2023–24 | INR million | 247 (consolidated), 160 (standalone) | 24 |

Each report supplies revenue, other income, total income, profit before tax, tax expense and profit for the year, for two years and two accounting bases. The parser checks literal rows, explicit year/basis/unit headers, revenue + other income = total income, and PBT − tax = profit where all three are present. It does not substitute profit attributable to owners for profit for the year. Annual figures are not relabelled quarterly. Conflicting automatic rows are withdrawn pending review. Automated source checks are labelled separately from manual review.

Borderless tables use PDF word coordinates and aligned year/value columns. Note references and percentage-growth columns are not mistaken for monetary values. Whitespace in a numeric cell can be removed; missing digits are never invented. Display conversion to crore uses Decimal; exports preserve the source units. PDF indices are distinct from printed page numbers.

Financial pages were visually inspected as well as parsed. This is a small acceptance set, not a general table-extraction benchmark.

## Reported failure

In the user's uploaded TCS Annual Report 2025–26, PDF page 35 contains both standalone and consolidated columns. The exact question `what is the total income in crores this year` now returns 271423 INR crore, consolidated, FY 2025–26, with the source row and page. The prior-year value is 259286; explicit standalone returns 230974. Revenue is kept separate from total income and income-tax expense. These checks validate the uploaded file's contents; the upload is not registered as an issuer-verified library template.

Unsupported financial lookups do not return an unrelated lease-liability paragraph. The app explains that the figure could not be verified for the requested year/basis. Direct numbers and arithmetic use typed source rows and Decimal; narrative explanations use the configured AI service with literal source references.

## User workflow

- The default screen is a report overview: choose a report and basis, inspect three main figures, read the cited brief, ask about that report or export.
- Brief sections cover business performance, management's explanation and business risks. Missing support is shown as a partial brief, rather than filled in. Provider failure leaves source figures usable and offers retry.
- Questions carry explicit document IDs when a report is selected. Recent answers are stored and can be reopened or removed.
- The main navigation has Overview, Ask, Reports and Compare. The former graph is replaced with a searchable, source-linked directory showing at most 24 matching people/organisations. Proximity does not establish an executive or ownership relationship.
- Opening a prepared library item in an account creates its own evidence copy; private uploads do not become public templates.
- Full browser regression tests run on an isolated offline fixture server. A separate local live-browser check covers the actual uploaded income question and real report source pages.

## Remaining launch gates

Public launch still needs an operated HTTPS deployment, password recovery and session revocation, verified backup/restore, shared abuse/cost limits, load and tenant-isolation testing under concurrency, a retention/deletion policy and independent review by intended users. The current local configuration is not exposed publicly. Production configuration rejects development secrets, missing authentication/AI, hash embeddings, default database credentials and non-HTTPS origins. Public signup never creates a production administrator.

Use `python -m app.admin email full_name` from an operator terminal to create an administrator deliberately; the password is prompted, never passed in command arguments. In development, the historical first-user convenience is retained. Do not reuse that development configuration for a public service.
## Verification recorded for this change

- Full backend suite: 90 tests passed on isolated SQLite.
- PostgreSQL integration: full 86-test run passed before the final additional financial cases; the final 15 financial/workspace/ownership/production/export cases also passed on PostgreSQL.
- Browser suite: 21 workflows passed on a separate offline test server, including report scope, source figures, source reader, directory bounds, conversations, notes, upload feedback, mobile navigation and export.
- Live local checks: the four official reports returned their checked total-income figures with correct source pages, units and basis. The actual Infosys PDF opened at page 30 in the browser with no page errors; mobile had no horizontal overflow. The downloaded brief was rendered and visually checked.
- Production frontend build and lint checks passed. Source figures and quote references were checked separately from the synthetic regression corpus; no public-user validation is claimed.

The latest live brief check produced complete three-section briefs for the uploaded TCS report, both Infosys reports and Wipro FY 2023–24. Wipro FY 2024–25 has a partial brief: business performance and risks are supported, but an explicit management explanation was not supported by the retrieved passages. The app labels it partial and keeps the checked figures available. This retrieval limitation is not hidden by inserting a number or an invented explanation.
