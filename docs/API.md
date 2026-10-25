# API guide

Interactive OpenAPI: [http://localhost:5173/api/docs](http://localhost:5173/api/docs). The same routes are available on port 8000. No API key is needed for local models/extractive answers. Accounts are optional: configuring `JWT_SECRET_KEY` enables bearer authentication and owner-scoped access. Import [FilingLens.postman_collection.json](FilingLens.postman_collection.json) for generated requests and response-schema checks.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Process liveness |
| GET | `/api/ready` | Database connectivity, worker heartbeat and provider mode |
| POST | `/api/demo` | Queue four clearly synthetic fixture PDFs; idempotent once loaded |
| POST | `/api/documents` | Multipart PDF upload with a JSON `metadata` string |
| GET | `/api/documents` | Document metadata, status and latest job error/attempt count |
| GET | `/api/documents/{id}` | One document and its latest job |
| POST | `/api/documents/{id}/retry` | Retry a failed document; returns 409 if already active |
| POST | `/api/documents/{id}/reindex` | Re-extract an indexed/failed document using current embedding settings; resets fact reviews |
| GET | `/api/documents/{id}/file` | Original PDF, inline, safe generated filename |
| GET | `/api/documents/{id}/pages/{page_index}` | Page text, printed label and table cells; index is zero-based |
| POST | `/api/search` | Filtered keyword/vector/hybrid evidence |
| POST | `/api/questions` | Cited extracts or configured generated claims, plus supported deterministic calculations |
| GET | `/api/facts` | Original metric candidates and their review state |
| PATCH | `/api/facts/{id}` | Review note, verification and optional original/restated revision status |
| POST | `/api/compare` | Deterministic calculation on two reviewed fact IDs |

Upload example using PowerShell and curl.exe (actual metadata is supplied by you):

```powershell
curl.exe -X POST http://localhost:8000/api/documents -F 'file=@C:/path/results.pdf' -F 'metadata={"company":"TCS","title":"TCS Q1 FY26 results","document_type":"quarterly_results","period_start":"2025-04-01","period_end":"2025-06-30","publication_date":null,"currency":"INR","units":"crore","basis":"consolidated"}'
```

The document-type enum is `quarterly_results`, `annual_report`, `presentation`, `transcript`. Known currency amounts use `unit`, `lakh`, `crore`, `million`, or `billion`. Units and publication date may be null. Source URL is optional HTTP(S). Basis must be explicit. Period start cannot follow period end. Public uploads are always marked non-synthetic; only the built-in fixture loader creates synthetic documents. The server checks file extension, PDF magic, stream/request size and SHA-256 duplicate identity.

Research request:

```json
{
  "question": "Compare revenue growth",
  "mode": "hybrid",
  "k": 8,
  "filters": {
    "companies": ["TCS", "Infosys"],
    "document_types": ["quarterly_results"],
    "period_ends": ["2025-06-30", "2025-09-30"],
    "publication_cutoff": "2025-10-31",
    "synthetic": true
  }
}
```

Filters are applied before ranking. Cutoff queries exclude unknown publication dates. For an “as of” question, set `publication_cutoff` explicitly using the interface's **As of** field; natural-language date parsing is not implemented. `k` ranges from 1 to 20. Questions are capped at 2,000 characters; JSON request bodies at 64 KiB. PDF payloads default to 100 MiB, configurable with `MAX_UPLOAD_MB` from 1–100. The API allows another 1 MiB for multipart overhead; the proxy permits up to 101 MiB. `/api/ready` exposes `max_upload_mb` so the interface validates against the same setting. Oversized PDF payloads and request bodies return HTTP 413.

Processing defaults are `MAX_PDF_PAGES=500`, `MAX_PAGE_TEXT_CHARS=250000` and `MAX_DOCUMENT_TEXT_CHARS=10000000`. Text budgets apply after removing extra PDF column spacing; a separate raw per-page guard remains. Exceeding a budget fails the job with its actual limit and the relevant setting name; evidence is never silently truncated. While processing, document `page_count` shows the total and `warning` carries progress such as `Reading pages: 120 of 360.`. The final warning is cleared or replaced with genuine extraction warnings when indexing completes.

Question responses include `claims`, retrieved `evidence`, `calculations`, `abstained`, `limitation`, `configuration`, `latency_ms`, provider `usage`, optional configured `cost_usd`, and a persistent `run_id`. Citation IDs are actual chunk IDs and have document/page metadata. Generated quotation validation establishes literal traceability, not semantic support. Missing provider usage is `{}`, not an invented token count. Cost is null when pricing is absent.

Responses also expose `answer_kind` (`answer`, `report_overview`, `clarification`, or `help`), optional `summary`, `report_overviews` and follow-up `suggestions`. Common orientation prompts such as “What is this?” use saved report metadata and the earliest available passage from each selected report. All company/type/period/cutoff/sample filters still apply. Multiple reports are described explicitly and overview output respects `k`. These routes do not call a model or embedding provider; their configuration records `answer_provider=local_context` and the actual routing strategy. Metadata descriptions are distinct from cited source excerpts and do not establish financial facts. Specific financial questions continue through normal retrieval/calculation and unknown facts still abstain.

Comparison request: `{"fact_ids":["first_id","second_id"],"operation":"percentage_change"}`. Operations are `percentage_change`, `difference`, `percentage_points`, `basis_points`. The second value is compared to the first. Revenue percentage change uses `(second-first)/abs(first)*100`; margins use percentage-point or basis-point differences. All results include original and normalised inputs, formula, result, units and actual source citations.

Fact review: `{"verified":true,"note":"Checked value, units, reporting period and basis against source PDF.","revision":"original"}`. Reviews require analyst/admin access when accounts are enabled; they remain user assertions rather than an independent financial audit. Reindexing clears candidates and reviews. The vector-only rebuild script preserves them.

Responses use 202 for queued work, 404 for missing resources, 409 for invalid job transitions, 413 for oversized request bodies, 415 for unsupported file names, 422 for invalid metadata/calculations, and 503 for provider failures. Requests carry an `X-Request-ID`. Structured request logs contain route, status and latency, not PDF bodies, prompts, API credentials or financial contents.

## Added endpoint reference

| Method | Path | Request / response |
|---|---|---|
| GET | `/api/auth/config` | `{enabled: boolean}`, public |
| POST | `/api/auth/register` | `{email,password,full_name}` → token/user, 201 |
| POST | `/api/auth/login` | `{email,password}` → token/user |
| POST | `/api/auth/refresh` | Current bearer token → renewed token/user within the sign-in window |
| GET | `/api/auth/me` | Current public user profile |
| GET | `/api/analytics?synthetic=true&document_ids=id1,id2` | Checked series, summaries and company profiles; optional source/document filters |
| POST | `/api/conversations` | Search request plus UUID `session_id` → answer plus session/turn |
| GET | `/api/conversations/{session_id}` | Chronological messages and stored cited answers |
| POST | `/api/documents/{id}/annotations` | `{page_index,selected_text,note}` → note, 201 |
| GET | `/api/documents/{id}/annotations` | Saved notes in page order |
| DELETE | `/api/annotations/{id}` | `{deleted:true}` |
| POST | `/api/documents/{id}/analyze-sentiment` | Queue FinBERT commentary analysis, 202 |
| GET | `/api/documents/{id}/sentiment` | Feature status, latest task status/error and cached result |
| GET | `/api/sentiment?synthetic=false` | Company/period tone timeline from cached results |
| POST | `/api/documents/{id}/extract-entities` | Queue spaCy extraction, 202 |
| GET | `/api/documents/{id}/entities?page_index=0` | Entity types, counts and source mentions; page/entity filters and mention_offset/mention_limit supported |
| GET | `/api/documents/{id}/knowledge-graph` | Nodes, sentence-co-occurrence edges and task status |
| POST | `/api/export/report` | Selected documents → PDF, XLSX, Markdown or CSV attachment |
| GET | `/api/export/facts?format=csv` | All visible checked facts; `json` also supported |
| WS | `/api/ws` | Scoped live document/analysis events and heartbeat |

All document paths enforce visibility, including PDFs and derived data. Administrators can view all documents; analysts/viewers see their own. A missing or inaccessible object returns 404. Analysts/admins can upload and review; only admins load samples. Viewers can search, ask questions/conversations, compare, export and create their own notes/derived analyses. Document upload/retry/reindex and financial fact reviews require analyst/admin access.

## Authentication examples

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@example.test","password":"replace-with-a-strong-password","full_name":"Analyst"}'
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@example.test","password":"replace-with-a-strong-password"}'
curl http://localhost:8000/api/documents -H 'Authorization: Bearer YOUR_TOKEN'
```

The first account becomes administrator. Do not commit a real secret or bearer token. Login/register return `access_token`, `token_type`, `expires_at` and `user` (`id`, `email`, `full_name`, `role`). Default access expiry is 60 minutes. Refresh requires an unexpired token and is limited to an eight-hour sign-in window. Disabled accounts fail authentication. With no JWT secret the local demo stays open; registration is disabled.

## Conversations, notes and export

```json
{
  "session_id": "11111111-1111-4111-8111-111111111111",
  "question": "What affected operating margin?",
  "filters": {"companies": ["TCS"], "synthetic": true},
  "mode": "hybrid",
  "k": 6
}
```

Post this to `/api/conversations`. Subsequent turns use the same UUID and filters. The server supplies the last five messages as context; prior answers are not evidence. Different filters on the same conversation return 409. Responses keep the question-answer contract and add `session_id` and `turn_number`. `confidence` is null for offline extracts and a model estimate for generated replies. An estimate below 0.5 causes abstention.

Create a note with `{"page_index":0,"selected_text":"an exact passage from the page","note":"Check this section later"}`. The selected text must occur on that page after whitespace normalisation. Note bounds are 3–4,000 characters of source and 1–2,000 of commentary. Deletion is owner scoped.

```bash
curl -X POST http://localhost:8000/api/export/report \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{"document_ids":["DOCUMENT_ID"],"format":"pdf","include_qa":true}' \
  --output filinglens-analysis.pdf
```

Formats are `pdf`, `xlsx`, `md`, `csv`; at most 50 selected reports. Optional `run_id` exports a particular saved answer. Q&A inclusion is restricted to answers whose cited documents all belong to the selected set and the current account scope, using the latest 100 saved runs. Old runs from before response persistence cannot be reconstructed. Fact exports include only checked facts. CSV/spreadsheet text is escaped to prevent formula injection; workbook calculation formulas are built by application code from numerical inputs.

## Filters, bounds and paging

Document/fact listing returns all visible records in this project version; there is no cursor-pagination contract. Search is bounded by `k` (1–20), with at most one selected evidence passage per PDF page. Company/type/period/cutoff/source filters apply before retrieval, not after selecting global results. Dashboard `document_ids` is a comma-separated visible-document selection; an empty selection produces empty series. Unknown dates are excluded by publication cutoffs. Samples and uploads have separate source filters.

Optional analysis returns 503 with setup instructions when disabled, 409 if the PDF is not ready, and 202 only after the worker task is committed. GET returns `not_requested`, `queued`, `processing`, `complete` or `failed`, alongside a cached result where available. Heading detection, entity detections and sentiment probabilities are model/heuristic outputs, not checked financial facts. Graph edges are labelled `mentioned_together`; no executive or financial relationship is inferred from proximity alone.

## Live events

```javascript
const socket = new WebSocket('ws://localhost:5173/api/ws');
socket.onopen = () => {
  // Only needed when accounts are enabled. Keep tokens out of URL query strings.
  const token = localStorage.getItem('filinglens-token');
  if (token) socket.send(JSON.stringify({token}));
};
socket.onmessage = ({data}) => {
  const event = JSON.parse(data);
  if (event.type === 'ping') socket.send('pong');
  else console.log(event.type, event.document_id, event.progress);
};
```

The server first sends `{type:"connected",cursor:n}`. Events include `document_status` (`queued`, `processing`, `failed`), `extraction_progress` (`completed`, `total`, human-readable `progress`), `job_complete` (`status:"indexed"`, `page_count`), `sentiment_complete` and `entities_complete`. Each persisted event has an increasing `event_id`. There is a 15-second heartbeat; reconnect and refresh a current document snapshot rather than assuming replay. Notifications originate from a database outbox so the worker may be a different process. The browser uses exponential reconnect backoff and a 60-second snapshot recovery interval.

## Error reference and limits

| Status | Meaning |
|---|---|
| 401 | Missing, expired, invalid or disabled-account session |
| 403 | Account role cannot perform the action |
| 404 | Missing or inaccessible document/page/note/answer |
| 409 | Invalid job state, changed conversation filters or duplicate account |
| 413 | Request or PDF exceeds its configured size limit |
| 415 | Upload filename is not a PDF |
| 422 | Invalid fields, untraceable note quotation or incompatible financial calculation |
| 429 | Sign-in/register limit reached: 20 attempts/minute/IP/API process |
| 503 | Database, optional model, credentials or remote provider unavailable |

Application errors include `detail` and, where request context exists, `request_id`; every HTTP response also has `X-Request-ID`. Validation errors contain field locations/messages without echoing submitted passwords. Gemini has up to three attempts with backoff on rate limits/server errors and a 30-second per-attempt timeout. Other public/API routes have no distributed quota service. Add shared/edge rate limits and HTTPS for a public deployment.

## Python and JavaScript clients

```python
import httpx
base = 'http://localhost:8000/api'
headers = {'Authorization': 'Bearer YOUR_TOKEN'}  # omit in the open local demo
answer = httpx.post(base + '/questions', headers=headers, timeout=120,
    json={'question':'What is this report?', 'filters':{'synthetic':False}})
answer.raise_for_status()
print(answer.json()['summary'])
```

```javascript
const response = await fetch('/api/questions', {
  method: 'POST',
  headers: {'Content-Type':'application/json', Authorization:'Bearer YOUR_TOKEN'},
  body: JSON.stringify({question:'What is this report?', filters:{synthetic:false}})
});
if (!response.ok) throw new Error((await response.json()).detail);
console.log((await response.json()).summary);
```

Regenerate the Postman collection with `python scripts/generate_postman.py`. It reads OpenAPI without connecting to or changing a database, groups requests by API tag, stores a returned login token and validates documented JSON response schemas. Choose local PDF file paths and real document/fact IDs before running mutation requests.

## Streaming answers

Both `POST /api/questions` and `POST /api/conversations` support `Accept: text/event-stream` with the same JSON body and bearer authentication as the regular endpoints. Requests without that Accept header retain the existing complete JSON response.

The stream sends SSE frames:

- `status`: a readable message while finding passages, writing and checking sources.
- `delta`: the next piece of provisional answer text. Append `data.text` to the draft.
- `draft`: a replacement draft, used when JSON escape decoding revises a partial string.
- `done`: the normal complete answer object, after citation/quote checks and the database commit. Replace the draft with this result.
- `error`: a readable `data.message`. Discard the unfinished draft and offer retry.

Comments keep the connection alive while retrieval or the provider is working. The frontend uses fetch streaming so it can POST a question, send the Authorization header and cancel through AbortController. Raw model JSON and reasoning tokens are not displayed. Draft text is explicitly labelled as awaiting source checks; it is not exported or saved as a completed answer.

A cancelled in-progress request rolls back its answer/conversation transaction. Already completed results remain in history. A failed stream is not automatically replayed after partial output, which avoids duplicate text and duplicate paid generations. Nginx buffering is disabled and the stream sends `X-Accel-Buffering: no`.

Streaming improves the time to the first readable text; retrieval and full generation still take their normal time. Checked table figures and local report-context replies can finish immediately without model tokens.
