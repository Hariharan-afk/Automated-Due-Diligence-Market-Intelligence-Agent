"""
State Manager

Manages pipeline state in PostgreSQL to track:
- SEC filings fetched
- Wikipedia page revisions
- News articles
- Pipeline runs
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cloud.postgres_connector import PostgresConnector
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class StateManager:
    """
    Manages pipeline state tracking
    
    Features:
    - Track fetched SEC filings
    - Track Wikipedia page revisions
    - Track news articles with expiration
    - Track pipeline execution runs
    - Query unfetched/pending data
    """
    
    def __init__(self, postgres_connector: PostgresConnector):
        """
        Initialize state manager
        
        Args:
            postgres_connector: PostgresConnector instance
        """
        self.db = postgres_connector
        logger.info("StateManager initialized")
    
    # ==================== SEC FILINGS ====================
    
    def track_sec_filing(
        self,
        ticker: str,
        filing_type: str,
        accession_number: str,
        filing_date: str,
        fiscal_year: int,
        fiscal_quarter: Optional[int] = None,
        url: Optional[str] = None,
        status: str = 'pending'
    ) -> bool:
        """
        Track a SEC filing
        
        Args:
            ticker: Company ticker
            filing_type: '10-K' or '10-Q'
            accession_number: Unique SEC accession number
            filing_date: Filing date (YYYY-MM-DD)
            fiscal_year: Fiscal year
            fiscal_quarter: Fiscal quarter (for 10-Q)
            url: URL to filing
            status: 'pending', 'processing', 'completed', 'failed'
        
        Returns:
            True if successful
        """
        try:
            query = """
                INSERT INTO sec_filings 
                (ticker, filing_type, accession_number, filing_date, fiscal_year, fiscal_quarter, url, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (accession_number) DO UPDATE SET 
                    status = EXCLUDED.status,
                    url = COALESCE(EXCLUDED.url, sec_filings.url)
            """
            self.db.execute(
                query,
                (ticker, filing_type, accession_number, filing_date, fiscal_year, fiscal_quarter, url, status)
            )
            logger.debug(f"Tracked SEC filing: {ticker} {filing_type} {accession_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to track SEC filing: {e}")
            return False
    
    def mark_sec_filing_processed(
        self,
        accession_number: str,
        status: str = 'completed'
    ) -> bool:
        """
        Mark a filing as processed
        
        Args:
            accession_number: SEC accession number
            status: 'completed' or 'failed'
        
        Returns:
            True if successful
        """
        try:
            query = """
                UPDATE sec_filings 
                SET status = %s, processed_at = NOW()
                WHERE accession_number = %s
            """
            self.db.execute(query, (status, accession_number))
            logger.debug(f"Marked filing as {status}: {accession_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark filing: {e}")
            return False
    
    def get_sec_filing_status(self, accession_number: str) -> Optional[str]:
        """
        Get status of a SEC filing
        
        Args:
            accession_number: SEC accession number
        
        Returns:
            Status string or None if not found
        """
        result = self.db.fetch_one(
            "SELECT status FROM sec_filings WHERE accession_number = %s",
            (accession_number,)
        )
        return result['status'] if result else None
    
    def filing_exists(self, accession_number: str) -> bool:
        """Check if filing has been tracked"""
        return self.get_sec_filing_status(accession_number) is not None
    
    def get_pending_sec_filings(self, limit: int = 100) -> List[Dict]:
        """
        Get filings that need processing
        
        Args:
            limit: Max number of filings to return
        
        Returns:
            List of filing dicts
        """
        query = """
            SELECT * FROM sec_filings 
            WHERE status IN ('pending', 'failed')
            ORDER BY filing_date DESC
            LIMIT %s
        """
        return self.db.fetch_all(query, (limit,))
    
    def get_filings_for_company(
        self,
        ticker: str,
        filing_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get filings for a specific company
        
        Args:
            ticker: Company ticker
            filing_type: Optional filter by type
            limit: Max results
        
        Returns:
            List of filing dicts
        """
        if filing_type:
            query = """
                SELECT * FROM sec_filings 
                WHERE ticker = %s AND filing_type = %s
                ORDER BY filing_date DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (ticker, filing_type, limit))
        else:
            query = """
                SELECT * FROM sec_filings 
                WHERE ticker = %s
                ORDER BY filing_date DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (ticker, limit))
    
    # ==================== WIKIPEDIA ====================
    
    def track_wikipedia_page(
        self,
        ticker: str,
        page_title: str,
        page_url: str,
        revision_id: int,
        status: str = 'active'
    ) -> bool:
        """
        Track a Wikipedia page revision
        
        Args:
            ticker: Company ticker
            page_title: Wikipedia page title
            page_url: URL to page
            revision_id: Current revision ID
            status: 'active' or 'replaced'
        
        Returns:
            True if successful
        """
        try:
            query = """
                INSERT INTO wikipedia_pages 
                (ticker, page_title, page_url, revision_id, last_checked, last_updated, status)
                VALUES (%s, %s, %s, %s, NOW(), NOW(), %s)
                ON CONFLICT (ticker) DO UPDATE SET 
                    page_title = EXCLUDED.page_title,
                    page_url = EXCLUDED.page_url,
                    revision_id = EXCLUDED.revision_id,
                    last_checked = NOW(),
                    last_updated = CASE 
                        WHEN wikipedia_pages.revision_id != EXCLUDED.revision_id THEN NOW()
                        ELSE wikipedia_pages.last_updated
                    END,
                    status = EXCLUDED.status
            """
            self.db.execute(query, (ticker, page_title, page_url, revision_id, status))
            logger.debug(f"Tracked Wikipedia page: {ticker} (rev: {revision_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to track Wikipedia page: {e}")
            return False
    
    def update_wikipedia_check_time(self, ticker: str) -> bool:
        """Update last checked time for Wikipedia page"""
        try:
            query = "UPDATE wikipedia_pages SET last_checked = NOW() WHERE ticker = %s"
            self.db.execute(query, (ticker,))
            return True
        except Exception as e:
            logger.error(f"Failed to update check time: {e}")
            return False
    
    def get_wikipedia_revision(self, ticker: str) -> Optional[int]:
        """
        Get stored revision ID for a company
        
        Args:
            ticker: Company ticker
        
        Returns:
            Revision ID or None
        """
        result = self.db.fetch_one(
            "SELECT revision_id FROM wikipedia_pages WHERE ticker = %s",
            (ticker,)
        )
        return result['revision_id'] if result else None
    
    def get_all_wikipedia_pages(self) -> List[Dict]:
        """Get all tracked Wikipedia pages"""
        return self.db.fetch_all("SELECT * FROM wikipedia_pages ORDER BY ticker")
    
    def get_stale_wikipedia_pages(self, days: int = 7) -> List[Dict]:
        """
        Get Wikipedia pages that haven't been checked recently
        
        Args:
            days: Number of days to consider stale
        
        Returns:
            List of page dicts
        """
        query = """
            SELECT * FROM wikipedia_pages 
            WHERE last_checked < NOW() - INTERVAL '%s days'
            OR last_checked IS NULL
            ORDER BY last_checked ASC NULLS FIRST
        """
        return self.db.fetch_all(query, (days,))
    
    # ==================== NEWS ARTICLES ====================
    
    def track_news_article(
        self,
        ticker: str,
        article_id: str,
        article_title: str,
        article_url: str,
        published_date: datetime,
        status: str = 'active'
    ) -> bool:
        """
        Track a news article
        
        Args:
            ticker: Company ticker
            article_id: Unique article ID
            article_title: Article title
            article_url: URL to article
            published_date: When article was published
            status: 'active' or 'deleted'
        
        Returns:
            True if successful
        """
        try:
            # Calculate expiration (6 months from publish)
            expires_at = published_date + timedelta(days=180)
            
            query = """
                INSERT INTO news_articles 
                (ticker, article_id, article_title, article_url, published_date, fetched_at, expires_at, status)
                VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)
                ON CONFLICT (article_id) DO UPDATE SET 
                    status = EXCLUDED.status
            """
            self.db.execute(
                query,
                (ticker, article_id, article_title, article_url, published_date, expires_at, status)
            )
            logger.debug(f"Tracked news article: {ticker} - {article_title[:50]}")
            return True
        except Exception as e:
            logger.error(f"Failed to track news article: {e}")
            return False
    
    def article_exists(self, article_id: str) -> bool:
        """Check if article has been tracked"""
        result = self.db.fetch_one(
            "SELECT id FROM news_articles WHERE article_id = %s",
            (article_id,)
        )
        return result is not None
    
    def get_expired_news(self) -> List[Dict]:
        """
        Get news articles that have expired (>6 months old)
        
        Returns:
            List of expired article dicts
        """
        query = """
            SELECT * FROM news_articles 
            WHERE expires_at < NOW() AND status = 'active'
            ORDER BY expires_at ASC
        """
        return self.db.fetch_all(query)
    
    def mark_news_deleted(self, article_ids: List[str]) -> int:
        """
        Mark multiple news articles as deleted
        
        Args:
            article_ids: List of article IDs to mark
        
        Returns:
            Number of articles marked
        """
        if not article_ids:
            return 0
        
        try:
            query = """
                UPDATE news_articles 
                SET status = 'deleted'
                WHERE article_id = ANY(%s)
            """
            return self.db.execute_many(
                "UPDATE news_articles SET status = 'deleted' WHERE article_id = %s",
                [(aid,) for aid in article_ids]
            )
        except Exception as e:
            logger.error(f"Failed to mark news as deleted: {e}")
            return 0
    
    def get_news_for_company(self, ticker: str, limit: int = 100) -> List[Dict]:
        """Get recent news for a company"""
        query = """
            SELECT * FROM news_articles 
            WHERE ticker = %s AND status = 'active'
            ORDER BY published_date DESC
            LIMIT %s
        """
        return self.db.fetch_all(query, (ticker, limit))
    
    # ==================== PIPELINE RUNS ====================
    
    def track_pipeline_run(
        self,
        dag_id: str,
        run_id: str,
        execution_date: datetime,
        status: str = 'running',
        metrics: Optional[Dict] = None
    ) -> int:
        """
        Track a pipeline run
        
        Args:
            dag_id: DAG identifier
            run_id: Unique run ID
            execution_date: When run started
            status: 'running', 'completed', 'failed'
            metrics: Optional metrics dict
        
        Returns:
            Run ID (database primary key)
        """
        try:
            import json
            query = """
                INSERT INTO pipeline_runs 
                (dag_id, run_id, execution_date, status, metrics)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """
            result = self.db.fetch_one(
                query,
                (dag_id, run_id, execution_date, status, json.dumps(metrics) if metrics else None)
            )
            run_pk = result['id']
            logger.info(f"Started tracking pipeline run: {dag_id} ({run_id})")
            return run_pk
        except Exception as e:
            logger.error(f"Failed to track pipeline run: {e}")
            return -1
    
    def update_pipeline_run(
        self,
        run_pk: int,
        status: str,
        metrics: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update a pipeline run
        
        Args:
            run_pk: Run primary key from track_pipeline_run
            status: New status
            metrics: Updated metrics
            error: Error message if failed
        
        Returns:
            True if successful
        """
        try:
            import json
            query = """
                UPDATE pipeline_runs 
                SET status = %s, 
                    metrics = %s,
                    error = %s,
                    completed_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE completed_at END
                WHERE id = %s
            """
            self.db.execute(
                query,
                (status, json.dumps(metrics) if metrics else None, error, status, run_pk)
            )
            logger.debug(f"Updated pipeline run {run_pk}: {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update pipeline run: {e}")
            return False
    
    def get_recent_pipeline_runs(self, dag_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Get recent pipeline runs
        
        Args:
            dag_id: Optional filter by DAG
            limit: Max results
        
        Returns:
            List of run dicts
        """
        if dag_id:
            query = """
                SELECT * FROM pipeline_runs 
                WHERE dag_id = %s
                ORDER BY execution_date DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (dag_id, limit))
        else:
            query = """
                SELECT * FROM pipeline_runs 
                ORDER BY execution_date DESC
                LIMIT %s
            """
            return self.db.fetch_all(query, (limit,))
    
    # ==================== STATISTICS ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall statistics
        
        Returns:
            Dict with counts and metrics
        """
        stats = {}
        
        # SEC filings
        sec_stats = self.db.fetch_one("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM sec_filings
        """)
        stats['sec_filings'] = dict(sec_stats) if sec_stats else {}
        
        # Wikipedia pages
        wiki_stats = self.db.fetch_one("""
            SELECT COUNT(*) as total FROM wikipedia_pages
        """)
        stats['wikipedia_pages'] = dict(wiki_stats) if wiki_stats else {}
        
        # News articles
        news_stats = self.db.fetch_one("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active,
                COUNT(CASE WHEN expires_at < NOW() AND status = 'active' THEN 1 END) as expired
            FROM news_articles
        """)
        stats['news_articles'] = dict(news_stats) if news_stats else {}
        
        # Pipeline runs
        pipeline_stats = self.db.fetch_one("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN status = 'running' THEN 1 END) as running
            FROM pipeline_runs
        """)
        stats['pipeline_runs'] = dict(pipeline_stats) if pipeline_stats else {}
        
        return stats


if __name__ == "__main__":
    # Example usage
    print("Testing StateManager...")
    
    # NOTE: Requires PostgreSQL connection
    # from src.cloud import PostgresConnector
    # 
    # db = PostgresConnector(
    #     host='localhost',
    #     database='data_pipeline',
    #     user='postgres',
    #     password='password'
    # )
    # db.create_tables()
    # 
    # state = StateManager(db)
    # 
    # # Track a SEC filing
    # state.track_sec_filing(
    #     ticker='AAPL',
    #     filing_type='10-K',
    #     accession_number='0000320193-24-000123',
    #     filing_date='2024-11-01',
    #     fiscal_year=2024,
    #     url='https://sec.gov/...'
    # )
    # 
    # # Check if already tracked
    # if state.filing_exists('0000320193-24-000123'):
    #     print("Filing already tracked!")
    # 
    # # Get stats
    # stats = state.get_stats()
    # print(f"Stats: {stats}")
    # 
    # db.close()
    
    print("✅ StateManager ready (configure with actual database to test)")
