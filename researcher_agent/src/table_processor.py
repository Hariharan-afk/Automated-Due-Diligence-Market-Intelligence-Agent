# researcher_agent/src/table_processor.py
import time
from typing import Dict, List
from groq import Groq

from utils.config import config


class TableProcessor:
    """Handles LLM-based table summarization"""
    
    def __init__(self):
        self.llm_client = Groq(api_key=config.GROQ_API_KEY)
        self.model = config.TABLE_SUMMARY_MODEL
        self.temperature = config.TABLE_SUMMARY_TEMPERATURE
        self.max_tokens = config.TABLE_SUMMARY_MAX_TOKENS
    
    def generate_table_summary(
        self,
        table_content: str,
        context_before: str,
        context_after: str
    ) -> str:
        """
        Generate a natural language summary of a table using LLM
        
        Args:
            table_content: The table content in text format
            context_before: Text appearing before the table
            context_after: Text appearing after the table
            
        Returns:
            Natural language summary of the table
        """
        prompt = f"""You are analyzing a financial table from an SEC filing. Generate a concise, informative summary that captures:
1. What the table shows (topic/purpose)
2. Key metrics and their values
3. Important trends or comparisons
4. Time periods covered (if applicable)

Context before table:
{context_before}

TABLE CONTENT:
{table_content}

Context after table:
{context_after}

Provide a clear, factual summary in 2-3 sentences that would help someone searching for this information. Focus on the numbers and trends."""

        try:
            response = self.llm_client.chat.completions.create(
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
                max_tokens=self.max_tokens
            )
            
            summary = response.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            print(f"✗ Error generating table summary: {e}")
            # Fallback: simple description
            return f"Table containing financial data with {len(table_content.split(chr(10)))} rows."
    
    def process_tables(
        self,
        components: List[Dict],
        get_context_fn
    ) -> List[Dict]:
        """
        Process all tables in components list with LLM summaries
        
        Args:
            components: List of document components
            get_context_fn: Function to get surrounding context for a table
            
        Returns:
            List of enriched table dictionaries
        """
        processed_tables = []
        table_count = sum(1 for c in components if c['type'] == 'table')
        
        print(f"Processing {table_count} tables with LLM summaries...")
        
        for i, component in enumerate(components):
            if component['type'] != 'table':
                continue
            
            # Get surrounding context
            context_before, context_after = get_context_fn(components, i)
            
            # Generate summary
            print(f"  Generating summary for table {i+1}/{len(components)}...", end=" ")
            summary = self.generate_table_summary(
                component['content'],
                context_before,
                context_after
            )
            print("✓")
            
            # Create enriched table data
            table_data = {
                **component,
                'summary': summary,
                'context_before': context_before,
                'context_after': context_after,
                'component_index': i
            }
            
            processed_tables.append(table_data)
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        return processed_tables


# # Example usage
# if __name__ == "__main__":
#     from researcher_agent.src.document_processor import DocumentProcessor
    
#     processor = DocumentProcessor()
#     table_processor = TableProcessor()
    
#     sample_text = """
#     Our revenue performance improved significantly in fiscal 2024.
    
#     ##TABLE_START
#     Revenue by Segment (in millions)
#                         2024      2023      2022
#     Product Sales     $45,200   $42,100   $39,800
#     Services          $12,300   $11,500   $10,200
#     Total Revenue     $57,500   $53,600   $50,000
#     ##TABLE_END
    
#     The growth was driven by strong demand in our product lineup and expanding service offerings.
#     """
    
#     components = processor.parse_section_components(sample_text)
#     processed_tables = table_processor.process_tables(
#         components,
#         processor.get_surrounding_context
#     )
    
#     for table in processed_tables:
#         print(f"\nTable Summary:")
#         print(table['summary'])
#         print(f"\nOriginal Table:")
#         print(table['content'][:200])