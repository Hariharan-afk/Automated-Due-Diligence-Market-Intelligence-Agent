import sys
sys.path.append('.')

import json
from typing import List
from src.agents.base_agent import BaseAgent
from src.tools.gcp_client import get_gcp_client
from src.config import AGENT_CONFIG

class AnalyserAgent(BaseAgent):
    """Decomposes complex queries into sub-queries"""
    
    def __init__(self):
        super().__init__("Analyser")
        self.client = get_gcp_client()
        self.temperature = AGENT_CONFIG["analyser"]["temperature"]
    
    def execute(self, user_query: str) -> List[str]:
        """
        Decompose user query into 3-5 sub-queries
        
        Args:
            user_query: User's question
        
        Returns:
            List of sub-queries
        """
        self.log(f"Decomposing query: '{user_query}'")
        
        prompt = f"""You are a financial research analyst. Break this query into 3-5 specific sub-queries.

User Query: {user_query}

Requirements:
- Each sub-query should be independent and focused
- Cover all aspects of the original query
- Suitable for document retrieval

Return ONLY a JSON array of sub-queries.
Example: ["sub-query 1", "sub-query 2", "sub-query 3"]"""
        
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        # Parse JSON
        content = response.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
        
        sub_queries = json.loads(content)
        
        self.log(f"Generated {len(sub_queries)} sub-queries:")
        for i, sq in enumerate(sub_queries, 1):
            self.log(f"  {i}. {sq}")
        
        return sub_queries
