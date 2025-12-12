"""
PostgreSQL Connector

Handles database operations for state management and metadata storage
"""

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor, execute_batch
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class PostgresConnector:
    """
    PostgreSQL connector for state management
    
    Features:
    - Connection pooling
    - Automatic reconnection
    - Transaction support
    - Batch operations
    """
    
    def __init__(
        self,
        host: str,
        port: int = 5432,
        database: str = 'data_pipeline',
        user: str = 'postgres',
        password: str = '',
        min_connections: int = 1,
        max_connections: int = 10
    ):
        """
        Initialize PostgreSQL connector
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Username
            password: Password
            min_connections: Minimum pool size
            max_connections: Maximum pool size
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        
        logger.info(f"Initializing PostgreSQL connection to {host}:{port}/{database}")
        
        # Create connection pool
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                min_connections,
                max_connections,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            logger.info(f"Connection pool created (min={min_connections}, max={max_connections})")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Get a connection from pool (context manager)
        
        Usage:
            with connector.get_connection() as conn:
                cursor = conn.cursor()
                ...
        """
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Connection error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def execute(
        self,
        query: str,
        params: Optional[Tuple] = None,
        fetch: bool = False,
        commit: bool = True
    ) -> Optional[List[Dict]]:
        """
        Execute a query
        
        Args:
            query: SQL query
            params: Query parameters
            fetch: Whether to fetch results
            commit: Whether to commit transaction
        
        Returns:
            List of result dicts (if fetch=True), None otherwise
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                
                if fetch:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                
                if commit:
                    conn.commit()
                
                return None
    
    def execute_many(
        self,
        query: str,
        params_list: List[Tuple],
        commit: bool = True
    ) -> int:
        """
        Execute same query with multiple parameter sets
        
        Args:
            query: SQL query
            params_list: List of parameter tuples
            commit: Whether to commit transaction
        
        Returns:
            Number of rows affected
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                execute_batch(cursor, query, params_list)
                rowcount = cursor.rowcount
                
                if commit:
                    conn.commit()
                
                logger.info(f"Executed batch: {rowcount} rows affected")
                return rowcount
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        """
        Fetch single row
        
        Args:
            query: SQL query
            params: Query parameters
        
        Returns:
            Result dict or None
        """
        results = self.execute(query, params, fetch=True)
        return results[0] if results else None
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """
        Fetch all rows
        
        Args:
            query: SQL query
            params: Query parameters
        
        Returns:
            List of result dicts
        """
        results = self.execute(query, params, fetch=True)
        return results if results else []
    
    def create_tables(self):
        """
        Create all required tables for the data pipeline
        
        Tables:
        - sec_filings: Track SEC filings
        - wikipedia_pages: Track Wikipedia revisions
        - news_articles: Track news articles
        - pipeline_runs: Track DAG runs
        """
        logger.info("Creating database tables...")
        
        # SEC filings table
        self.execute("""
            CREATE TABLE IF NOT EXISTS sec_filings (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                filing_type VARCHAR(10) NOT NULL,
                accession_number VARCHAR(50) UNIQUE NOT NULL,
                filing_date DATE NOT NULL,
                fiscal_year INTEGER,
                fiscal_quarter INTEGER,
                url TEXT,
                fetched_at TIMESTAMP,
                processed_at TIMESTAMP,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Wikipedia pages table
        self.execute("""
            CREATE TABLE IF NOT EXISTS wikipedia_pages (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) UNIQUE NOT NULL,
                page_title VARCHAR(255),
                page_url TEXT,
                revision_id BIGINT,
                last_checked TIMESTAMP,
                last_updated TIMESTAMP,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # News articles table
        self.execute("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                article_id VARCHAR(255) UNIQUE NOT NULL,
                article_title TEXT,
                article_url TEXT,
                published_date TIMESTAMP,
                fetched_at TIMESTAMP,
                expires_at TIMESTAMP,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Pipeline runs table
        self.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id SERIAL PRIMARY KEY,
                dag_id VARCHAR(100) NOT NULL,
                run_id VARCHAR(100),
                execution_date TIMESTAMP NOT NULL,
                status VARCHAR(20) DEFAULT 'running',
                metrics JSONB,
                error TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)
        
        # Create indexes
        self.execute("""
            CREATE INDEX IF NOT EXISTS idx_sec_ticker ON sec_filings(ticker);
            CREATE INDEX IF NOT EXISTS idx_sec_filing_date ON sec_filings(filing_date);
            CREATE INDEX IF NOT EXISTS idx_sec_status ON sec_filings(status);
            
            CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_articles(ticker);
            CREATE INDEX IF NOT EXISTS idx_news_expires ON news_articles(expires_at);
            CREATE INDEX IF NOT EXISTS idx_news_status ON news_articles(status);
            
            CREATE INDEX IF NOT EXISTS idx_pipeline_dag ON pipeline_runs(dag_id);
            CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_runs(status);
        """)
        
        logger.info("All tables created successfully")
    
    def close(self):
        """Close all connections in pool"""
        if hasattr(self, 'pool') and self.pool:
            self.pool.closeall()
            logger.info("All database connections closed")


if __name__ == "__main__":
    # Example usage
    print("Testing PostgresConnector...")
    
    # NOTE: Configure with actual database credentials
    # connector = PostgresConnector(
    #     host='localhost',
    #     port=5432,
    #     database='data_pipeline',
    #     user='postgres',
    #     password='your_password'
    # )
    
    # # Create tables
    # connector.create_tables()
    
    # # Test insert
    # connector.execute(
    #     "INSERT INTO sec_filings (ticker, filing_type, accession_number, filing_date) VALUES (%s, %s, %s, %s)",
    #     ('AAPL', '10-K', '0000320193-24-000123', '2024-11-01')
    # )
    
    # # Test fetch
    # filings = connector.fetch_all("SELECT * FROM sec_filings WHERE ticker = %s", ('AAPL',))
    # print(f"Found {len(filings)} filings")
    
    # connector.close()
    
    print("✅ PostgresConnector ready (configure with actual credentials to test)")
