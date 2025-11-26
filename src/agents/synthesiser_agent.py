import sys
sys.path.append('.')

from typing import List, Dict
import numpy as np
from src.agents.base_agent import BaseAgent
from src.tools.gcp_client import chat_completion, get_gcp_client
from src.config import AGENT_CONFIG

class SynthesiserAgent(BaseAgent):
    """Generates comprehensive answer from retrieved information"""
    
    def __init__(self):
        super().__init__("Synthesiser")
        self.client = get_gcp_client()
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
        
        prompt = f"""You are a financial analyst. Answer the query based ONLY on the provided documents.

User Query: {query}

Retrieved Documents:
{context}

Instructions:
1. Provide a comprehensive answer
2. Cite sources using [Company - Source - Date] format
3. If information conflicts, mention both perspectives
4. Be objective and factual

Answer:"""
        
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        # Extract sources
        sources = self._extract_sources(chunks)
        
        # Calculate confidence
        confidence = np.mean([c.get('final_score', 0) for c in chunks])
        
        self.log(f"Answer generated (confidence: {confidence:.2f})")
        
        return {
            'answer': response,
            'sources': sources,
            'confidence': float(confidence)
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
                    'ticker': metadata.get('ticker')
                })
        
        return sources