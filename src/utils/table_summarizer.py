"""
Table Summarizer using Groq API
Generates concise summaries of tables for efficient embedding and retrieval
"""

import os
import logging
import time
from typing import List, Dict, Optional
from groq import Groq
import tiktoken

logger = logging.getLogger(__name__)


class GroqTableSummarizer:
    """
    Summarizes tables using Groq's fast LLM inference
    
    Uses llama-3.1-8b-instant for cost-effective and fast summarization
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "llama-3.1-8b-instant",
        max_summary_length: int = 300,
        rate_limit_rpm: int = 300
    ):
        """
        Initialize Groq summarizer
        
        Args:
            api_key: Groq API key (or from GROQ_API_KEY env var)
            model: Model to use for summarization
            max_summary_length: Maximum characters in summary
            rate_limit_rpm: Requests per minute limit
        """
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("Groq API key must be provided or set in GROQ_API_KEY environment variable")
        
        self.client = Groq(api_key=self.api_key)
        self.model = model
        self.max_summary_length = max_summary_length
        self.rate_limit_rpm = rate_limit_rpm
        
        # Track requests for rate limiting
        self.request_times = []
        
        # Initialize tokenizer for cost calculation
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")  # Close enough for estimation
        except:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        logger.info(f"Initialized GroqTableSummarizer with model: {model}")
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        
        # Remove requests older than 60 seconds
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # If we're at the limit, wait
        if len(self.request_times) >= self.rate_limit_rpm:
            sleep_time = 60 - (current_time - self.request_times[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, waiting {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
                self.request_times = []
        
        self.request_times.append(current_time)
    
    def summarize_table(
        self, 
        table_markdown: str, 
        context: Optional[Dict] = None,
        max_retries: int = 3
    ) -> str:
        """
        Summarize a single table
        
        Args:
            table_markdown: Table in markdown format
            context: Additional context (section name, filing type, etc.)
            max_retries: Number of retry attempts
        
        Returns:
            Summary text
        """
        # Build prompt with context
        prompt = self._build_summary_prompt(table_markdown, context)
        
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a financial analyst expert at summarizing tables from SEC filings concisely and accurately."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=200,  # Increased for longer summaries with context
                    temperature=0.3,  # Low temperature for consistent summaries
                )
                
                summary = response.choices[0].message.content.strip()
                
                # Truncate if needed
                if len(summary) > self.max_summary_length:
                    summary = summary[:self.max_summary_length] + "..."
                
                logger.debug(f"Generated summary ({len(summary)} chars) for table")
                return summary
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to summarize table after {max_retries} attempts")
                    return f"[Table: {context.get('section_name', 'Unknown')} - Summary unavailable]"
        
        return "[Summary unavailable]"
    
    def summarize_batch(
        self, 
        tables: List[Dict],
        show_progress: bool = True
    ) -> List[str]:
        """
        Summarize multiple tables with progress tracking
        
        Args:
            tables: List of dicts with 'table_markdown' and optional 'context'
            show_progress: Show progress bar
        
        Returns:
            List of summaries
        """
        summaries = []
        
        for i, table_data in enumerate(tables):
            if show_progress and (i + 1) % 10 == 0:
                logger.info(f"Summarized {i + 1}/{len(tables)} tables...")
            
            summary = self.summarize_table(
                table_markdown=table_data.get('table_markdown', ''),
                context=table_data.get('context', {})
            )
            summaries.append(summary)
        
        logger.info(f"Completed summarizing {len(tables)} tables")
        return summaries
    
    def _build_summary_prompt(
        self, 
        table_markdown: str, 
        context: Optional[Dict] = None
    ) -> str:
        """Build the summarization prompt with comprehensive context"""
        context = context or {}
        
        # Count tokens to estimate cost
        tokens = len(self.tokenizer.encode(table_markdown))
        
        # Build comprehensive context string with all available metadata
        context_parts = []
        
        if context.get('company'):
            context_parts.append(f"Company: {context['company']}")
        if context.get('ticker'):
            context_parts.append(f"Ticker: {context['ticker']}")
        if context.get('filing_type'):
            context_parts.append(f"Filing Type: {context['filing_type']}")
        if context.get('filing_year'):
            context_parts.append(f"Filing Year: {context['filing_year']}")
        if context.get('fiscal_quarter'):
            context_parts.append(f"Fiscal Quarter: Q{context['fiscal_quarter']}")
        if context.get('section'):
            context_parts.append(f"Section: {context['section']}")
        if context.get('section_name'):
            context_parts.append(f"Section Name: {context['section_name']}")
        
        context_str = "\n".join(context_parts)
        
        prompt = f"""Context:
{context_str}

Task: Analyze and summarize the table below.

First, provide a brief explanation (1 sentence) of what this table represents in the context of the filing.
Then, summarize the table data in 2-3 clear sentences. Focus on:
1. What specific data the table shows (e.g., revenue breakdown, expenses, assets)
2. Key values, trends, or notable figures
3. Any significant changes, comparisons, or patterns

Table ({tokens} tokens):
{table_markdown}

Provide your response in this format:
[Table Explanation]: [One sentence explaining what this table is]
[Summary]: [2-3 sentences summarizing the data]

Max length: {self.max_summary_length} characters:"""
        
        return prompt
    
    def estimate_cost(self, num_tables: int, avg_tokens_per_table: int = 500) -> Dict:
        """
        Estimate the cost of summarizing tables
        
        Args:
            num_tables: Number of tables to summarize
            avg_tokens_per_table: Average tokens per table
        
        Returns:
            Dict with cost breakdown
        """
        # Groq pricing (as of Dec 2024)
        input_cost_per_m = 0.05  # $0.05 per 1M input tokens
        output_cost_per_m = 0.08  # $0.08 per 1M output tokens
        
        total_input_tokens = num_tables * avg_tokens_per_table
        total_output_tokens = num_tables * 100  # ~100 tokens per summary
        
        input_cost = (total_input_tokens / 1_000_000) * input_cost_per_m
        output_cost = (total_output_tokens / 1_000_000) * output_cost_per_m
        total_cost = input_cost + output_cost
        
        return {
            'num_tables': num_tables,
            'input_tokens': total_input_tokens,
            'output_tokens': total_output_tokens,
            'input_cost_usd': round(input_cost, 4),
            'output_cost_usd': round(output_cost, 4),
            'total_cost_usd': round(total_cost, 4)
        }


if __name__ == "__main__":
    # Test the summarizer
    logging.basicConfig(level=logging.INFO)
    
    # Example table
    test_table = """
| Product Category | Q1 2024 | Q2 2024 | Q3 2024 | YoY Change |
|------------------|---------|---------|---------|------------|
| iPhone           | 45.2B   | 49.3B   | 52.1B   | +15%       |
| Mac              | 7.5B    | 8.2B    | 9.1B    | +8%        |
| iPad             | 5.6B    | 6.1B    | 6.8B    | +12%       |
| Services         | 21.2B   | 23.1B   | 24.9B   | +18%       |
"""
    
    context = {
        'section_name': "Management's Discussion and Analysis",
        'filing_type': '10-K',
        'company': 'Apple Inc.'
    }
    
    try:
        summarizer = GroqTableSummarizer()
        summary = summarizer.summarize_table(test_table, context)
        print(f"\nTable Summary:\n{summary}\n")
        
        # Cost estimate
        cost_est = summarizer.estimate_cost(num_tables=3000, avg_tokens_per_table=500)
        print(f"Cost Estimate for 3000 tables:")
        print(f"  Total: ${cost_est['total_cost_usd']:.4f}")
        
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set GROQ_API_KEY environment variable")
