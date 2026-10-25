from fastapi import FastAPI

app = FastAPI(title="FilingLens", version="0.1.0", description="Indian financial filings intelligence")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FilingLens"}
