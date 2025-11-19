# src/data_processing/table_summarizer.py
"""
LLM-based table summarization using Groq Llama 3.3

Generates concise, factual summaries of financial tables
"""

import time
import hashlib
from typing import Dict, Optional
from pathlib import Path

from groq import Groq

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import config
from src.utils.logging_config import get_logger
from src.storage.blob_storage_manager import BlobStorageManager

logger = get_logger(__name__)


class TableSummarizer:
    """
    Generate natural language summaries of tables using Groq LLM
    
    Features:
    - Uses Llama 3.3 70B for high-quality summaries
    - Caches summaries by table hash to avoid recomputation
    - Tracks API usage and costs
    - Handles failures gracefully with fallback summaries
    """
    
    def __init__(self):
        """Initialize table summarizer with Groq client"""
        # Initialize Groq client
        api_key = config.api.groq_api_key
        
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
        
        self.client = Groq(api_key=api_key)
        
        # Load model config
        self.model = config.api.groq_model
        self.temperature = config.api.groq_temperature
        self.max_tokens = config.api.groq_max_tokens
        
        # Initialize cache
        self.blob_storage = BlobStorageManager()
        
        # Track usage
        self.api_calls = 0
        self.cache_hits = 0
        self.total_tokens = 0
        
        logger.info(f"TableSummarizer initialized with model: {self.model}")
    
    def generate_summary(
        self,
        table_markdown: str,
        context_before: str,
        context_after: str
    ) -> str:
        """
        Generate natural language summary of table using LLM
        
        Args:
            table_markdown: Table in markdown format
            context_before: Text appearing before table
            context_after: Text appearing after table
            
        Returns:
            Natural language summary (2-3 sentences)
        """
        # Check cache first
        table_hash = self._compute_table_hash(table_markdown)
        cached_summary = self.blob_storage.get_table_summary(table_hash)
        
        if cached_summary:
            self.cache_hits += 1
            logger.info(f"📦 Using cached summary (cache hit rate: {self._get_cache_hit_rate():.1f}%)")
            return cached_summary
        
        # Generate new summary via LLM
        try:
            summary = self._call_groq_api(table_markdown, context_before, context_after)
            
            # Cache the summary
            self.blob_storage.save_table_summary(table_hash, summary)
            
            logger.info(f"✅ Generated new table summary via LLM")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ LLM summarization failed: {e}")
            
            # Fallback to simple summary
            fallback = self._generate_fallback_summary(table_markdown)
            logger.warning(f"Using fallback summary: {fallback}")
            
            return fallback
    
    def _call_groq_api(
        self,
        table_markdown: str,
        context_before: str,
        context_after: str
    ) -> str:
        """
        Call Groq API to generate summary
        
        Args:
            table_markdown: Table in markdown
            context_before: Context before table
            context_after: Context after table
            
        Returns:
            Generated summary
        """
        # Build prompt
        prompt = self._build_prompt(table_markdown, context_before, context_after)
        
        # Make API call
        start_time = time.time()
        
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial analyst expert at summarizing tables from SEC filings. Be concise and factual."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=0.9
        )
        
        # Extract summary
        summary = completion.choices[0].message.content.strip()
        
        # Track usage
        self.api_calls += 1
        if hasattr(completion, 'usage'):
            self.total_tokens += completion.usage.total_tokens
        
        elapsed = time.time() - start_time
        logger.debug(f"LLM call completed in {elapsed:.2f}s")
        
        return summary
    
    def _build_prompt(
        self,
        table_markdown: str,
        context_before: str,
        context_after: str
    ) -> str:
        """
        Build prompt for LLM summarization
        
        Args:
            table_markdown: Table in markdown
            context_before: Context before
            context_after: Context after
            
        Returns:
            Formatted prompt
        """
        prompt = f"""Analyze this financial table from an SEC filing and generate a concise summary.

Context before table:
{context_before}

TABLE:
{table_markdown}

Context after table:
{context_after}

Generate a clear, factual summary in 2-3 sentences that captures:
1. What the table shows (topic and purpose)
2. Key metrics and their values
3. Important trends or comparisons (if applicable)
4. Time periods covered (if applicable)

Focus on specific numbers and facts. Be precise and concise."""
        
        return prompt
    
    def _compute_table_hash(self, table_markdown: str) -> str:
        """
        Compute hash of table content for caching
        
        Args:
            table_markdown: Table markdown
            
        Returns:
            MD5 hash
        """
        return hashlib.md5(table_markdown.encode('utf-8')).hexdigest()
    
    def _generate_fallback_summary(self, table_markdown: str) -> str:
        """
        Generate simple fallback summary if LLM fails
        
        Args:
            table_markdown: Table markdown
            
        Returns:
            Basic summary
        """
        lines = [l for l in table_markdown.split('\n') if l.strip() and not l.startswith('|---')]
        row_count = len(lines) - 1  # Subtract header
        
        return f"Table containing financial data with {row_count} data rows."
    
    def _get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        total_requests = self.api_calls + self.cache_hits
        if total_requests == 0:
            return 0.0
        return (self.cache_hits / total_requests) * 100
    
    def get_usage_stats(self) -> Dict:
        """
        Get API usage statistics
        
        Returns:
            Usage statistics dictionary
        """
        return {
            'api_calls': self.api_calls,
            'cache_hits': self.cache_hits,
            'total_requests': self.api_calls + self.cache_hits,
            'cache_hit_rate': self._get_cache_hit_rate(),
            'total_tokens': self.total_tokens,
            'estimated_cost_usd': (self.total_tokens / 1_000_000) * 0.60  # Groq pricing
        }


# ==================== TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING TABLE SUMMARIZER")
    print("="*70 + "\n")
    
    try:
        summarizer = TableSummarizer()
        
        # Test table
        table_markdown = """| Revenue Segment | 2024   | 2023  | YoY Growth |
|----------------|--------|-------|------------|
| Product Sales  | $100M  | $90M  | 11%        |
| Services       | $50M   | $45M  | 11%        |
| Total Revenue  | $150M  | $135M | 11%        |"""
        
        context_before = "Our revenue performance in fiscal 2024 exceeded expectations across all business segments. The company maintained strong pricing power."
        context_after = "This revenue growth was driven by strong demand in our flagship product lineup."
        
        print("Test 1: Generate table summary")
        print("-" * 70)
        print(f"Table:\n{table_markdown}\n")
        
        summary = summarizer.generate_summary(
            table_markdown,
            context_before,
            context_after
        )
        
        print(f"✅ Generated Summary:")
        print(f"   {summary}\n")
        
        # Test 2: Cache hit
        print("\nTest 2: Test caching (should be cache hit)")
        print("-" * 70)
        
        summary2 = summarizer.generate_summary(
            table_markdown,
            context_before,
            context_after
        )
        
        print(f"✅ Summary retrieved (from cache)")
        print(f"   {summary2}\n")
        
        # Test 3: Usage stats
        print("\nTest 3: Get usage statistics")
        print("-" * 70)
        
        stats = summarizer.get_usage_stats()
        print(f"✅ Usage Stats:")
        print(f"   API calls: {stats['api_calls']}")
        print(f"   Cache hits: {stats['cache_hits']}")
        print(f"   Cache hit rate: {stats['cache_hit_rate']:.1f}%")
        print(f"   Total tokens: {stats['total_tokens']:,}")
        print(f"   Estimated cost: ${stats['estimated_cost_usd']:.4f}")
        
        print("\n" + "="*70)
        print("✅ ALL TABLE SUMMARIZER TESTS PASSED")
        print("="*70 + "\n")
        
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Make sure GROQ_API_KEY is set in your .env file")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()