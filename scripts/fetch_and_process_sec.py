#!/usr/bin/env python3
"""
Orchestration script to fetch, process, and store SEC filings

This script:
1. Loads companies from configs/companies.yaml
2. Loads SEC config from configs/sec_config.yaml
3. Fetches 10-K and 10-Q filings for each company using edgartools
4. Chunks the full document text
5. Generates metadata for each chunk
6. Calculates chunk statistics
7. Saves outputs to data/ folder:
   - sec_chunks_<timestamp>.json - All chunks with metadata
   - chunk_statistics_<timestamp>.json - Statistics by company/source/filing type
"""

import argparse
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_ingestion.sec_fetcher import SECFetcher
from src.data_processing.chunker import TextChunker
from src.utils.chunk_stats import calculate_statistics, print_statistics_summary
from src.utils.table_summarizer import GroqTableSummarizer
from src.data_processing.table_processor import TableProcessor
from src.data_storage.table_store import TableStore
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def load_yaml_config(file_path: Path) -> Dict[str, Any]:
    """Load YAML configuration file"""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def save_json(data: Dict[str, Any], file_path: Path) -> None:
    """Save data to JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved to: {file_path}")


def main():
    parser = argparse.ArgumentParser(description='Fetch and process SEC filings')
    parser.add_argument('--test-mode', action='store_true',
                       help='Test mode: only process first company')
    parser.add_argument('--cik', type=str,
                       help='Process only specific CIK (for testing)')
    parser.add_argument('--single-10k', action='store_true',
                       help='Fast test: only process ONE 10-K for first company (AAPL 2024)')
    parser.add_argument('--config-dir', type=str, default='configs',
                       help='Configuration directory (default: configs)')
    parser.add_argument('--output-dir', type=str, default='data',
                       help='Output directory (default: data)')
    
    args = parser.parse_args()
    
    # Setup paths
    base_dir = Path(__file__).parent.parent
    config_dir = base_dir / args.config_dir
    output_dir = base_dir / args.output_dir
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("="*70)
    logger.info("SEC FILING FETCHER AND PROCESSOR")
    logger.info("="*70)
    
    # Load configurations
    logger.info("\n1. Loading configurations...")
    
    companies_config = load_yaml_config(config_dir / 'companies.yaml')
    sec_config = load_yaml_config(config_dir / 'sec_config.yaml')
    
    companies = companies_config['companies']
    
    # Filter by CIK if specified
    if args.cik:
        companies = [c for c in companies if c['cik'] == args.cik]
        if not companies:
            logger.error(f"No company found with CIK: {args.cik}")
            return
        logger.info(f"  Filtering to CIK: {args.cik}")
    
    # Test mode: only first company
    if args.test_mode:
        companies = companies[:1]
        logger.info(f"  TEST MODE: Processing only {companies[0]['ticker']}")
    
    logger.info(f"  Companies: {len(companies)}")
    logger.info(f"  Start date: {sec_config['fetch_start_date']}")
    logger.info(f"  End date: {sec_config.get('fetch_end_date', 'today')}")
    
    # Initialize components
    logger.info("\n2. Initializing components...")
    
    fetcher = SECFetcher(user_identity=sec_config['user_identity'])
    
    # Get chunking parameters from config or use defaults
    chunk_size = sec_config.get('chunk_size', 800)
    overlap = sec_config.get('overlap', 100)
    chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
    
    logger.info(f"  Chunker: {chunk_size} tokens, {overlap} overlap")
    
    # Initialize table processing (if enabled)
    table_config = sec_config.get('table_processing', {})
    table_processor = None
    table_store = None
    
    if table_config.get('enabled', False):
        try:
            # Get API key from environment or config
            api_key = os.getenv('GROQ_API_KEY') or table_config.get('groq_api_key', '').replace('${GROQ_API_KEY}', os.getenv('GROQ_API_KEY', ''))
            
            if api_key and api_key != '${GROQ_API_KEY}':
                summarizer = GroqTableSummarizer(
                    api_key=api_key,
                    model=table_config.get('groq_model', 'llama-3.1-8b-instant'),
                    max_summary_length=table_config.get('summary_max_length', 200),
                    rate_limit_rpm=table_config.get('rate_limit_rpm', 30)
                )
                
                table_processor = TableProcessor(
                    summarizer=summarizer,
                    min_table_size=table_config.get('min_table_size', 0)
                )
                
                table_store = TableStore(storage_path=str(output_dir / 'tables'))
                
                logger.info(f"  Table Processing: ENABLED")
                logger.info(f"    Model: {table_config.get('groq_model')}")
                logger.info(f"    Min table size: {table_config.get('min_table_size', 0)} cells")
            else:
                logger.warning("  Table Processing: DISABLED (GROQ_API_KEY not set)")
        except Exception as e:
            logger.error(f"  Table Processing: DISABLED (Error: {e})")
    else:
        logger.info("  Table Processing: DISABLED (not enabled in config)")
    
    # Fetch filings for all companies
    logger.info("\n3. Fetching SEC filings...")
    
    all_filings = fetcher.fetch_multiple_companies(
        companies=companies,
        filing_types=['10-K', '10-Q'],
        start_date=sec_config['fetch_start_date'],
        end_date=sec_config.get('fetch_end_date')
    )
    
    # Filter to single 10-K if requested (for fast testing)
    if args.single_10k:
        logger.info("\n  SINGLE 10-K MODE: Filtering to one 10-K filing for first company")
        for ticker in list(all_filings.keys()):
            # Keep only 10-K filings
            filings = [f for f in all_filings[ticker] if f['filing_type'] == '10-K']
            if filings:
                # Keep only the most recent one (2024)
                all_filings[ticker] = [filings[0]]
                logger.info(f"  Selected: {ticker} 10-K filed on {filings[0]['filing_date']}")
                break  # Only first company
        # Remove other companies
        all_filings = {ticker: all_filings[ticker] for ticker in list(all_filings.keys())[:1]}
    
    # Count total filings
    total_filings = sum(len(filings) for filings in all_filings.values())
    logger.info(f"\n  Total filings to process: {total_filings}")
    
    # Process and chunk filings
    logger.info("\n4. Chunking documents...")
    
    all_chunks = []
    all_tables = []  # Store tables separately
    
    # Create progress bar for all filings
    total_items = sum(len(filings) for filings in all_filings.values())
    pbar = tqdm(total=total_items, desc="Processing filings", unit="filing")
    
    for ticker, filings in all_filings.items():
        for filing in filings:
            try:
                # Process each section in the filing
                for section in filing.get('sections', []):
                    section_code = section['section_code']
                    section_name = section['section_name']
                    section_text = section['section_text']
                    section_html_doc = section.get('section_html_doc')  # Now HtmlDocument object
                    
                    # Process tables if enabled
                    section_tables = []
                    if table_processor and section_html_doc:
                        try:
                            # Create metadata for table processing
                            table_metadata = {
                                'ticker': ticker,
                                'company': filing['company'],
                                'section': section_code,
                                'section_name': section_name,
                                'filing_type': filing['filing_type'],
                                'filing_date': filing['filing_date'],
                                'accession_number': filing['accession_number']
                            }
                            
                            # Process section with table detection
                            processed_text, section_tables = table_processor.process_section(
                                section_html=section_html_doc,  # Pass HtmlDocument object
                                section_text=section_text,
                                metadata=table_metadata
                            )
                            
                            # Use processed text (with table references)
                            section_text = processed_text
                            
                            # Collect tables
                            all_tables.extend(section_tables)
                            
                        except Exception as table_err:
                            logger.warning(f"Table processing failed for {section_code}: {table_err}")
                            # Fall back to original text
                    
                    # Chunk the section text (with table references if processing enabled)
                    chunks = chunker.chunk_text(section_text)
                    
                    # Add metadata to each chunk
                    for i, chunk_text in enumerate(chunks):
                        # Extract table references from chunk
                        table_refs = []
                        if table_processor:
                            table_refs = table_processor.extract_table_references(chunk_text)
                        
                        chunk_data = {
                            'chunk_id': f"{ticker}_sec_{filing['accession_number']}_{section_code}_{i}",
                            'company': filing['company'],
                            'ticker': ticker,
                            'cik': filing['cik'],
                            'filing_type': filing['filing_type'],
                            'filing_date': filing['filing_date'],
                            'fiscal_year': filing['fiscal_year'],
                            'fiscal_quarter': filing['fiscal_quarter'],
                            'filing_url': filing['filing_url'],
                            'accession_number': filing['accession_number'],
                            'section': section_code,
                            'section_name': section_name,
                            'chunk_text': chunk_text,
                            'chunk_length': len(chunk_text),
                            'chunk_index': i,
                            'total_chunks_in_section': len(chunks),
                            'table_references': table_refs,  # NEW: Table reference IDs
                            'has_tables': len(table_refs) > 0,  # NEW: Flag for table presence
                            'data_source': 'sec',
                            'fetched_date': datetime.now().isoformat()
                        }
                        
                        all_chunks.append(chunk_data)
                
                pbar.update(1)
                
            except Exception as e:
                logger.error(f"Failed to chunk filing {filing.get('accession_number', 'unknown')}: {e}")
                pbar.update(1)
                continue
    
    pbar.close()
    
    logger.info(f"  Total chunks created: {len(all_chunks)}")
    if all_tables:
        logger.info(f"  Total tables extracted: {len(all_tables)}")
    
    # Calculate statistics
    logger.info("\n5. Calculating statistics...")
    
    stats = calculate_statistics(all_chunks)
    
    # Print summary
    print_statistics_summary(stats)
    
    # Save outputs
    logger.info("\n6. Saving outputs...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save chunks
    chunks_output = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'data_source': 'sec',
            'total_companies': len(companies),
            'total_filings': total_filings,
            'total_chunks': len(all_chunks),
            'chunk_size': chunk_size,
            'chunk_overlap': overlap
        },
        'chunks': all_chunks
    }
    
    chunks_file = output_dir / f'sec_chunks_{timestamp}.json'
    save_json(chunks_output, chunks_file)
    
    # Save tables (if any)
    tables_file = None
    if all_tables and table_store:
        tables_file = table_store.save_tables(all_tables, f'tables_{timestamp}.json')
        logger.info(f"  Tables saved: {len(all_tables)} tables")
    
    # Save statistics
    stats_file = output_dir / f'chunk_statistics_{timestamp}.json'
    save_json(stats, stats_file)
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*70)
    logger.info(f"Companies processed: {len(companies)}")
    logger.info(f"Filings processed:   {total_filings}")
    logger.info(f"Chunks created:      {len(all_chunks)}")
    if all_tables:
        logger.info(f"Tables extracted:    {len(all_tables)}")
    logger.info(f"\nOutputs:")
    logger.info(f"  Chunks:      {chunks_file}")
    logger.info(f"  Statistics:  {stats_file}")
    if tables_file:
        logger.info(f"  Tables:      {tables_file}")
    logger.info("="*70)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nFATAL ERROR: {e}", exc_info=True)
        sys.exit(1)
