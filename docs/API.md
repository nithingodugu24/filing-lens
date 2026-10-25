# API guide

Interactive OpenAPI: [http://localhost:5173/api/docs](http://localhost:5173/api/docs). The same routes are available on port 8000. No API key is needed for local extractive mode. There is no application authentication.

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

Filters are applied before ranking. Cutoff queries exclude unknown publication dates. For an “as of” question, set `publication_cutoff` explicitly using the interface's **As of** field; natural-language date parsing is not implemented. `k` ranges from 1 to 20. Questions are capped at 2,000 characters; JSON request bodies at 64 KiB. Upload requests are capped at 21 MiB including multipart overhead and PDF payloads at 20 MiB.

Question responses include `claims`, retrieved `evidence`, `calculations`, `abstained`, `limitation`, `configuration`, `latency_ms`, provider `usage`, optional configured `cost_usd`, and a persistent `run_id`. Citation IDs are actual chunk IDs and have document/page metadata. Generated quotation validation establishes literal traceability, not semantic support. Missing provider usage is `{}`, not an invented token count. Cost is null when pricing is absent.

Comparison request: `{"fact_ids":["first_id","second_id"],"operation":"percentage_change"}`. Operations are `percentage_change`, `difference`, `percentage_points`, `basis_points`. The second value is compared to the first. Revenue percentage change uses `(second-first)/abs(first)*100`; margins use percentage-point or basis-point differences. All results include original and normalised inputs, formula, result, units and actual source citations.

Fact review: `{"verified":true,"note":"Checked value, units, reporting period and basis against source PDF.","revision":"original"}`. Reviews are local assertions, with no identity or authentication guarantee. This is a demo, not a controlled financial-data approval process. Reindexing clears candidates and reviews.

Responses use 202 for queued work, 404 for missing resources, 409 for invalid job transitions, 413 for oversized request bodies, 415 for unsupported file names, 422 for invalid metadata/calculations, and 503 for provider failures. Requests carry an `X-Request-ID`. Structured request logs contain route, status and latency, not PDF bodies, prompts, API credentials or financial contents.
