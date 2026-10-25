# FilingLens

Indian Financial Filings Intelligence. Built in stages; see [MILESTONES.md](docs/MILESTONES.md).

Initial local setup (Python 3.11+, Node 22):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "./backend[dev]"
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# In a second terminal
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. API documentation: http://127.0.0.1:8000/docs.

This repository is being implemented. Demo data will be synthetic and clearly labelled.
