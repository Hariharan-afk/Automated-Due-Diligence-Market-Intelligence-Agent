import sys
sys.path.append('.')

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
    result = orchestrator.execute(state["query"])
    return {"classification": result, "iteration": 0}

def run_planner(state: AgentState):
    print(f"\n--- PLANNER (Iteration {state.get('iteration', 0)}) ---")
    # If we have feedback, append it to context
    context = state.get("feedback", "")
    sub_queries = planner.execute(state["query"], context)
    return {"sub_queries": sub_queries}

def run_researcher(state: AgentState):
    print(f"\n--- RESEARCHER ---")
    chunks = researcher.execute(state["sub_queries"])
    return {"research_data": chunks}

def run_synthesiser(state: AgentState):
    print(f"\n--- SYNTHESISER ---")
    result = synthesiser.execute(state["query"], state["research_data"])
    return {
        "answer": result["answer"],
        "sources": result["sources"]
    }

def run_evaluator(state: AgentState):
    print(f"\n--- EVALUATOR ---")
    result = evaluator.execute(state["query"], state["answer"], state["sources"])
    return {
        "evaluation": result,
        "confidence": result.get("confidence", 0.5),
        "hallucination_score": result.get("hallucination_score", 0.0),
        "iteration": state["iteration"] + 1
    }

# 4. Define Conditional Logic
def decide_next_step(state: AgentState):
    decision = state["evaluation"].get("decision", "approve")
    iteration = state["iteration"]
    
    if decision == "reject" and iteration < 3:  # Max 3 retries
        print(f"❌ REJECTED: {state['evaluation'].get('reason')} -> Retrying...")
        return "planner"
    else:
        if iteration >= 3:
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
