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
    
    def execute(self, query: str, answer: str, sources: list) -> Dict[str, Any]:
        """
        Evaluate the generated answer
        
        Args:
            query: Original user query
            answer: Generated answer
            sources: List of sources used
            
        Returns:
            Dict with approval status and feedback
        """
        self.log("Evaluating answer quality...")
        
        prompt = f"""You are a Quality Assurance Auditor for financial reports. Evaluate this answer.

Original Query: {query}
Generated Answer: {answer}
Number of Sources: {len(sources)}

CRITICAL HALLUCINATION CHECK:
1. Extract the company names mentioned in the QUERY
2. Extract the company names mentioned in the ANSWER
3. If they are DIFFERENT companies, this is a SEVERE HALLUCINATION

Example:
- Query: "Compare Apple and Microsoft"
- Answer talks about: "Microsoft and Tesla"
- Result: SEVERE HALLUCINATION (hallucination_score = 0.9+)

Criteria:
1. Completeness: Does it answer the specific query?
2. Factual Support: Is it based on the provided sources?
3. Hallucinations: Any unsupported claims? Wrong companies?

Decision:
- 'approve': High quality, ready for user.
- 'reject': Missing key info, vague, or hallucinations.

Also provide:
1. A confidence score from 0.0 to 1.0 based on answer quality.
2. A hallucination_score from 0.0 to 1.0 (0.0 = no hallucinations, 1.0 = severe hallucinations) - check if the answer addresses the EXACT query or if it answers a different question.

Return ONLY a JSON object.
Example: {{"decision": "approve", "reason": "Comprehensive answer with good citations.", "feedback": "", "confidence": 0.85, "hallucination_score": 0.1}}
OR
Example: {{"decision": "reject", "reason": "Answer compares wrong companies - user asked about Apple vs Microsoft but answer discusses Microsoft vs Tesla.", "feedback": "Focus on the exact companies mentioned in the query.", "confidence": 0.3, "hallucination_score": 0.9}}"""
        
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        try:
            # Parse JSON
            result = extract_json(response)
            confidence = result.get('confidence', 0.5)
            hallucination = result.get('hallucination_score', 0.0)
            self.log(f"Evaluation: {result['decision'].upper()} - {result['reason']} (Confidence: {confidence:.2f}, Hallucination: {hallucination:.2f})")
            return result
        except Exception as e:
            self.log(f"Error parsing evaluation: {e}")
            # Fallback to approve to avoid infinite loops on error
            return {"decision": "approve", "reason": "Error in evaluation, defaulting to approve.", "feedback": "", "confidence": 0.5, "hallucination_score": 0.0}
