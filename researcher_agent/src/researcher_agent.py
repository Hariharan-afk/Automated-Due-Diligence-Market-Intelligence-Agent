# researcher_agent/src/researcher_agent.py
from typing import Dict, List, Optional
from groq import Groq

from utils.config import config
from researcher_agent.src.query_parser import QueryParser, CompanyResolver
from researcher_agent.src.data_fetcher import SECDataFetcher
from researcher_agent.src.document_processor import DocumentProcessor
from researcher_agent.src.table_processor import TableProcessor
from researcher_agent.src.embeddings_manager import EmbeddingsManager
from researcher_agent.src.metadata_manager import MetadataManager


class ResearcherAgent:
    """
    Main orchestrator for the Researcher Agent
    Handles the complete pipeline from query to indexed chunks
    """
    
    def __init__(self):
        print("\n" + "="*60)
        print("Initializing Researcher Agent...")
        print("="*60 + "\n")
        
        # Initialize all components
        self.llm_client = Groq(api_key=config.QUERY_PARSER_MODEL_API_KEY)
        self.query_parser = QueryParser(self.llm_client)
        self.company_resolver = CompanyResolver()
        self.data_fetcher = SECDataFetcher()
        self.document_processor = DocumentProcessor()
        self.table_processor = TableProcessor()
        self.embeddings_manager = EmbeddingsManager()
        self.metadata_manager = MetadataManager()
        
        print("✓ All components initialized\n")
    
    def process_query(self, user_query: str) -> Dict:
        """
        Process a user query and return search results
        
        Args:
            user_query: Natural language query from user
            
        Returns:
            Dictionary containing processed results
        """
        print(f"\n{'='*60}")
        print(f"Processing Query: {user_query}")
        print(f"{'='*60}\n")
        
        # Step 1: Parse query
        print("Step 1: Parsing query...")
        parsed_query = self.query_parser.parse_query(user_query)
        print(f"  Extracted company: {parsed_query['company']}")
        print(f"  Analysis type: {parsed_query['analysis_type']}")
        print(f"  Time horizon: {parsed_query['time_horizon']}\n")
        
        # Step 2: Resolve company
        print("Step 2: Resolving company...")
        try:
            company_info = self.company_resolver.resolve(parsed_query['company'])
            print(f"  ✓ Resolved: {company_info['title']} ({company_info['ticker']})\n")
        except ValueError as e:
            print(f"  ✗ {e}")
            return {'error': str(e)}
        
        # Step 3: Process filing
        result = self.process_company_filing(
            company_info['ticker'],
            filing_type="10-K"  # Can be extended based on parsed_query
        )
        
        return {
            'query': parsed_query,
            'company': company_info,
            'processing_result': result
        }
    
    def process_company_filing(
        self,
        ticker: str,
        filing_type: str = "10-K"
    ) -> Dict:
        """
        Complete pipeline: Fetch, process, and index a company filing
        
        Args:
            ticker: Company ticker symbol
            filing_type: Type of filing to process
            
        Returns:
            Dictionary with processing statistics
        """
        print(f"\n{'='*60}")
        print(f"Processing {filing_type} for {ticker}")
        print(f"{'='*60}\n")
        
        # Step 3: Fetch filing
        print("Step 3: Fetching filing from SEC...")
        filing_data = self.data_fetcher.fetch_filing_with_sections(ticker, filing_type)
        
        if not filing_data:
            return {'error': f'Failed to fetch {filing_type} for {ticker}'}
        
        filing_metadata = filing_data['filing_metadata']
        
        # Step 4: Check if already processed
        print("\nStep 4: Checking if filing already processed...")
        if self.metadata_manager.check_filing_exists(filing_metadata['accessionNo']):
            print(f"  ✓ Filing already processed and indexed")
            return {
                'status': 'already_processed',
                'accession_number': filing_metadata['accessionNo']
            }
        
        # Step 5-10: Process all sections
        all_chunks = []
        sections_processed = []
        
        for section_code, section_text in filing_data['sections'].items():
            print(f"\n{'─'*60}")
            print(f"Processing Section {section_code}")
            print(f"{'─'*60}\n")
            
            # Step 5: Parse components
            print("Step 5: Parsing section components...")
            components = self.document_processor.parse_section_components(section_text)
            table_count = sum(1 for c in components if c['type'] == 'table')
            text_count = sum(1 for c in components if c['type'] == 'text')
            print(f"  Found {table_count} tables and {text_count} text segments\n")
            
            # Step 6: Process tables with LLM
            if table_count > 0:
                print("Step 6: Generating table summaries with LLM...")
                processed_tables = self.table_processor.process_tables(
                    components,
                    self.document_processor.get_surrounding_context
                )
                print()
            else:
                processed_tables = []
                print("Step 6: No tables to process\n")
            
            # Step 7-8: Create chunks and generate embeddings
            print("Step 7-8: Creating chunks and generating embeddings...")
            section_chunks = self.embeddings_manager.create_chunks_with_embeddings(
                components,
                processed_tables,
                section_code,
                filing_metadata
            )
            print(f"  Created {len(section_chunks)} chunks")
            print(f"    - Tables: {sum(1 for c in section_chunks if c['type'] == 'table')}")
            print(f"    - Text: {sum(1 for c in section_chunks if c['type'] == 'text')}\n")
            
            all_chunks.extend(section_chunks)
            sections_processed.append(section_code)
        
        # Step 9: Store in Qdrant
        print(f"\n{'='*60}")
        print(f"Step 9: Storing chunks in vector database")
        print(f"{'='*60}\n")
        total_stored = self.embeddings_manager.store_in_qdrant(all_chunks)
        
        # Step 10: Update metadata
        print(f"\nStep 10: Updating metadata database...")
        self.metadata_manager.save_filing_metadata(
            filing_metadata,
            sections_processed,
            total_stored
        )
        
        # Summary
        print(f"\n{'='*60}")
        print(f"✓ PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Company: {filing_metadata['companyName']} ({ticker})")
        print(f"Filing: {filing_type} filed {filing_metadata['filedAt']}")
        print(f"Sections processed: {len(sections_processed)}")
        print(f"Total chunks created: {total_stored}")
        print(f"  - Tables: {sum(1 for c in all_chunks if c['type'] == 'table')}")
        print(f"  - Text: {sum(1 for c in all_chunks if c['type'] == 'text')}")
        print(f"{'='*60}\n")
        
        return {
            'status': 'success',
            'ticker': ticker,
            'filing_type': filing_type,
            'filing_date': filing_metadata['filedAt'],
            'accession_number': filing_metadata['accessionNo'],
            'sections_processed': sections_processed,
            'total_chunks': total_stored,
            'table_chunks': sum(1 for c in all_chunks if c['type'] == 'table'),
            'text_chunks': sum(1 for c in all_chunks if c['type'] == 'text')
        }
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for relevant chunks
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of search results
        """
        return self.embeddings_manager.search(query, limit)


# Main execution
if __name__ == "__main__":
    # Initialize agent
    agent = ResearcherAgent()
    
    # Option 1: Process a specific company
    # result = agent.process_company_filing("AAPL", "10-K")
    
    # Option 2: Process from natural language query
    result = agent.process_query(
        "Analyze AMD's financial health and risk factors from their latest annual report"
    )
    
    print("\nFinal Result:")
    print(result)