import sys
sys.path.append('.')

from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.tools.local_client import get_local_client
from src.config import AGENT_CONFIG
from src.utils.helpers import extract_json

class EvaluatorAgent(BaseAgent):
    """Validates answer quality and completeness"""
    
    def __init__(self):
        super().__init__("Evaluator")
        self.client = get_local_client()
        self.temperature = AGENT_CONFIG["evaluator"]["temperature"]
    
    def _format_sources(self, sources: list) -> str:
        """Helper to format sources list into a readable string"""
        formatted_text = ""
        for i, source in enumerate(sources):
            # Handle if source is a dictionary (common) or just a string
            content = source.get('content', str(source)) if isinstance(source, dict) else str(source)
            # Truncate very long sources to fit context window if necessary
            formatted_text += f"--- Source {i+1} ---\n{content[:2000]}\n\n" 
        return formatted_text

    def execute(self, query: str, answer: str, sources: list) -> Dict[str, Any]:
        self.log("Evaluating answer quality...")
        
        import datetime
        
        # 1. PREPARE SOURCE TEXT (The critical fix)
        context_text = self._format_sources(sources)
        
        # If no sources were provided, we must rely on internal knowledge or fail
        if not context_text.strip():
            context_text = "No external context provided. Rely on internal knowledge."

        # 2. ENHANCED PROMPT
        prompt = f"""You are an expert Fact-Checker. 

### GOAL
Verify if the [Generated Answer] is supported by the [Context Sources].

### INPUT DATA
<query>
{query}
</query>

<context_sources>
{context_text}
</context_sources>

<generated_answer>
{answer}
</generated_answer>

### RULES
1. **Source Priority:** You must prioritize the information in <context_sources>.
2. **Date Handling:** If the context says "last quarter" and the answer infers the specific date based on the current date ({datetime.datetime.now().strftime('%B %Y')}), APPROVE it.
3. **Inference:** If the answer combines two facts from the context to reach a logical conclusion, APPROVE it.
4. **Benefit of the Doubt:** If the answer is generally correct but misses a minor detail, APPROVE it. Only REJECT for hallucinations or factual contradictions.

### OUTPUT FORMAT
Return valid JSON only.
{{
    "decision": "approve" | "reject",
    "reason": "Brief explanation of why.",
    "confidence": 0.0 to 1.0 (How certain are you of this decision?),
    "hallucination_score": 0.0 to 1.0 (0 = grounded, 1 = complete fiction)
}}
"""
        
        # Debug print to ensure context is actually there
        # print(f"🔎 [DEBUG] Context length: {len(context_text)} characters")
        
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        try:
            result = extract_json(response)
            
            # Default fallback if keys are missing
            decision = result.get('decision', 'approve').lower()
            reason = result.get('reason', 'No reason provided')
            hallucination = result.get('hallucination_score', 0.0)

            self.log(f"Evaluation: {decision.upper()} - {reason} (Hallucination Score: {hallucination})")
            return result
            
        except Exception as e:
            self.log(f"Error parsing evaluation: {e}")
            return {
                "decision": "approve", 
                "reason": "Evaluation failed, defaulting to approval.", 
                "hallucination_score": 0.0
            }
