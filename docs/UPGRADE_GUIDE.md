# FilingLens upgrade guide

The twelve items in the supplied roadmap are implemented as application features. External credentials and independent research labels are separate from implementation. This is an educational system, not a validated financial adviser.

## What to use

| Screen / action | Purpose |
|---|---|
| Ask a question | Ask once, or switch to Conversation mode for follow-ups; open a cited source |
| My reports | Upload a digital PDF, watch live preparation progress and review extracted figures |
| Compare numbers | Compare two checked figures with explicit basis, units and formula |
| Dashboard | Revenue, operating-margin and relative company charts using checked facts only |
| Knowledge graph | Explore detected names and figures, with source-page mentions |
| Source reader | Read text, highlight a quotation in the PDF, browse pages, save notes or analyse commentary |
| Export | Download a PDF, Excel workbook, CSV facts or Markdown analysis; individual answers have Save answer |
| Moon / sun | Change theme; the preference is saved; mobile uses bottom navigation |

Uploaded and sample reports remain separate. Shared company and period selections also apply to the dashboard. A real PDF can be ready for text questions while having no checked financial metrics; that is an empty chart state, not missing company performance.

## Local models

The lightweight defaults still work without model downloads. To enable the full CPU model environment in Docker, set these values in your ignored `.env`:

```dotenv
INSTALL_ML=true
SENTIMENT_ENABLED=true
NER_ENABLED=true
EMBEDDING_PROVIDER=sentence-transformer
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
```

Then run `docker compose up -d --build`. The ML image includes pinned CPU PyTorch, sentence-transformers, spaCy and its English model. Hugging Face weights download on first use into the persistent `model_cache` volume; model loading is reported in server/worker logs. Subsequent requests reuse in-memory models and cached weights. No document content is sent to Hugging Face to run these local models.

If existing documents used different embeddings, rebuild their vectors using the configured environment:

```powershell
# Host Python, connected to the Compose database using .env:
python scripts/rebuild_embeddings.py
```

This writes each document's new vectors atomically and preserves pages, facts, review notes and annotations. Keyword search remains available during a model change. Vector/hybrid search rejects mixed fingerprints until all selected documents match the new configuration. The older `/reindex` action re-extracts the PDF and resets extracted fact reviews; use it only when that is intended.

For host development:

```powershell
uv pip install --python .venv/Scripts/python.exe -r backend/requirements-dev.lock
uv pip install --python .venv/Scripts/python.exe --no-deps -e backend
.venv/Scripts/python.exe -m spacy download en_core_web_sm
```

`requirements-dev.lock` includes CPU package-index configuration. `requirements.lock` is the light runtime; `requirements-ml.lock` is the optional model runtime. spaCy 3.8.7 and preshed 3.0.10 are pinned after a newer preshed Windows tokenizer failed in a real model load.

MiniLM uses 384 native dimensions. FinBERT uses 768; smaller configured vectors are explicitly truncated and renormalised, which is an experiment rather than a trained dimensionality reduction. Dimensions larger than a model's output fail clearly. Model-native token limits still apply to embedding inputs. Missing ML packages or weights produce an actionable error and leave keyword search available; the provider never silently substitutes hash vectors.

FinBERT is a sentiment classifier, not a sentence-similarity model. Its mean-pooled hidden states are included only as an experimental retrieval baseline. Applying a published domain model does not itself establish a new research contribution.

## Gemini

