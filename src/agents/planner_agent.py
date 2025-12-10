import sys
sys.path.append('.')

from typing import List, Dict, Any
from src.agents.base_agent import BaseAgent
from src.tools.local_client import get_local_client
from src.config import AGENT_CONFIG
from src.utils.helpers import extract_json

class PlannerAgent(BaseAgent):
    """Decomposes complex queries into prioritized strategic sub-queries"""
    
    def __init__(self):
        super().__init__("Planner")
        self.client = get_local_client()
        self.temperature = AGENT_CONFIG["planner"]["temperature"]
    
    def execute(self, user_query: str, context: str = "") -> List[str]:
        """
        Decompose user query into 3-5 sub-queries
        
        Args:
            user_query: User's question
            context: Optional context from previous attempts (for re-planning)
        
        Returns:
            List of sub-queries
        """
        self.log(f"Planning research for: '{user_query}'")
        
        prompt = f"""You are a Strategic Research Planner. Break down the user's query into specific, actionable sub-queries.

User Query: {user_query}

AVAILABLE DATA SOURCES:
1. SEC Filings (Form 10-K, 10-Q): Financial statements, revenue, risks, management discussion. Best for hard numbers.
2. News Articles: Market sentiment, product launches, stock performance, recent events. Best for trends and updates.
3. Wikipedia: General company history, business model, competitor overview. Best for context.

CONSTRAINTS:
1. Generate exactly 5 sub-queries.
2. Ensure sub-queries are answerable by the sources above.
3. Do NOT ask for "interviews," "expert opinions," or "proprietary data" (we don't have these).
4. Focus on facts, figures, and public information.
5. Prioritize the specific companies and years mentioned in the user query.

Output Format:
Return ONLY a JSON object with a "sub_queries" key containing a list of strings.
Example: {{"sub_queries": ["Revenue of Apple in 2023 from SEC filings", "Recent news about Microsoft AI market share", ...]}}"""
        
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        try:
            # Parse JSON
            parsed_json = extract_json(response)
            
            # Handle both dict ({"sub_queries": [...]}) and list (["...", "..."]) formats
            if isinstance(parsed_json, dict) and "sub_queries" in parsed_json:
                sub_queries = parsed_json["sub_queries"]
            elif isinstance(parsed_json, list):
                sub_queries = parsed_json
            else:
                self.log(f"Unexpected JSON format: {parsed_json}")
                return [user_query]
            
            self.log(f"Generated {len(sub_queries)} sub-queries:")
            for i, sq in enumerate(sub_queries, 1):
                self.log(f"  {i}. {sq}")
            
            return sub_queries
        except Exception as e:
            self.log(f"Error parsing plan: {e}")
            # Fallback
            return [user_query]
