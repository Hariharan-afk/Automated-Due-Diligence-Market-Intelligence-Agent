import sys
sys.path.append('.')

from typing import List, Dict
import numpy as np
from src.agents.base_agent import BaseAgent
from src.tools.local_client import get_local_client
from src.config import AGENT_CONFIG
from src.utils.helpers import extract_json

class SynthesiserAgent(BaseAgent):
    """Generates comprehensive answer from retrieved information"""
    
    def __init__(self):
        super().__init__("Synthesiser")
        self.client = get_local_client()
        self.temperature = AGENT_CONFIG["synthesiser"]["temperature"]
    
    def execute(self, query: str, chunks: List[Dict]) -> Dict:
        """
        Generate final answer with citations
        
        Args:
            query: Original user query
            chunks: Retrieved chunks from Researcher
        
        Returns:
            {
                'answer': str,
                'sources': List[Dict],
                'confidence': float
            }
        """
        self.log("Generating answer...")
        
        if not chunks:
            return {
                'answer': "I couldn't find relevant information to answer your query.",
                'sources': [],
                'confidence': 0.0
            }
        
        # Format context
        context = self._format_context(chunks)
        
        prompt = f"""You are a Senior Financial Analyst. Synthesize the provided research chunks into a comprehensive answer for the user's query.

User Query: {query}

Research Data:
{context}

Instructions:
1. Answer the query DIRECTLY based on the provided data.
2. Structure your answer as a professional financial report (Markdown format).
3. You MUST use the following structure:
   - **Executive Summary**: A concise 2-3 sentence summary of the answer.
   - **Key Findings**: Bullet points highlighting the most important numbers and facts.
   - **Detailed Analysis**: In-depth explanation of the data, trends, and context.
   - **Data Gaps/Limitations**: State limitations ONLY if the data is completely absent. Do not pedantically list every missing minor detail.
4. Use bold text for key figures (e.g., **$102.5 billion**).
5. Maintain a professional, objective tone.
6. Do NOT use conversational filler.
7. Do NOT include a "Sources" section at the end (this will be added automatically).

6. Output Format:
   Return ONLY the report text in Markdown.

Grounding Rules:
- You are a RAG (Retrieval-Augmented Generation) engine, NOT a creative writer.
- If a specific number (like "$4.9 billion") is not in the provided [Research Data], DO NOT USE IT.
- Do not use your internal training knowledge to fill in gaps. If the data is missing from the context, state that it is unavailable.
- Every claim must be supportable by the provided text.
"""
        
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        # No JSON parsing needed - response IS the report
        final_answer = response

        # Extract sources from chunks
        sources = self._extract_sources(chunks)
        
        self.log(f"Answer generated")
        
        return {
            'answer': final_answer,
            'sources': sources
        }
    
    def _format_context(self, chunks: List[Dict]) -> str:
        """Format chunks into readable context"""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get('metadata', {})
            source_info = f"{metadata.get('company_name', 'Unknown')} - {metadata.get('data_source_type', 'Unknown')} - {metadata.get('fetched_date', 'Unknown')}"
            
            context_parts.append(
                f"[Document {i}] {source_info}\n{chunk['raw_chunk']}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    def _extract_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Extract unique sources"""
        sources = []
        seen = set()
        
        for chunk in chunks:
            metadata = chunk.get('metadata', {})
            source_key = (
                metadata.get('company_name'),
                metadata.get('data_source_type'),
                metadata.get('document_id')
            )
            
            if source_key not in seen:
                seen.add(source_key)
                sources.append({
                    'company': metadata.get('company_name'),
                    'source_type': metadata.get('data_source_type'),
                    'date': metadata.get('fetched_date'),
                    'ticker': metadata.get('ticker'),
                    'content': chunk.get('raw_chunk', '') # CRITICAL FIX: Pass content to Evaluator
                })
        
        return sources