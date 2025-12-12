# src/data_ingestion/sec_fetcher.py
"""Simplified SEC fetcher using edgartools to fetch entire 10-K and 10-Q filings"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SECFetcher:
    """
    Fetches SEC filings using edgartools (free, no API key required)
    
    Features:
    - Fetch filings by CIK (not ticker)
    - Get full document text (entire filing, not sections)
    - Extract metadata from edgartools Filing objects
    - Automatically handles fiscal year/quarter
    
    Requires:
    - User identity (email) for SEC compliance
    - edgartools package (pip install edgartools)
    """
    
    def __init__(self, user_identity: str):
        """
        Initialize SEC fetcher with edgartools
        
        Args:
            user_identity: Email address for SEC compliance
                          (e.g., "your.name@example.com")
        """
        try:
            from edgar import set_identity
            set_identity(user_identity)
            logger.info(f"SECFetcher initialized with edgartools (identity: {user_identity})")
        except ImportError:
            raise ImportError(
                "edgartools not found. Install it with:\n"
                "  pip install edgartools"
            )
    
    def fetch_filings_by_cik(
        self,
        cik: str,
        filing_types: List[str],
        start_date: str,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch SEC filings for a company using CIK
        
        Args:
            cik: Company CIK (with or without leading zeros)
            filing_types: List of form types (e.g., ['10-K', '10-Q'])
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), None = today
        
        Returns:
            List of filing dicts with metadata and full document text
        """
        from edgar import Company
        
        # Normalize CIK (edgartools accepts with or without leading zeros)
        cik_str = str(cik).strip()
        
        logger.info(f"Fetching filings for CIK {cik_str}: {filing_types} from {start_date}")
        
        try:
            # Get company by CIK
            company = Company(cik_str)
            logger.info(f"Found company: {company.name}")
            
            # Build date range filter
            if end_date:
                date_filter = f"{start_date}:{end_date}"
            else:
                date_filter = f"{start_date}:"
            
            # Fetch filings
            filings = company.get_filings(
                form=filing_types,
                filing_date=date_filter
            )
            
            logger.info(f"Found {len(filings)} filings")
            
            # Process each filing
            results = []
            for i, filing in enumerate(filings):
                try:
                    logger.info(f"Processing filing {i+1}/{len(filings)}: {filing.form} on {filing.filing_date}")
                    
                    # Extract fiscal year and quarter
                    period = filing.period_of_report
                    if isinstance(period, str):
                        fiscal_year = int(period[:4])
                    else:
                        fiscal_year = period.year
                    
                    fiscal_quarter = self._get_fiscal_quarter(filing)
                    
                    # Get structured document (TenK or TenQ object)
                    # filing.obj() returns the appropriate report object based on form type
                    doc = None
                    try:
                        doc = filing.obj()
                        logger.info(f"  Got document object: {type(doc).__name__}")
                    except Exception as e:
                        logger.warning(f"  Could not get document via filing.obj(): {e}")
                    
                    # Extract all sections using ChunkedDocument for proper block-level access
                    sections_data = []
                    
                    if doc and hasattr(doc, 'items'):
                        # Get list of all available items in the filing
                        available_items = doc.items
                        logger.info(f"  Found {len(available_items)} items: {available_items}")
                        
                        # Create ChunkedDocument ONCE for the entire filing
                        # This parses the HTML into blocks and associates them with items
                        chunked_doc = None
                        try:
                            from edgar.files.htmltools import ChunkedDocument
                            from edgar.files.html_documents import HtmlDocument
                            chunked_doc = ChunkedDocument(filing.html())
                            logger.debug(f"  Created ChunkedDocument for section-level block extraction")
                        except Exception as chunk_err:
                            logger.warning(f"  Could not create ChunkedDocument: {chunk_err}")
                        
                        # Extract each section
                        for item in available_items:
                            try:
                                # Use bracket notation to get section text
                                section_text = doc[item]
                                
                                if section_text and len(section_text.strip()) > 100:  # Filter very short sections
                                    # Extract item number from item string (e.g., "Item 1" -> "1", "Item 1A" -> "1A")
                                    item_code = item.replace("Item ", "").replace("ITEM ", "").strip()
                                    
                                    # Get section title from structure
                                    section_title = self._get_section_title(doc, item)
                                    
                                    # Get section-specific HTML blocks
                                    section_html_doc = None
                                    try:
                                        if chunked_doc:
                                            # Get chunks (blocks) for this specific item only
                                            item_chunks = list(chunked_doc.chunks_for_item(item))
                                            
                                            if item_chunks:
                                                # Flatten all blocks from all chunks for this section
                                                section_blocks = []
                                                for chunk in item_chunks:
                                                    section_blocks.extend(chunk)  # chunk is a List[Block]
                                                
                                                # Create HtmlDocument from section-specific blocks
                                                section_html_doc = HtmlDocument(blocks=section_blocks)
                                                logger.debug(f"    Created HtmlDocument for {item} with {len(section_blocks)} blocks")
                                            else:
                                                logger.debug(f"    No chunks found for {item}, using fallback")
                                    except Exception as html_err:
                                        logger.debug(f"Could not extract blocks for {item}: {html_err}")
                                    
                                    # Fallback: create simple HTML from text
                                    if section_html_doc is None:
                                        fallback_html = f"<html><body><p>{section_text}</p></body></html>"
                                        section_html_doc = HtmlDocument.from_html(fallback_html)
                                        logger.debug(f"    Using fallback HTML for {item}")
                                    
                                    sections_data.append({
                                        'section_code': item_code,
                                        'section_name': section_title,
                                        'section_text': section_text,
                                        'section_html_doc': section_html_doc,  # HtmlDocument object with section-specific blocks
                                        'section_length': len(section_text)
                                    })
                                    logger.info(f"    ✓ {item}: {section_title} ({len(section_text)} chars)")
                            except Exception as e:
                                logger.warning(f"    ✗ Failed to extract {item}: {e}")
                                continue
                    
                    # Final fallback: use full document text
                    if not sections_data:
                        logger.warning(f"  No sections found in document, falling back to full text")
                        # Fallback: use full document text as single section
                        try:
                            full_text = filing.text()
                            sections_data.append({
                                'section_code': 'FULL_DOCUMENT',
                                'section_name': 'Full Document',
                                'section_text': full_text,
                                'section_length': len(full_text)
                            })
                        except Exception as e:
                            logger.error(f"  Failed to get full text fallback: {e}")
                            continue
                    
                    if not sections_data:
                        logger.warning(f"  No content extracted from filing")
                        continue
                    
                    # Create filing result with sections
                    filing_data = {
                        'cik': filing.cik,
                        'company': filing.company,
                        'filing_type': filing.form,
                        'filing_date': str(filing.filing_date),
                        'fiscal_year': fiscal_year,
                        'fiscal_quarter': fiscal_quarter,
                        'accession_number': filing.accession_no,
                        'filing_url': filing.homepage_url,
                        'sections': sections_data,  # List of sections with metadata
                        'total_sections': len(sections_data),
                        'total_length': sum(s['section_length'] for s in sections_data)
                    }
                    
                    results.append(filing_data)
                    
                    logger.info(f"  ✓ Extracted {len(sections_data)} sections, {filing_data['total_length']:,} total characters")
                    
                    # Rate limiting (be nice to SEC servers)
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to process filing {filing.accession_no}: {e}")
                    continue
            
            logger.info(f"Successfully fetched {len(results)}/{len(filings)} filings")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to fetch filings for CIK {cik_str}: {e}")
            raise
    
    def _get_fiscal_quarter(self, filing) -> Optional[int]:
        """
        Extract fiscal quarter from filing
        
        Args:
            filing: edgartools Filing object
        
        Returns:
            Quarter number (1-3) for 10-Q, None for 10-K
        """
        # 10-K doesn't have quarters
        if filing.form == '10-K':
            return None
        
        # For 10-Q, try to extract from filing
        try:
            # period_of_report can be string or datetime
            period = filing.period_of_report
            
            if isinstance(period, str):
                # Parse string date (format: YYYY-MM-DD)
                month = int(period[5:7])
            else:
                # It's a datetime-like object
                month = period.month
            
            # Q1: Jan-Mar (months 1-3)
            # Q2: Apr-Jun (months 4-6)
            # Q3: Jul-Sep (months 7-9)
            # Q4: Oct-Dec (months 10-12) - but 10-Q is only Q1-Q3
            
            if month in [1, 2, 3]:
                return 1
            elif month in [4, 5, 6]:
                return 2
            elif month in [7, 8, 9]:
                return 3
            else:
                # This shouldn't happen for 10-Q
                logger.warning(f"Unexpected month {month} for 10-Q filing")
                return None
                
        except Exception as e:
            logger.warning(f"Could not determine fiscal quarter: {e}")
            return None
    
    def _get_section_title(self, doc, item: str) -> str:
        """
        Get section title from TenK/TenQ structure
        
        Args:
            doc: TenK or TenQ object
            item: Item name (e.g., "Item 1", "Item 1A")
        
        Returns:
            Section title from structure, or the item name if not found
        """
        try:
            # Normalize item key: "Item 1" -> "ITEM 1"
            item_key = item.upper()
            
            # Look through structure to find matching item
            if hasattr(doc, 'structure') and hasattr(doc.structure, 'structure'):
                for part, items in doc.structure.structure.items():
                    if item_key in items:
                        return items[item_key].get('Title', item)
            
            # Fallback: return the item name itself
            return item
        except Exception as e:
            logger.warning(f"Could not get title for {item}: {e}")
            return item
    
    def fetch_multiple_companies(
        self,
        companies: List[Dict[str, str]],
        filing_types: List[str],
        start_date: str,
        end_date: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch filings for multiple companies
        
        Args:
            companies: List of company dicts with 'cik' and 'ticker' keys
            filing_types: List of form types
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), None = today
        
        Returns:
            Dict mapping ticker to list of filings
        """
        results = {}
        
        for i, company in enumerate(companies):
            ticker = company['ticker']
            cik = company['cik']
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Fetching {ticker} ({i+1}/{len(companies)})")
            logger.info(f"{'='*60}")
            
            try:
                filings = self.fetch_filings_by_cik(
                    cik=cik,
                    filing_types=filing_types,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Add ticker to each filing
                for filing in filings:
                    filing['ticker'] = ticker
                
                results[ticker] = filings
                
            except Exception as e:
                logger.error(f"Failed to fetch filings for {ticker}: {e}")
                results[ticker] = []
        
        return results
