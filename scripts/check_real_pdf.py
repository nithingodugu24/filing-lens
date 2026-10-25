"""Check official downloads without redistributing their PDF files."""

import json
from pathlib import Path

import httpx

from app.ingestion import extract_pdf

sources = [
    (
        "infosys-q1-fy26",
        "https://www.infosys.com/investors/reports-filings/quarterly-results/2025-2026/q1/documents/q1-fy26-financial-results-auditorsreports.pdf",
    ),
    (
        "tcs-q2-fy26",
        "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/2025-26/q2/Presentations/Q2%202025-26%20Fact%20Sheet.pdf",
    ),
]
folder = Path(".local/real-source")
folder.mkdir(parents=True, exist_ok=True)
results = []
for name, url in sources:
    result = {
        "url": url,
        "scope": "Extraction only; no financial values verified. Real PDFs stay outside Git.",
    }
    try:
        response = httpx.get(url, timeout=45, follow_redirects=True)
        response.raise_for_status()
        path = folder / f"{name}.pdf"
        path.write_bytes(response.content)
        pages, tables, warnings = extract_pdf(path)
        result.update(
            status="extracted",
            pages=len(pages),
            tables=len(tables),
            warnings=warnings,
            text_characters=sum(len(p[2]) for p in pages),
        )
    except httpx.HTTPStatusError as error:
        result.update(
            status="download_blocked",
            http_status=error.response.status_code,
            next_step="Download manually from the official investor-relations page; no access controls were bypassed.",
        )
    except (httpx.HTTPError, ValueError):
        result.update(
            status="check_failed", next_step="Retry manually and inspect the PDF."
        )
    results.append(result)
Path("docs/real-extraction-check.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)
print(json.dumps(results, indent=2))
