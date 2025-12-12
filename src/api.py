
import sys
import os
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure src is in path
sys.path.append('.')

# Load env variables
load_dotenv()
# Explicitly set credentials path to absolute path to be safe
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("vertex-key.json")

from src.graph import app
from src.utils.result_saver import save_result

# Initialize FastAPI
api = FastAPI(
    title="Market Due Diligence Agent API",
    description="5-Agent System for Financial Analysis (Sec, News, Wiki)",
    version="1.0.0"
)

# Request Model
class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = "default_user"

# Response Model
class AnalysisResponse(BaseModel):
    answer: str
    sources: list[str] = []
    metadata: Dict[str, Any] = {}

@api.get("/")
def health_check():
    return {"status": "ok", "system": "Market Due Diligence Agent"}

@api.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: QueryRequest):
    """
    Analyze a market query using the 5-agent system.
    """
    try:
        print(f"📥 Received query: {request.query}")
        
        # Prepare inputs for LangGraph
        inputs = {"query": request.query}
        
        # Invoke the graph
        final_state = app.invoke(inputs)
        
        if isinstance(final_state, dict):
            answer = final_state.get("answer", "No answer generated.")
        else:
            answer = str(final_state)
        
        # Save result (optional side effect)
        save_result(request.query, final_state)
        
        # --- METRIC COLLECTION ---
        timing = final_state.get("timing", {})
        token_usage = final_state.get("token_usage", {})
        
        # Calculate derived metrics
        total_tokens = sum(token_usage.values())
        est_cost = (total_tokens / 1000) * 0.002 # $0.002 per 1k tokens (example rate)
        
        # Total latency from graph (sum of parts, or wall clock?) 
        # Wall clock is better for user experience, but sum of parts is good for breakdown.
        # Let's use the sum of parts for "AI Processing Time"
        total_ai_latency = sum(timing.values()) * 1000 # to ms
        
        # Record rich history
        STATS["history"].append({
            "timestamp": time.time(),
            "latency_ms": total_ai_latency,
            "status": 200,
            "error": 0,
            "breakdown": timing,
            "tokens": total_tokens,
            "cost": est_cost,
            "rag_hit": 1 if len(final_state.get("sources", [])) > 0 else 0
        })
        
        return AnalysisResponse(
            answer=answer,
            sources=[], # TODO: Extract sources from state if needed
            metadata={"status": "completed"}
        )
        
    except Exception as e:
        print(f"❌ Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import time
from collections import deque

# --- Observability / Metrics ---
# --- Observability / Metrics ---
STATS = {
    "total_requests": 0,
    "total_errors": 0,
    "history": deque(maxlen=100) # List of {timestamp, latency, status, breakdown, tokens, cost}
}

@api.middleware("http")
async def track_metrics(request: Request, call_next):
    # middleware only tracks basic counts now
    try:
        response = await call_next(request)
        if request.url.path == "/analyze":
            STATS["total_requests"] += 1
            if response.status_code >= 400:
                STATS["total_errors"] += 1
        return response
    except Exception as e:
        STATS["total_errors"] += 1
        raise e

@api.get("/stats")
def get_stats():
    """Returns real-time system metrics + History for charts."""
    history_list = list(STATS["history"])
    
    avg_latency = 0
    if history_list:
        latencies = [x["latency_ms"] for x in history_list]
        avg_latency = sum(latencies) / len(latencies)
    
    return {
        "status": "healthy",
        "total_requests": STATS["total_requests"],
        "total_errors": STATS["total_errors"],
        "avg_latency_ms": round(avg_latency, 2),
        "history": history_list  # Return full list for plotting
    }

if __name__ == "__main__":
    import uvicorn
    # Run server
    uvicorn.run(api, host="0.0.0.0", port=8000)
