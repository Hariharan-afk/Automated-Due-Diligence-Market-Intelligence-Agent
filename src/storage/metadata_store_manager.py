# src/storage/metadata_store_manager.py
"""Manager for PostgreSQL metadata operations"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import config
from src.utils.logging_config import get_logger
from src.utils.retry_handler import retry_on_failure

logger = get_logger(__name__)


class MetadataStoreManager:
    """Manages PostgreSQL operations for metadata storage"""
    
    def __init__(self, pool_size: int = 5):
        """
        Initialize metadata store manager
        
        Args:
            pool_size: Size of connection pool
        """
        self.pool = SimpleConnectionPool(
            minconn=1,
            maxconn=pool_size,
            host=config.database.postgres_host,
            port=config.database.postgres_port,
            database=config.database.postgres_database,
            user=config.database.postgres_user,
            password=config.database.postgres_password
        )
        logger.info("MetadataStoreManager initialized with connection pool")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections
        
        Usage:
            with manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    # ==================== COMPANY OPERATIONS ====================
    
    def get_all_companies(self) -> List[Dict[str, Any]]:
        """Get all companies from database"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT ticker, company_name, cik, sector, industry, added_date
                FROM companies
                ORDER BY ticker
            """)
            companies = cursor.fetchall()
            logger.info(f"Retrieved {len(companies)} companies")
            return [dict(row) for row in companies]
    
    def get_company_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get company by ticker symbol"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT ticker, company_name, cik, sector, industry, added_date
                FROM companies
                WHERE ticker = %s
            """, (ticker,))
            company = cursor.fetchone()
            return dict(company) if company else None
    
    # ==================== SEC FILING OPERATIONS ====================
    
    @retry_on_failure
    def save_filing_metadata(
        self,
        ticker: str,
        filing_type: str,
        filing_date: str,
        accession_number: str,
        filing_url: str,
        fiscal_year: Optional[int] = None,
        fiscal_quarter: Optional[int] = None,
        fiscal_period_end: Optional[str] = None
    ) -> int:
        """
        Save SEC filing metadata
        
        Args:
            ticker: Company ticker symbol
            filing_type: Type of filing (10-K, 10-Q)
            filing_date: Date of filing
            accession_number: SEC accession number
            filing_url: URL to filing
            fiscal_year: Fiscal year
            fiscal_quarter: Fiscal quarter (for 10-Q)
            fiscal_period_end: Fiscal period end date
            
        Returns:
            Filing ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert or update filing
            cursor.execute("""
                INSERT INTO sec_filings (
                    ticker, filing_type, filing_date, accession_number,
                    filing_url, fiscal_year, fiscal_quarter, fiscal_period_end,
                    status, fetched_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'fetched', NOW())
                ON CONFLICT (accession_number) 
                DO UPDATE SET
                    filing_url = EXCLUDED.filing_url,
                    fetched_at = NOW(),
                    updated_at = NOW()
                RETURNING id
            """, (
                ticker, filing_type, filing_date, accession_number,
                filing_url, fiscal_year, fiscal_quarter, fiscal_period_end
            ))
            
            filing_id = cursor.fetchone()[0]
            logger.info(f"Saved filing metadata: {ticker} {filing_type} (ID: {filing_id})")
            return filing_id
    
    def update_filing_status(
        self,
        filing_id: int,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Update filing processing status
        
        Args:
            filing_id: Filing ID
            status: New status (pending, fetched, processing, completed, failed)
            error_message: Optional error message if failed
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sec_filings
                SET status = %s, error_message = %s, updated_at = NOW()
                WHERE id = %s
            """, (status, error_message, filing_id))
            logger.info(f"Updated filing {filing_id} status to: {status}")
    
    def update_filing_processing_complete(
        self,
        filing_id: int,
        sections_extracted: List[str],
        total_chunks: int,
        text_chunks: int,
        table_chunks: int
    ):
        """
        Mark filing as processing complete
        
        Args:
            filing_id: Filing ID
            sections_extracted: List of section codes extracted
            total_chunks: Total number of chunks
            text_chunks: Number of text chunks
            table_chunks: Number of table chunks
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sec_filings
                SET 
                    status = 'completed',
                    sections_extracted = %s,
                    total_chunks = %s,
                    text_chunks = %s,
                    table_chunks = %s,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (sections_extracted, total_chunks, text_chunks, table_chunks, filing_id))
            logger.info(f"Filing {filing_id} processing complete: {total_chunks} chunks")
    
    def mark_filing_indexed(self, filing_id: int):
        """Mark filing as indexed in vector database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sec_filings
                SET indexed_in_vector_db = TRUE, indexed_at = NOW()
                WHERE id = %s
            """, (filing_id,))
            logger.info(f"Marked filing {filing_id} as indexed")
    
    def get_filing_by_accession(self, accession_number: str) -> Optional[Dict[str, Any]]:
        """Get filing by accession number"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM sec_filings
                WHERE accession_number = %s
            """, (accession_number,))
            filing = cursor.fetchone()
            return dict(filing) if filing else None
    
    def get_filings_by_ticker(
        self,
        ticker: str,
        filing_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get filings for a ticker
        
        Args:
            ticker: Company ticker
            filing_type: Optional filter by filing type
            limit: Maximum number of filings to return
            
        Returns:
            List of filing records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if filing_type:
                cursor.execute("""
                    SELECT * FROM sec_filings
                    WHERE ticker = %s AND filing_type = %s
                    ORDER BY filing_date DESC
                    LIMIT %s
                """, (ticker, filing_type, limit))
            else:
                cursor.execute("""
                    SELECT * FROM sec_filings
                    WHERE ticker = %s
                    ORDER BY filing_date DESC
                    LIMIT %s
                """, (ticker, limit))
            
            filings = cursor.fetchall()
            return [dict(row) for row in filings]
    
    def check_filing_exists(self, accession_number: str) -> bool:
        """Check if filing already exists"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM sec_filings 
                    WHERE accession_number = %s
                )
            """, (accession_number,))
            return cursor.fetchone()[0]
    
    # ==================== WIKIPEDIA OPERATIONS ====================
    
    def save_wikipedia_metadata(
        self,
        ticker: str,
        page_title: str,
        page_url: str,
        revision_id: int,
        chunk_count: int = 0
    ):
        """Save or update Wikipedia page metadata"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO wikipedia_pages (
                    ticker, page_title, page_url, revision_id,
                    chunk_count, last_checked, last_updated
                )
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (ticker)
                DO UPDATE SET
                    page_title = EXCLUDED.page_title,
                    page_url = EXCLUDED.page_url,
                    revision_id = EXCLUDED.revision_id,
                    chunk_count = EXCLUDED.chunk_count,
                    last_checked = NOW(),
                    last_updated = NOW()
            """, (ticker, page_title, page_url, revision_id, chunk_count))
            logger.info(f"Saved Wikipedia metadata for {ticker}")
    
    def get_wikipedia_revision(self, ticker: str) -> Optional[int]:
        """Get stored Wikipedia revision ID for ticker"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT revision_id FROM wikipedia_pages
                WHERE ticker = %s
            """, (ticker,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def mark_wikipedia_indexed(self, ticker: str):
        """Mark Wikipedia page as indexed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE wikipedia_pages
                SET indexed_in_vector_db = TRUE
                WHERE ticker = %s
            """, (ticker,))
    
    # ==================== NEWS OPERATIONS ====================
    
    def save_news_article(
        self,
        ticker: str,
        article_url: str,
        title: str,
        source: str,
        published_date: datetime,
        author: Optional[str] = None,
        retention_days: int = 3
    ) -> Optional[int]:
        """
        Save news article metadata
        
        Args:
            ticker: Company ticker
            article_url: Article URL
            title: Article title
            source: News source
            published_date: Publication date
            author: Optional author
            retention_days: Days to keep article (default: 3)
            
        Returns:
            Article ID or None if duplicate
        """
        delete_after = published_date + timedelta(days=retention_days)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO news_articles (
                        ticker, article_url, title, source, author,
                        published_date, delete_after
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (ticker, article_url, title, source, author, published_date, delete_after))
                
                article_id = cursor.fetchone()[0]
                logger.info(f"Saved news article: {title[:50]}... (ID: {article_id})")
                return article_id
                
            except psycopg2.IntegrityError:
                # Duplicate article URL
                logger.debug(f"Article already exists: {article_url}")
                return None
    
    def get_expired_news_articles(self) -> List[Dict[str, Any]]:
        """Get news articles that should be deleted"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, ticker, article_url, title
                FROM news_articles
                WHERE delete_after < NOW() AND indexed_in_vector_db = TRUE
            """)
            articles = cursor.fetchall()
            logger.info(f"Found {len(articles)} expired news articles")
            return [dict(row) for row in articles]
    
    def delete_news_articles(self, article_ids: List[int]):
        """Delete news articles by IDs"""
        if not article_ids:
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM news_articles
                WHERE id = ANY(%s)
            """, (article_ids,))
            logger.info(f"Deleted {len(article_ids)} news articles from database")
    
    def mark_news_indexed(self, article_id: int, chunk_count: int):
        """Mark news article as indexed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE news_articles
                SET indexed_in_vector_db = TRUE, chunk_count = %s
                WHERE id = %s
            """, (chunk_count, article_id))
    
    # ==================== STATISTICS ====================
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get overall pipeline statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Company count
            cursor.execute("SELECT COUNT(*) as count FROM companies")
            company_count = cursor.fetchone()['count']
            
            # Filing stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    SUM(total_chunks) as total_chunks
                FROM sec_filings
            """)
            filing_stats = dict(cursor.fetchone())
            
            # News stats
            cursor.execute("""
                SELECT COUNT(*) as count FROM news_articles
                WHERE delete_after > NOW()
            """)
            news_count = cursor.fetchone()['count']
            
            stats = {
                "companies": company_count,
                "filings": filing_stats,
                "news_articles": news_count,
                "timestamp": datetime.now().isoformat()
            }
            
            return stats
    
    def close(self):
        """Close connection pool"""
        self.pool.closeall()
        logger.info("Closed database connection pool")


