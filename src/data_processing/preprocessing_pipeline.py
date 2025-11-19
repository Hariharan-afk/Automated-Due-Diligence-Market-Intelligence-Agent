# src/data_processing/preprocessing_pipeline.py
"""
Main preprocessing pipeline orchestrator

Coordinates complete preprocessing workflow from raw sections to enriched chunks
"""

from typing import Dict, List, Optional, Any, Union
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_processing.document_parser import DocumentParser
from src.data_processing.table_extractor import TableExtractor
from src.data_processing.table_summarizer import TableSummarizer
from src.data_processing.text_cleaner import TextCleaner
from src.data_processing.chunking_engine import ChunkingEngine
from src.data_processing.metadata_enricher import MetadataEnricher
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class PreprocessingPipeline:
    """
    Orchestrates complete preprocessing workflow
    
    Workflow:
    1. Parse sections into components (tables + text)
    2. Process tables: extract → summarize → enrich
    3. Process text: clean → chunk → enrich
    4. Return all enriched chunks
    
    Features:
    - Section-aware chunk sizing
    - Table context enrichment
    - LLM-based table summaries
    - Comprehensive metadata
    """
    
    def __init__(self):
        """Initialize all preprocessing components"""
        logger.info("Initializing PreprocessingPipeline...")
        
        self.parser = DocumentParser()
        self.table_extractor = TableExtractor()
        self.table_summarizer = TableSummarizer()
        self.text_cleaner = TextCleaner()
        self.chunking_engine = ChunkingEngine()
        self.metadata_enricher = MetadataEnricher()
        
        # Load sections config
        self.sections_config = config.sections_config
        
        # Statistics
        self.stats = {
            'total_filings': 0,
            'total_sections': 0,
            'total_chunks': 0,
            'table_chunks': 0,
            'text_chunks': 0
        }
        
        logger.info("✅ PreprocessingPipeline ready")
    
    def process_filing(self, filing_data: Dict) -> List[Dict[str, Any]]:
        """
        Process complete filing into enriched chunks
        
        Args:
            filing_data: Filing data from sec_fetcher.fetch_filings_with_sections()
                {
                    'filing_metadata': {...},
                    'sections': {'1A': '...', '7': '...'},
                    'extraction_stats': {...}
                }
        
        Returns:
            List of enriched chunks ready for embedding
        """
        filing_metadata = filing_data['filing_metadata']
        sections = filing_data['sections']
        
        logger.info(
            f"\n{'='*70}\n"
            f"PROCESSING FILING: {filing_metadata['ticker']} "
            f"{filing_metadata['filing_type']} {filing_metadata['filing_date']}\n"
            f"{'='*70}"
        )
        
        all_chunks = []
        start_time = time.time()
        
        # Get section names
        section_names = self.sections_config['sec_filing_sections'].get(
            filing_metadata['filing_type'],
            {}
        )
        
        # Process each section
        for section_code, section_text in sections.items():
            section_name = section_names.get(section_code, section_code)
            
            logger.info(f"\n📄 Processing Section {section_code}: {section_name}")
            
            section_chunks = self._process_section(
                section_code=section_code,
                section_name=section_name,
                section_text=section_text,
                filing_metadata=filing_metadata
            )
            
            all_chunks.extend(section_chunks)
            
            logger.info(
                f"   ✅ Section complete: {len(section_chunks)} chunks "
                f"({sum(1 for c in section_chunks if c['chunk_type'] == 'table')} tables, "
                f"{sum(1 for c in section_chunks if c['chunk_type'] == 'text')} text)"
            )
        
        # Update statistics
        self.stats['total_filings'] += 1
        self.stats['total_sections'] += len(sections)
        self.stats['total_chunks'] += len(all_chunks)
        self.stats['table_chunks'] += sum(1 for c in all_chunks if c['chunk_type'] == 'table')
        self.stats['text_chunks'] += sum(1 for c in all_chunks if c['chunk_type'] == 'text')
        
        elapsed = time.time() - start_time
        
        logger.info(
            f"\n{'='*70}\n"
            f"✅ FILING COMPLETE: {len(all_chunks)} total chunks in {elapsed:.2f}s\n"
            f"   Tables: {sum(1 for c in all_chunks if c['chunk_type'] == 'table')}\n"
            f"   Text: {sum(1 for c in all_chunks if c['chunk_type'] == 'text')}\n"
            f"{'='*70}\n"
        )
        
        return all_chunks
    
    def _process_section(
        self,
        section_code: str,
        section_name: str,
        section_text: str,
        filing_metadata: Dict
    ) -> List[Dict[str, Any]]:
        """
        Process one section into enriched chunks
        
        Args:
            section_code: Section code
            section_name: Section name
            section_text: Raw section text
            filing_metadata: Filing metadata
            
        Returns:
            List of enriched chunks from this section
        """
        section_chunks = []
        
        # Step 1: Parse into components
        components = self.parser.parse_section(section_text)
        
        if not components:
            logger.warning(f"No components found in section {section_code}")
            return []
        
        logger.info(f"   Parsed into {len(components)} components")
        
        # Step 2: Process tables
        table_position = 0
        for i, component in enumerate(components):
            if component['type'] == 'table':
                table_chunk = self._process_table_component(
                    table_component=component,
                    components=components,
                    table_index=i,
                    filing_metadata=filing_metadata,
                    section_code=section_code,
                    section_name=section_name,
                    table_position=table_position
                )
                
                if table_chunk:
                    section_chunks.append(table_chunk)
                    table_position += 1
        
        # Step 3: Process text
        text_position = 0
        for component in components:
            if component['type'] == 'text':
                text_chunks = self._process_text_component(
                    text_component=component,
                    filing_metadata=filing_metadata,
                    section_code=section_code,
                    section_name=section_name,
                    starting_position=text_position
                )
                
                section_chunks.extend(text_chunks)
                text_position += len(text_chunks)
        
        return section_chunks
    
    def _process_table_component(
        self,
        table_component: Dict,
        components: List[Dict],
        table_index: int,
        filing_metadata: Dict,
        section_code: str,
        section_name: str,
        table_position: int
    ) -> Optional[Dict[str, Any]]:
        """
        Process one table component into enriched chunk
        
        Returns:
            Enriched table chunk or None if processing fails
        """
        try:
            # Get surrounding context
            context_before, context_after = self.parser.get_surrounding_context(
                components=components,
                table_index=table_index,
                sentences_before=self.sections_config['chunking_strategy']['tables']['context_sentences_before'],
                sentences_after=self.sections_config['chunking_strategy']['tables']['context_sentences_after']
            )
            
            # Process table (parse and convert to markdown)
            processed_table = self.table_extractor.process_table(
                table_component=table_component,
                context_before=context_before,
                context_after=context_after
            )
            
            if not processed_table:
                logger.error(f"Failed to process table at index {table_index}")
                return None
            
            # Generate LLM summary
            logger.info(f"   Generating LLM summary for table {table_position}...")
            table_summary = self.table_summarizer.generate_summary(
                table_markdown=processed_table['markdown_table'],
                context_before=context_before,
                context_after=context_after
            )
            
            # Enrich with metadata
            enriched_chunk = self.metadata_enricher.enrich_table_chunk(
                table_summary=table_summary,
                table_markdown=processed_table['markdown_table'],
                context_before=context_before,
                context_after=context_after,
                table_metadata=processed_table['metadata'],
                filing_metadata=filing_metadata,
                section_code=section_code,
                section_name=section_name,
                position_in_section=table_position
            )
            
            logger.info(f"   ✅ Table chunk created: {enriched_chunk['chunk_id']}")
            
            return enriched_chunk
            
        except Exception as e:
            logger.error(f"Error processing table component: {e}")
            return None
    
    def _process_text_component(
        self,
        text_component: Dict,
        filing_metadata: Dict,
        section_code: str,
        section_name: str,
        starting_position: int
    ) -> List[Dict[str, Any]]:
        """
        Process text component into enriched chunks
        
        Returns:
            List of enriched text chunks
        """
        try:
            # Clean text
            cleaned_text = self.text_cleaner.clean_text(text_component['content'])
            
            # Validate cleaned text
            if not self.text_cleaner.validate_cleaned_text(cleaned_text):
                logger.warning(f"Cleaned text validation failed, skipping")
                return []
            
            # Chunk text with section-aware sizing
            text_chunks = self.chunking_engine.chunk_text(
                text=cleaned_text,
                section_code=section_code,
                section_name=section_name
            )
            
            # Enrich each chunk with metadata
            enriched_chunks = []
            for i, chunk_text in enumerate(text_chunks):
                enriched_chunk = self.metadata_enricher.enrich_text_chunk(
                    chunk_text=chunk_text,
                    filing_metadata=filing_metadata,
                    section_code=section_code,
                    section_name=section_name,
                    chunk_index=starting_position + i
                )
                enriched_chunks.append(enriched_chunk)
            
            logger.info(f"   ✅ Created {len(enriched_chunks)} text chunks")
            
            return enriched_chunks
            
        except Exception as e:
            logger.error(f"Error processing text component: {e}")
            return []
    
    def get_pipeline_stats(self) -> Dict:
        """
        Get pipeline processing statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            'llm_usage': self.table_summarizer.get_usage_stats()
        }
    
    def reset_stats(self):
        """Reset statistics counters"""
        self.stats = {
            'total_filings': 0,
            'total_sections': 0,
            'total_chunks': 0,
            'table_chunks': 0,
            'text_chunks': 0
        }
        logger.info("Statistics reset")


# ==================== TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING PREPROCESSING PIPELINE")
    print("="*70 + "\n")
    
    # Create sample filing data (simulating sec_fetcher output)
    sample_filing = {
        'filing_metadata': {
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'cik': '0000320193',
            'filing_type': '10-K',
            'filing_date': '2024-11-01',
            'fiscal_year': 2024,
            'fiscal_quarter': None,
            'accession_number': '0000320193-24-000123',
            'filing_url': 'https://...'
        },
        'sections': {
            '1A': """Risk Factors

