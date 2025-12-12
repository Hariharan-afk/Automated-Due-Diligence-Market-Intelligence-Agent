import sys
sys.path.append('.')
import time
import json

from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from src.agents.orchestrator_agent import OrchestratorAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.researcher_agent import ResearcherAgent
from src.agents.synthesiser_agent import SynthesiserAgent
from src.agents.evaluator_agent import EvaluatorAgent
from src.tools.hybrid_search import HybridSearchEngine
from src.tools.reranker import Reranker

# 1. Define State
class AgentState(TypedDict):
    query: str
    classification: Dict[str, Any]
    sub_queries: List[str]
    research_data: List[Dict]
    answer: str
    sources: List[Dict]
    evaluation: Dict[str, Any]
    confidence: float
    hallucination_score: float
    feedback: str
    iteration: int
    timing: Dict[str, float]
    token_usage: Dict[str, int]

# 2. Initialize Agents
# We initialize them outside the nodes to keep state persistence if needed
search_engine = HybridSearchEngine()
reranker = Reranker()

orchestrator = OrchestratorAgent()
planner = PlannerAgent()
researcher = ResearcherAgent(search_engine, reranker)
synthesiser = SynthesiserAgent()
evaluator = EvaluatorAgent()

# 3. Define Nodes
def run_orchestrator(state: AgentState):
    print(f"\n--- ORCHESTRATOR ---")
    start = time.time()
    result = orchestrator.execute(state["query"])
    duration = time.time() - start
    
    # Token Est
    tok_in = len(state["query"]) / 4
    tok_out = len(str(result)) / 4
    
    timing = state.get("timing", {}).copy()
    timing["orchestrator"] = duration
    
    usage = state.get("token_usage", {}).copy()
    usage["orchestrator"] = int(tok_in + tok_out)
    
    return {"classification": result, "iteration": 0, "timing": timing, "token_usage": usage}

def run_planner(state: AgentState):
    print(f"\n--- PLANNER (Iteration {state.get('iteration', 0)}) ---")
    start = time.time()
    # If we have feedback, append it to context
    context = state.get("feedback", "")
    sub_queries = planner.execute(state["query"], context)
    duration = time.time() - start
    
    # Token Est
    tok_in = (len(state["query"]) + len(context)) / 4
    tok_out = len(str(sub_queries)) / 4
    
    timing = state.get("timing", {}).copy()
    timing["planner"] = duration
    
    usage = state.get("token_usage", {}).copy()
    usage["planner"] = int(tok_in + tok_out)

    return {"sub_queries": sub_queries, "timing": timing, "token_usage": usage}

def run_researcher(state: AgentState):
    print(f"\n--- RESEARCHER ---")
    start = time.time()
    # Pass original query for Global Reranking
    chunks = researcher.execute(state["sub_queries"], state["query"])
    duration = time.time() - start
    
    # Token Est
    tok_in = len(str(state["sub_queries"])) / 4
    tok_out = len(str(chunks)) / 4
    
    timing = state.get("timing", {}).copy()
    timing["researcher"] = duration
    
    usage = state.get("token_usage", {}).copy()
    usage["researcher"] = int(tok_in + tok_out)

    return {"research_data": chunks, "timing": timing, "token_usage": usage}

def run_synthesiser(state: AgentState):
    print(f"\n--- SYNTHESISER ---")
    start = time.time()
    result = synthesiser.execute(state["query"], state["research_data"])
    duration = time.time() - start
    
    # Token Est
    tok_in = (len(state["query"]) + len(str(state["research_data"]))) / 4
    tok_out = len(result["answer"]) / 4
    
    timing = state.get("timing", {}).copy()
    timing["synthesiser"] = duration
    
    usage = state.get("token_usage", {}).copy()
    usage["synthesiser"] = int(tok_in + tok_out)

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "timing": timing,
        "token_usage": usage
    }

def run_evaluator(state: AgentState):
    print(f"\n--- EVALUATOR ---")
    start = time.time()
    result = evaluator.execute(state["query"], state["answer"], state["sources"])
    duration = time.time() - start
    
    # Token Est
    tok_in = (len(state["query"]) + len(state["answer"])) / 4
    tok_out = len(str(result)) / 4
    
    timing = state.get("timing", {}).copy()
    timing["evaluator"] = duration
    
    usage = state.get("token_usage", {}).copy()
    usage["evaluator"] = int(tok_in + tok_out)

    return {
        "evaluation": result,
        "confidence": result.get("confidence", 0.5),
        "hallucination_score": result.get("hallucination_score", 0.0),
        "iteration": state["iteration"] + 1,
        "timing": timing,
        "token_usage": usage
    }

# 4. Define Conditional Logic
def decide_next_step(state: AgentState):
    decision = state["evaluation"].get("decision", "approve")
    iteration = state["iteration"]
    
    if decision == "reject" and iteration < 2:  # Max 2 iterations (1 retry)
        print(f"❌ REJECTED: {state['evaluation'].get('reason')} -> Retrying...")
        return "planner"
    else:
        if iteration >= 2:
            print("⚠️ Max iterations reached. Delivering current answer.")
        else:
            print("✅ APPROVED")
        return END

# 5. Build Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("orchestrator", run_orchestrator)
workflow.add_node("planner", run_planner)
workflow.add_node("researcher", run_researcher)
workflow.add_node("synthesiser", run_synthesiser)
workflow.add_node("evaluator", run_evaluator)

# Add Edges
workflow.set_entry_point("orchestrator")
workflow.add_edge("orchestrator", "planner")
workflow.add_edge("planner", "researcher")
workflow.add_edge("researcher", "synthesiser")
workflow.add_edge("synthesiser", "evaluator")

# Conditional Edge
workflow.add_conditional_edges(
    "evaluator",
    decide_next_step,
    {
        "planner": "planner",
        END: END
    }
)

# Compile
app = workflow.compile()
