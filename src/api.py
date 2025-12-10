
import sys
import os
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
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
        
        return AnalysisResponse(
            answer=answer,
            sources=[], # TODO: Extract sources from state if needed
            metadata={"status": "completed"}
        )
        
    except Exception as e:
        print(f"❌ Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run server
    uvicorn.run(api, host="0.0.0.0", port=8000)
