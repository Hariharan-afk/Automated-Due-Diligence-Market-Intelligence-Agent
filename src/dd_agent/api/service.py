from __future__ import annotations
from fastapi import FastAPI

app = FastAPI(title="Due Diligence Agent API")

@app.get("/health")
def health():
    return {"ok": True}
