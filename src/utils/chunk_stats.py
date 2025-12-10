# src/utils/chunk_stats.py
"""Calculate and track chunk size statistics"""

from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def calculate_statistics(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate comprehensive chunk statistics
    
    Args:
        chunks: List of chunk dicts with metadata
               Each chunk should have: chunk_length, ticker, data_source, filing_type
    
    Returns:
        Statistics dict with global, per-company, per-source, per-filing-type breakdowns
    """
    if not chunks:
        logger.warning("No chunks provided for statistics calculation")
        return {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_chunks': 0
            }
        }
    
    logger.info(f"Calculating statistics for {len(chunks)} chunks...")
    
    # Extract all chunk lengths
    all_lengths = [c['chunk_length'] for c in chunks]
    
    # Build statistics structure
    stats = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_chunks': len(chunks)
        },
        'global_stats': _calculate_stats(all_lengths),
        'by_company': {},
        'by_data_source': {},
        'by_filing_type': {}
    }
    
    # Group chunks by company
    logger.info("Grouping by company...")
    company_chunks = defaultdict(list)
    for chunk in chunks:
        ticker = chunk.get('ticker', 'UNKNOWN')
        company_chunks[ticker].append(chunk)
    
    # Calculate stats per company
    for ticker, company_chunk_list in company_chunks.items():
        lengths = [c['chunk_length'] for c in company_chunk_list]
        
        stats['by_company'][ticker] = {
            'company_name': company_chunk_list[0].get('company', ticker),
            'total_chunks': len(company_chunk_list),
            **_calculate_stats(lengths),
            'by_filing_type': _group_by_filing_type(company_chunk_list)
        }
    
    logger.info(f"  Found {len(company_chunks)} companies")
    
    # Group chunks by data source
    logger.info("Grouping by data source...")
    source_chunks = defaultdict(list)
    for chunk in chunks:
        source = chunk.get('data_source', 'unknown')
        source_chunks[source].append(chunk)
    
    # Calculate stats per data source
    for source, source_chunk_list in source_chunks.items():
        lengths = [c['chunk_length'] for c in source_chunk_list]
        
        stats['by_data_source'][source] = {
            'total_chunks': len(source_chunk_list),
            **_calculate_stats(lengths)
        }
    
    logger.info(f"  Found {len(source_chunks)} data sources")
    
    # Group chunks by filing type
    logger.info("Grouping by filing type...")
    filing_type_chunks = defaultdict(list)
    for chunk in chunks:
        filing_type = chunk.get('filing_type', 'unknown')
        filing_type_chunks[filing_type].append(chunk)
    
    # Calculate stats per filing type
    for filing_type, filing_chunk_list in filing_type_chunks.items():
        lengths = [c['chunk_length'] for c in filing_chunk_list]
        
        stats['by_filing_type'][filing_type] = {
            'total_chunks': len(filing_chunk_list),
            **_calculate_stats(lengths)
        }
    
    logger.info(f"  Found {len(filing_type_chunks)} filing types")
    
    # Log summary
    logger.info(f"\nStatistics Summary:")
    logger.info(f"  Total chunks: {stats['global_stats']['total_chunks']}")
    logger.info(f"  Avg chunk size: {stats['global_stats']['avg_chunk_size']:.1f} chars")
    logger.info(f"  Min chunk size: {stats['global_stats']['min_chunk_size']} chars")
    logger.info(f"  Max chunk size: {stats['global_stats']['max_chunk_size']} chars")
    
    return stats


def _calculate_stats(lengths: List[int]) -> Dict[str, Any]:
    """
    Calculate min/max/avg statistics for a list of chunk lengths
    
    Args:
        lengths: List of chunk lengths (character counts)
    
    Returns:
        Dict with min, max, avg, total
    """
    if not lengths:
        return {
            'total_chunks': 0,
            'min_chunk_size': 0,
            'max_chunk_size': 0,
            'avg_chunk_size': 0.0,
            'total_characters': 0
        }
    
    return {
        'total_chunks': len(lengths),
        'min_chunk_size': min(lengths),
        'max_chunk_size': max(lengths),
        'avg_chunk_size': sum(lengths) / len(lengths),
        'total_characters': sum(lengths)
    }


def _group_by_filing_type(chunks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Group chunks by filing type and calculate stats
    
    Args:
        chunks: List of chunk dicts
    
    Returns:
        Dict mapping filing_type to statistics
    """
    filing_type_chunks = defaultdict(list)
    
    for chunk in chunks:
        filing_type = chunk.get('filing_type', 'unknown')
        filing_type_chunks[filing_type].append(chunk)
    
    result = {}
    for filing_type, filing_chunk_list in filing_type_chunks.items():
        lengths = [c['chunk_length'] for c in filing_chunk_list]
        result[filing_type] = _calculate_stats(lengths)
    
    return result


def print_statistics_summary(stats: Dict[str, Any]) -> None:
    """
    Print a formatted summary of statistics
    
    Args:
        stats: Statistics dict from calculate_statistics()
    """
    print("\n" + "="*70)
    print("CHUNK STATISTICS SUMMARY")
    print("="*70)
    
    # Global stats
    global_stats = stats.get('global_stats', {})
    print(f"\nGlobal Statistics:")
    print(f"  Total chunks:     {global_stats.get('total_chunks', 0):,}")
    print(f"  Total characters: {global_stats.get('total_characters', 0):,}")
    print(f"  Avg chunk size:   {global_stats.get('avg_chunk_size', 0):.1f} chars")
    print(f"  Min chunk size:   {global_stats.get('min_chunk_size', 0):,} chars")
    print(f"  Max chunk size:   {global_stats.get('max_chunk_size', 0):,} chars")
    
    # Per company
    by_company = stats.get('by_company', {})
    if by_company:
        print(f"\nBy Company:")
        for ticker in sorted(by_company.keys()):
            company_stats = by_company[ticker]
            print(f"  {ticker:6s} - {company_stats['total_chunks']:4d} chunks, "
                  f"avg: {company_stats['avg_chunk_size']:6.1f} chars")
    
    # Per data source
    by_source = stats.get('by_data_source', {})
    if by_source:
        print(f"\nBy Data Source:")
        for source in sorted(by_source.keys()):
            source_stats = by_source[source]
            print(f"  {source:10s} - {source_stats['total_chunks']:4d} chunks, "
                  f"avg: {source_stats['avg_chunk_size']:6.1f} chars")
    
    # Per filing type
    by_filing = stats.get('by_filing_type', {})
    if by_filing:
        print(f"\nBy Filing Type:")
        for filing_type in sorted(by_filing.keys()):
            filing_stats = by_filing[filing_type]
            print(f"  {filing_type:6s} - {filing_stats['total_chunks']:4d} chunks, "
                  f"avg: {filing_stats['avg_chunk_size']:6.1f} chars")
    
    print("\n" + "="*70)
