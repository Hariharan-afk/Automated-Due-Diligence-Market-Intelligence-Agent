import sys
sys.path.append('.')

from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.tools.local_client import get_local_client
from src.config import AGENT_CONFIG
from src.utils.helpers import extract_json

class OrchestratorAgent(BaseAgent):
    """Classifies query and determines workflow routing"""
    
    def __init__(self):
        super().__init__("Orchestrator")
        self.client = get_local_client()
        self.temperature = AGENT_CONFIG["orchestrator"]["temperature"]
    
    def execute(self, user_query: str) -> Dict[str, Any]:
        """
        Analyze query to determine type and complexity
        
        Args:
            user_query: User's question
            
        Returns:
            Dict containing classification and routing info
        """
        self.log(f"Analyzing query: '{user_query}'")
        
        prompt = f"""You are a senior workflow orchestrator. Analyze this query and determine the best workflow.

User Query: {user_query}

Classify into:
1. Query Type: 'financial', 'risk', 'market', 'general'
2. Complexity: 'simple' (direct answer), 'complex' (needs research)
3. Workflow: 'standard_research' (default for now)

Return ONLY a JSON object.
Example: {{"type": "financial", "complexity": "complex", "workflow": "standard_research"}}"""
        
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        try:
            # Parse JSON
            result = extract_json(response)
            self.log(f"Classification: {result}")
            return result
        except Exception as e:
            self.log(f"Error parsing orchestration result: {e}")
            # Fallback
            return {"type": "general", "complexity": "complex", "workflow": "standard_research"}
