#!/usr/bin/env python
"""
Unified Data Fetcher for Single Company

Fetches and processes data from:
- SEC (single 10-K filing)
- Wikipedia 
- News articles

Saves all data locally in a structured format.

Usage:
    python scripts/fetch_single_company.py --ticker AAPL --year 2024
"""

import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import os
from dotenv import load_dotenv

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_ingestion.sec_fetcher import SECFetcher
from src.data_ingestion.wikipedia_fetcher import WikipediaFetcher
from src.data_ingestion.news_fetcher import NewsFetcher
from src.data_processing.chunker import TextChunker
from src.data_processing.table_processor import TableProcessor
from src.utils.table_summarizer import GroqTableSummarizer
from src.data_storage.table_store import TableStore
from src.utils.logging_config import get_logger

# Validation and Bias Mitigation
from src.validation import DataValidator
from src.bias import CoverageTracker

logger = get_logger(__name__)


class SingleCompanyFetcher:
    """Fetch and process data for a single company from multiple sources"""
    
    def __init__(self, output_dir: Path, config_dir: Path):
        """
        Initialize fetcher
        
        Args:
            output_dir: Directory to save outputs
            output_dir: Directory with config files
        """
        self.output_dir = output_dir
        self.config_dir = config_dir
        
        # Load environment variables from repo root
        repo_root = Path(__file__).parent.parent.parent
        env_path = repo_root / ".env"
        load_dotenv(env_path)
        logger.info(f"Loaded environment from: {env_path}")
        
        # Load SEC config
        sec_config_path = config_dir / "sec_config.yaml"
        with open(sec_config_path) as f:
            self.sec_config = yaml.safe_load(f)
        
        # Initialize fetchers
        user_identity = self.sec_config.get('user_identity', 'DataPipeline/1.0')
        self.sec_fetcher = SECFetcher(user_identity=user_identity)
        self.wiki_fetcher = WikipediaFetcher()
        
        # Initialize News Fetcher (requires NEWSAPI_KEY from .env)
        newsapi_key = os.getenv("NEWSAPI_KEY")
        if newsapi_key:
            self.news_fetcher = NewsFetcher(mode="auto")
            logger.info("NewsFetcher initialized (NewsAPI + GDELT)")
        else:
            self.news_fetcher = None
            logger.warning("NEWSAPI_KEY not found - news fetching disabled")
        
        # Initialize chunker
        chunk_config = self.sec_config.get('chunking', {})
        self.chunker = TextChunker(
            chunk_size=chunk_config.get('chunk_size', 800),
            overlap=chunk_config.get('overlap', 100)
        )
        
        # Initialize table processing (if GROQ_API_KEY available)
        table_config = self.sec_config.get('table_processing', {})
        groq_key = os.getenv("GROQ_API_KEY")
        
        if table_config.get('enabled') and groq_key:
            summarizer = GroqTableSummarizer(
                api_key=groq_key,
                model=table_config.get('groq_model', 'llama-3.1-8b-instant'),
                max_summary_length=table_config.get('summary_max_length', 200),
                rate_limit_rpm=table_config.get('rate_limit_rpm', 30)
            )
            
            self.table_processor = TableProcessor(
                summarizer=summarizer,
                min_table_size=table_config.get('min_table_size', 0)
            )
            
            self.table_store = TableStore(output_dir / "tables")
            logger.info("Table processing enabled (Groq)")
        else:
            self.table_processor = None
            self.table_store = None
            logger.warning("Table processing disabled (no GROQ_API_KEY or disabled in config)")
        
        logger.info("SingleCompanyFetcher initialized")
    
    def fetch_sec_data(self, ticker: str, year: int) -> Dict[str, Any]:
        """
        Fetch single 10-K filing for company
        
        Args:
            ticker: Company ticker
            year: Fiscal year
        
        Returns:
            Dict with filing data and chunks
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"FETCHING SEC DATA: {ticker} 10-K {year}")
        logger.info(f"{'='*70}")
        
        # Get company info from config
        from src.utils.config import config
        company_info = config.get_company_by_ticker(ticker)
        if not company_info:
            logger.error(f"Company {ticker} not found in config")
            return None
        
        # Fetch filings for the specific year
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        filings = self.sec_fetcher.fetch_filings_by_cik(
            cik=company_info.cik,
            filing_types=['10-K'],
            start_date=start_date,
            end_date=end_date
        )
        
        if not filings:
            logger.error(f"No 10-K found for {ticker} in {year}")
            return None
        
        # Take the first (most recent) 10-K
        filing = filings[0]
        
        logger.info(f"Found 10-K: {filing['filing_date']}, Accession: {filing['accession_number']}")
        
        # Get sections (correct key is 'sections' not 'sections_data')
        sections = filing.get('sections', [])
        logger.info(f"Processing {len(sections)} sections...")
        
        all_chunks = []
        all_tables = []
        
        for section in sections:
            section_code = section['section_code']
            section_name = section['section_name']
            section_text = section['section_text']
            section_html_doc = section.get('section_html_doc')
            
            logger.info(f"  Processing {section_code}: {section_name}")
            
            # Process tables if enabled
            if self.table_processor and section_html_doc:
                try:
                    table_metadata = {
                        'ticker': ticker,
                        'company': filing['company'],
                        'filing_type': '10-K',
                        'filing_date': filing['filing_date'],
                        'accession_number': filing['accession_number'],
                        'section': section_code,
                        'section_name': section_name
                    }
                    
                    processed_text, section_tables = self.table_processor.process_section(
                        section_html=section_html_doc,
                        section_text=section_text,
                        metadata=table_metadata
                    )
                    
                    section_text = processed_text
                    all_tables.extend(section_tables)
                    
                    logger.info(f"    Found {len(section_tables)} tables")
                    
                except Exception as e:
                    logger.warning(f"    Table processing failed: {e}")
            
            # Chunk section text
            chunks = self.chunker.chunk_text(section_text)
            
            # Add metadata to chunks
            for i, chunk_text in enumerate(chunks):
                chunk_data = {
                    'chunk_id': f"{ticker}_sec_{filing['accession_number']}_{section_code}_{i}",
                    'company': filing['company'],
                    'ticker': ticker,
                    'filing_type': '10-K',
                    'filing_date': filing['filing_date'],
                    'fiscal_year': year,
                    'section': section_code,
                    'section_name': section_name,
                    'chunk_text': chunk_text,
                    'chunk_index': i,
                    'total_chunks_in_section': len(chunks),
                    'chunk_length': len(chunk_text),
                    'data_source': 'sec',
                    'fetched_date': datetime.now().isoformat()
                }
                
                # Extract table references
                if self.table_processor:
                    table_refs = self.table_processor.extract_table_references(chunk_text)
                    chunk_data['table_references'] = table_refs
                    chunk_data['has_tables'] = len(table_refs) > 0
                
                all_chunks.append(chunk_data)
            
            logger.info(f"    Created {len(chunks)} chunks")
        
        # Save tables
        if self.table_store and all_tables:
            self.table_store.save_tables(all_tables)
            logger.info(f"\nSaved {len(all_tables)} tables")
        
        logger.info(f"\nTotal SEC chunks: {len(all_chunks)}")
        
        return {
            'filing_metadata': {
                'ticker': ticker,
                'company': filing['company'],
                'filing_type': '10-K',
                'filing_date': filing['filing_date'],
                'fiscal_year': year,
                'accession_number': filing['accession_number']
            },
            'chunks': all_chunks,
            'num_tables': len(all_tables)
        }
    
    def fetch_wikipedia_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch Wikipedia page for company
        
        Args:
            ticker: Company ticker
        
        Returns:
            Dict with Wikipedia data and chunks
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"FETCHING WIKIPEDIA DATA: {ticker}")
        logger.info(f"{'='*70}")
        
        try:
            wiki_data = self.wiki_fetcher.fetch_by_ticker(ticker)
            
            logger.info(f"Fetched: {wiki_data['page_title']}")
            logger.info(f"Content: {len(wiki_data['text_content'])} chars")
            
            # Chunk the text content
            chunks = self.chunker.chunk_text(wiki_data['text_content'])
            
            # Add metadata
            wiki_chunks = []
            for i, chunk_text in enumerate(chunks):
                chunk_data = {
                    'chunk_id': f"{ticker}_wiki_{i}",
                    'ticker': ticker,
                    'page_title': wiki_data['page_title'],
                    'page_url': wiki_data['page_url'],
                    'chunk_text': chunk_text,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'chunk_length': len(chunk_text),
                    'data_source': 'wikipedia',
                    'fetched_date': datetime.now().isoformat()
                }
                wiki_chunks.append(chunk_data)
            
            logger.info(f"Created {len(wiki_chunks)} Wikipedia chunks")
            
            return {
                'page_metadata': {
                    'page_title': wiki_data['page_title'],
                    'page_url': wiki_data['page_url'],
                    'revision_id': wiki_data['revision_id']
                },
                'chunks': wiki_chunks
            }
            
        except Exception as e:
            logger.error(f"Wikipedia fetch failed: {e}")
            return None
    
    def fetch_news_data(self, ticker: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Fetch news articles for company
        
        Args:
            ticker: Company ticker
            days_back: Days to look back (default: 30)
        
        Returns:
            Dict with news data and chunks
        """
        if not self.news_fetcher:
            logger.warning("News fetching disabled (no NEWSAPI_KEY)")
            return None
        
        logger.info(f"\n{'='*70}")
        logger.info(f"FETCHING NEWS DATA: {ticker} (last {days_back} days)")
        logger.info(f"{'='*70}")
        
        try:
            articles = self.news_fetcher.fetch_by_ticker(
                ticker=ticker,
                days_back=days_back,
                max_records=50
            )
            
            logger.info(f"Fetched {len(articles)} articles")
            
            # Chunk each article
            news_chunks = []
            for article in articles:
                # Combine title and content for chunking
                full_text = f"{article['title']}\n\n{article.get('content', '')}"
                
                chunks = self.chunker.chunk_text(full_text)
                
                for i, chunk_text in enumerate(chunks):
                    chunk_data = {
                        'chunk_id': f"{ticker}_news_{article.get('article_id', 'unknown')}_{i}",
                        'ticker': ticker,
                        'article_title': article['title'],
                        'article_url': article.get('url'),
                        'published_date': article.get('published_at'),
                        'source': article.get('source'),
                        'chunk_text': chunk_text,
                        'chunk_index': i,
                        'total_chunks_in_article': len(chunks),
                        'chunk_length': len(chunk_text),
                        'relevance_score': article.get('relevance_score'),
                        'data_source': 'news',
                        'fetched_date': datetime.now().isoformat()
                    }
                    news_chunks.append(chunk_data)
            
            logger.info(f"Created {len(news_chunks)} news chunks from {len(articles)} articles")
            
            return {
                'news_metadata': {
                    'num_articles': len(articles),
                    'date_range_days': days_back
                },
                'chunks': news_chunks
            }
            
        except Exception as e:
            logger.error(f"News fetch failed: {e}")
            return None
    
    def save_data(self, ticker: str, year: int, data: Dict[str, Any]):
        """Save all data to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ticker}_{year}_all_data_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"SAVED: {filepath}")
        logger.info(f"{'='*70}")
        
        return filepath


def main():
    parser = argparse.ArgumentParser(
        description='Fetch and process data for a single company (SEC + Wikipedia + News)'
    )
    parser.add_argument('--ticker', type=str, required=True,
                       help='Company ticker (e.g., AAPL)')
    parser.add_argument('--year', type=int, required=True,
                       help='Fiscal year for 10-K (e.g., 2024)')
    parser.add_argument('--news-days', type=int, default=30,
                       help='Days of news to fetch (default: 30)')
    parser.add_argument('--output-dir', type=str, default='data',
                       help='Output directory (default: data)')
    parser.add_argument('--config-dir', type=str, default='configs',
                       help='Config directory (default: configs)')
    
    args = parser.parse_args()
    
    # Setup paths
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / args.output_dir
    config_dir = base_dir / args.config_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("="*70)
    logger.info("SINGLE COMPANY DATA FETCHER")
    logger.info("="*70)
    logger.info(f"Ticker: {args.ticker}")
    logger.info(f"Year: {args.year}")
    logger.info(f"Output: {output_dir}")
    
    # Initialize fetcher
    fetcher = SingleCompanyFetcher(output_dir, config_dir)
    
    # Fetch all data
    result = {
        'ticker': args.ticker,
        'year': args.year,
        'fetched_at': datetime.now().isoformat()
    }
    
    # 1. SEC Data
    sec_data = fetcher.fetch_sec_data(args.ticker, args.year)
    if sec_data:
        result['sec'] = sec_data
    
    # 2. Wikipedia Data
    wiki_data = fetcher.fetch_wikipedia_data(args.ticker)
    if wiki_data:
        result['wikipedia'] = wiki_data
    
    # 3. News Data
    news_data = fetcher.fetch_news_data(args.ticker, args.news_days)
    if news_data:
        result['news'] = news_data
    
    # Summary
    logger.info(f"\n{'='*70}")
    logger.info("SUMMARY")
    logger.info(f"{'='*70}")
    logger.info(f"SEC chunks:       {len(result.get('sec', {}).get('chunks', []))}")
    logger.info(f"SEC tables:       {result.get('sec', {}).get('num_tables', 0)}")
    logger.info(f"Wikipedia chunks: {len(result.get('wikipedia', {}).get('chunks', []))}")
    logger.info(f"News chunks:      {len(result.get('news', {}).get('chunks', []))}")
    logger.info(f"Total chunks:     {len(result.get('sec', {}).get('chunks', [])) + len(result.get('wikipedia', {}).get('chunks', [])) + len(result.get('news', {}).get('chunks', []))}")
    
    # Save
    filepath = fetcher.save_data(args.ticker, args.year, result)
    
    # ========================================
    # POST-PROCESSING: Validation & Bias Tracking
    # ========================================
    
    # 1. VALIDATE DATA
    logger.info(f"\n{'='*70}")
    logger.info("VALIDATING DATA QUALITY")
    logger.info(f"{'='*70}")
    
    validator = DataValidator()
    tables_dir = output_dir / "tables"
    validation_results = validator.run_all_validations(result, tables_dir)
    
    # Print validation summary
    if validation_results['overall_valid']:
        logger.info("✅ All validation checks passed!")
    else:
        logger.warning("⚠️ Some validation checks failed:")
        for issue in validation_results['critical_issues'][:5]:
            logger.warning(f"  - {issue}")
    
    # Save validation report
    validation_file = filepath.parent / f"{filepath.stem}_validation.json"
    with open(validation_file, 'w') as f:
        json.dump(validation_results, f, indent=2)
    logger.info(f"Validation report saved: {validation_file}")
    
    # 2. TRACK COVERAGE FOR BIAS MITIGATION
    logger.info(f"\n{'='*70}")
    logger.info("TRACKING COVERAGE METRICS")
    logger.info(f"{'='*70}")
    
    # Initialize coverage tracker
    bias_config_dir = base_dir / "bias_config"
    bias_config_dir.mkdir(parents=True, exist_ok=True)
    
    coverage_tracker = CoverageTracker(bias_config_dir / "coverage_metrics.json")
    
    # Combine all chunks for tracking
    all_chunks = []
    all_chunks.extend(result.get('sec', {}).get('chunks', []))
    all_chunks.extend(result.get('wikipedia', {}).get('chunks', []))
    all_chunks.extend(result.get('news', {}).get('chunks', []))
    
    # Get company name
    company_name = result.get('sec', {}).get('filing_metadata', {}).get('company', args.ticker)
    num_tables = result.get('sec', {}).get('num_tables', 0)
    
    # Track coverage
    coverage_metrics = coverage_tracker.track_company(
        ticker=args.ticker,
        company_name=company_name,
        chunks=all_chunks,
        num_tables=num_tables,
        metadata={'year': args.year, 'file': filepath.name}
    )
    
    logger.info(f"Coverage tracked: {coverage_metrics['total_chunks']} chunks, completeness={coverage_metrics['completeness_score']:.2f}")
    
    # Print summary stats
    summary_stats = coverage_tracker.get_summary_stats()
    if summary_stats['total_companies'] > 1:
        logger.info(f"\nGlobal Coverage Stats (across {summary_stats['total_companies']} companies):")
        logger.info(f"  Average chunks: {summary_stats['avg_total_chunks']:.1f}")
        logger.info(f"  Your company: {coverage_metrics['total_chunks']} chunks")
        ratio = coverage_metrics['total_chunks'] / summary_stats['avg_total_chunks']
        logger.info(f"  Coverage ratio: {ratio:.2f}x average")
    
    # FINAL SUMMARY
    logger.info(f"\n{'='*70}")
    logger.info("COMPLETE!")
    logger.info(f"{'='*70}")
    logger.info(f"✅ Data saved: {filepath}")
    logger.info(f"✅ Validation: {'PASSED' if validation_results['overall_valid'] else 'WARNINGS'}")
    logger.info(f"✅ Coverage tracked: {coverage_metrics['total_chunks']} chunks")
    logger.info(f"\nDone! Data saved to: {filepath}")


if __name__ == "__main__":
    main()