Set `ANSWER_PROVIDER=gemini`, `GEMINI_API_KEY` and `GEMINI_MODEL`, then restart the backend. The current configurable default is `gemini-3.8-flash`. The roadmap's `gemini-2.0-flash` was retired; check [Google's model lifecycle page](https://ai.google.dev/gemini-api/docs/deprecations/) for availability in your account.

The default answer provider remains extractive. No Gemini key is bundled and no paid Gemini request was used to verify this implementation. SDK construction, the 30-second per-attempt timeout, retries and the validated response path have automated tests using controlled responses. Rate limits/server errors receive at most three attempts. Real service access, quota and model answer quality need a configured account.

Remote generation receives the question, up to five recent conversation messages and retrieved passages. Remote embeddings receive text to embed. Use providers according to the documents' permissions. Citation IDs and verbatim quotes are checked, but those checks do not prove that the model's interpretation follows from a quote. Confidence is a model estimate, not measured accuracy; estimates below 0.5 cause abstention. Uncited free-form model summaries are not displayed as verified findings.

Conversation IDs are UUIDs. Recent context can help retrieve a follow-up topic; history is not source evidence. Changing the selected reports starts a new conversation in the UI and rejects continuation with different filters in the API. Answers and conversation history are persisted for explicit export.

## Accounts

Set a random `JWT_SECRET_KEY` with at least 32 characters to enable registration and sign-in. An empty key preserves the local demo. The first registered account becomes administrator and inherits existing local reports. Create that account before exposing an authenticated deployment to others.

Administrators can see all reports and load samples. Analysts upload and review their own reports; viewers can read, ask questions/conversations, save personal notes and request derived analysis, but cannot upload/reindex documents or review financial facts. The API enforces access on source PDFs, search, facts, conversations, graphs, exports and live events. Deduplication is per owner even when two users upload the same bytes. The source file can share hashed storage without sharing document records.

Passwords use bcrypt. JWTs use HS256, issuer/audience validation and configurable expiry. The browser refreshes active tokens within an eight-hour sign-in window. It stores the requested bearer token in localStorage and removes it on sign-out/401. This is a project authentication system: there is no email verification, password recovery, token revocation list or shared distributed rate limiter. Sign-in/registration are limited to 20 attempts/minute/IP per API process; a public deployment should add an edge/shared limiter and HTTPS.

## Notes, NLP and events

Notes must quote text actually present on the chosen extracted page. They are separate from the original PDF and are not written back into its bytes. The enhanced PDF viewer includes page navigation, fit/zoom and a collapsible window of up to 20 thumbnails. A standard PDF viewer is used if enhanced rendering fails. Matching normalises whitespace/table separators, so difficult PDF text layouts may still need the text reader.

Sentiment jobs use token-bounded FinBERT chunks (512 including special tokens) and token-weighted aggregation. The current section heuristic analyses heading-containing management-commentary pages, not a perfectly segmented complete management discussion. Contents pages and short listings are screened out heuristically. Missing commentary returns an explicit failure, never an invented neutral score. Positive tone does not imply good financial performance.

spaCy recognises organisations, people, money, dates and percentages, with financial rules for metrics, crore/lakh and FY notation. These are model detections, not reviewed facts. Graph edges mean **mentioned together in a sentence**. The UI does not claim that proximity establishes a CEO role or a revenue relationship. Nodes link back to mentions. The graph display is capped at 150 nodes and 350 edges for usability; per-entity mention responses start at 200, with Load more mentions to browse the rest. Detected entities can be underlined in the source text.

Optional sentiment/entity jobs are automatically queued after new indexing when their feature flags are enabled. The separate worker records durable status events in the database; the API streams these over `/api/ws`, so notifications cross process boundaries. Events are scoped by document access. WebSockets reconnect with backoff and use a first-frame bearer token rather than a URL token. A 60-second refresh remains as recovery for missed/disconnected events. Large production installations need outbox retention and stronger operational controls.

## Research and reproducibility

```powershell
python evaluation/benchmark_embeddings.py
python evaluation/run_full.py --bert-score
```

These scripts create isolated temporary SQLite corpora and never replace user document indexes. The committed full evaluation contains 270 runs: 30 questions × 3 modes × 3 local embedding configurations. It includes MRR, NDCG, recall, precision, MAP, numerical exact match, ROUGE, measured DistilBERT BERTScore, citation precision/recall, literal quote support, latency percentiles, abstention confusion counts and paired bootstrap comparisons. PNG charts and JSON/Markdown reports are in `evaluation/`.

The questions and relevance labels are agent authored. Earlier held-out questions have now been inspected, so this is a regression benchmark, not a new blind test. The synthetic corpus is tiny. The private 360-page annual report was checked separately for ingestion, real model inference, source navigation and answer workflow; it is not a manually labelled real-world retrieval benchmark. The full PDF is not committed.

Semantic faithfulness remains unmeasured without independent claim annotations. ROUGE/BERTScore measure text similarity, not financial correctness. Quote support is labelled separately. Abstention results expose remaining extractive baseline failures; no claim of perfect adversarial safety or general superiority is made. See [FULL_REPORT.md](../evaluation/FULL_REPORT.md) and [EMBEDDING_REPORT.md](../evaluation/EMBEDDING_REPORT.md).

## References

- [Sentence Transformers encode and normalisation API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
- [ProsusAI FinBERT model](https://huggingface.co/ProsusAI/finbert)
- [Google Gen AI Python SDK](https://github.com/googleapis/python-genai)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [React-PDF viewer and text renderer](https://github.com/wojtekmaj/react-pdf)
- [vis-network interaction API](https://visjs.github.io/vis-network/docs/network/)
