# Quick walkthrough

1. Start Docker Desktop, run `docker compose up -d --build`, and open [FilingLens](http://localhost:5173).
2. Click **Upload report**. Choose or drop a PDF, enter the company, choose the report type and financial year, and confirm which figures it contains. The report name is filled from the filename. Dates are shown before upload; an annual 2025–26 report uses 1 April 2025 to 31 March 2026. Use **Use different dates** for another period. Publication date, currency, units and source link are under **Optional details**. The PDF limit is 100 MB by default.
3. Open **My reports**. Wait for **Ready**. If the status says **Needs attention**, read the reason and retry or supply a better PDF. A scanned PDF needs text recognition first. A failed report is never treated as ready.
4. Open **Ask a question**. Keep **My uploaded reports** selected, choose a company/period, and start with **What is this report?**. The app explains the company, report period and page count and links to its opening page. Choose a follow-up button or type a specific question, then click **Find answer**. Open the source button beside an excerpt or calculation to inspect its page. **Read text**, **View PDF** and **Open PDF** provide different ways to verify it. Broad prompts such as “why?” now ask what you want to understand instead of claiming the report lacks the answer.
5. To try the included examples, choose **Sample reports** under **Reports to use**, or **Try with sample reports** on an empty screen. Sample figures are invented and are kept separate from uploaded reports. Select all companies and **Compare revenue growth**: the sample results are TCS +2.5% and Infosys +4%.
6. Open **Compare numbers**. On the sample reports, choose TCS, operating margin and basis-point change. The sample change is +100 bps from 24% to 25%. The source values, calculation and source links appear together. Real recognised numbers must be checked in My reports before they can be compared.
7. Ask **What is the share price?** The sample corpus cannot answer, and the interface says **I couldn't find a supported answer**, with suggested questions. Related-word unsupported questions can still fail abstention; see [the evaluation report](../evaluation/REPORT.md).
8. **More search options** holds report-type, publication-cutoff and retrieval settings. **How answers work** in the footer explains the method and recorded evaluation. These options are available without crowding the main workflow.

For real documents, use the [official manifest](../sources/official-manifest.json). Automated download checks returned HTTP 403 for the attempted official PDFs. Download through the issuer's normal website and upload manually. Real-disclosure answer quality and live paid providers remain unverified.

## Upgrade demonstration

1. Select Sample reports, then Dashboard. Show checked revenue/margin series and the relative company comparison. State that the numbers are invented; changing Company updates the charts.
2. Return to Ask a question, choose Conversation mode, ask what affected operating margin, then ask why it changed. Open a citation from either turn.
3. In the reader, choose View PDF, inspect the highlighted quotation, browse nearby pages and use fit/zoom. Select a short source passage, add a note, then open it from Notes. These annotations do not alter the original PDF.
4. Use Export to download a PDF or Excel analysis. Show the checked facts, formulas and source references. An individual reply also has Save answer.
5. For an uploaded real report, ask “What is this report?”, then a specific business-model question. Open its cited pages. Charts may be empty if no real figures were reviewed; explain why this is preferable to plotting unchecked numbers.
6. With local models enabled, open Sentiment for identified management-commentary pages and Knowledge graph for source-linked entity mentions. Tone scores are model estimates. Graph edges mean sentence co-occurrence, not proven business relationships.
7. Show evaluation/FULL_REPORT.md: 270 actual regression runs, explicit metrics, bootstrap intervals, remaining abstention failures and the synthetic-corpus limitation. FinBERT was not assumed to outperform the hash baseline.
8. If a Gemini API key is configured, demonstrate a generated cited answer. Otherwise state that the adapter/validation/retry path is tested with controlled responses; do not present extractive answers as live Gemini reasoning.
9. Accounts are enabled only when a JWT secret is configured. The initial administrator should be registered by the owner, rather than pre-created during the demo setup.