We face intense competition in the markets where we operate. Our competitors include established technology companies with substantial resources.

##TABLE_START
Competitive Landscape
Competitor    Market Share
Competitor A  25%
Competitor B  15%
Our Company   20%
##TABLE_END

The competitive environment requires continuous innovation and significant R&D investment. We must maintain our technological edge.

We also face regulatory risks in multiple jurisdictions. Privacy regulations are evolving rapidly."""
        },
        'extraction_stats': {
            'total_sections_expected': 4,
            'sections_extracted': 4,
            'success': True
        }
    }
    
    try:
        # Initialize pipeline
        pipeline = PreprocessingPipeline()
        
        # Process filing
        print("Processing sample filing...")
        print("-" * 70)
        
        enriched_chunks = pipeline.process_filing(sample_filing)
        
        # Display results
        print(f"\n{'='*70}")
        print("RESULTS")
        print(f"{'='*70}\n")
        
        print(f"✅ Generated {len(enriched_chunks)} enriched chunks\n")
        
        for i, chunk in enumerate(enriched_chunks, 1):
            print(f"{i}. {chunk['chunk_id']}")
            print(f"   Type: {chunk['chunk_type']}")
            print(f"   Contains table: {chunk['contains_table']}")
            print(f"   Tokens: {chunk['token_count']}")
            
            if chunk['chunk_type'] == 'table':
                print(f"   Table: {chunk['table_row_count']}×{chunk['table_col_count']}")
                print(f"   Summary: {chunk['table_summary']}")
            
            print(f"   Text preview: {chunk['text'][:100]}...")
            print()
        
        # Show pipeline stats
        print(f"\n{'='*70}")
        print("PIPELINE STATISTICS")
        print(f"{'='*70}\n")
        
        stats = pipeline.get_pipeline_stats()
        print(f"Filings processed: {stats['total_filings']}")
        print(f"Sections processed: {stats['total_sections']}")
        print(f"Total chunks: {stats['total_chunks']}")
        print(f"  - Table chunks: {stats['table_chunks']}")
        print(f"  - Text chunks: {stats['text_chunks']}")
        
        print(f"\nLLM Usage:")
        print(f"  API calls: {stats['llm_usage']['api_calls']}")
        print(f"  Cache hits: {stats['llm_usage']['cache_hits']}")
        print(f"  Cache hit rate: {stats['llm_usage']['cache_hit_rate']:.1f}%")
        print(f"  Total tokens: {stats['llm_usage']['total_tokens']:,}")
        print(f"  Estimated cost: ${stats['llm_usage']['estimated_cost_usd']:.4f}")
        
        print(f"\n{'='*70}")
        print("✅ PREPROCESSING PIPELINE TEST COMPLETE")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()