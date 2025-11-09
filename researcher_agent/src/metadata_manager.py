# researcher_agent/src/metadata_manager.py
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Optional

from utils.config import config


class MetadataManager:
    """Handles PostgreSQL metadata operations"""
    
    def __init__(self):
        self.connection_params = {
            'host': config.DB_HOST,
            'port': config.DB_PORT,
            'dbname': config.DB_NAME,
            'user': config.DB_USER,
            'password': config.DB_PASSWORD
        }
    
    def _get_connection(self):
        """Create a new database connection"""
        return psycopg2.connect(**self.connection_params)
    
    def check_filing_exists(self, accession_number: str) -> bool:
        """
        Check if a filing has already been processed
        
        Args:
            accession_number: Unique SEC accession number
            
        Returns:
            True if filing exists and is indexed
        """
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT indexed_in_vector_db 
                FROM filings 
                WHERE accession_number = %s
            """, (accession_number,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            return result is not None and result[0]
            
        except Exception as e:
            print(f"✗ Error checking filing existence: {e}")
            return False
    
    def get_company_filings(
        self, 
        ticker: str, 
        filing_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all processed filings for a company
        
        Args:
            ticker: Company ticker symbol
            filing_type: Optional filter by filing type
            
        Returns:
            List of filing records
        """
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            if filing_type:
                cur.execute("""
                    SELECT * FROM filings 
                    WHERE company_ticker = %s AND filing_type = %s
                    ORDER BY filing_date DESC
                """, (ticker, filing_type))
            else:
                cur.execute("""
                    SELECT * FROM filings 
                    WHERE company_ticker = %s
                    ORDER BY filing_date DESC
                """, (ticker,))
            
            results = cur.fetchall()
            cur.close()
            conn.close()
            
            return [dict(row) for row in results]
            
        except Exception as e:
            print(f"✗ Error fetching company filings: {e}")
            return []
    
    def save_filing_metadata(
        self,
        filing_metadata: Dict,
        sections_extracted: List[str],
        chunk_count: int
    ) -> bool:
        """
        Save or update filing metadata
        
        Args:
            filing_metadata: Filing metadata from SEC API
            sections_extracted: List of section codes extracted
            chunk_count: Total number of chunks created
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # First, ensure company exists
            cur.execute("""
                INSERT INTO company_metadata (company_ticker, company_cik, company_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (company_ticker) DO NOTHING
            """, (
                filing_metadata['ticker'],
                filing_metadata.get('cik', ''),
                filing_metadata['companyName']
            ))
            
            # Then insert/update filing
            cur.execute("""
                INSERT INTO filings (
                    company_ticker,
                    filing_type,
                    filing_date,
                    fiscal_period_end,
                    accession_number,
                    sections_extracted,
                    last_fetched,
                    chunk_count,
                    indexed_in_vector_db
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (accession_number) 
                DO UPDATE SET
                    sections_extracted = EXCLUDED.sections_extracted,
                    last_fetched = EXCLUDED.last_fetched,
                    chunk_count = EXCLUDED.chunk_count,
                    indexed_in_vector_db = EXCLUDED.indexed_in_vector_db
            """, (
                filing_metadata['ticker'],
                filing_metadata['formType'],
                filing_metadata['filedAt'].split('T')[0],  # Extract date part
                filing_metadata.get('periodOfReport', filing_metadata['filedAt'].split('T')[0]),
                filing_metadata['accessionNo'],
                sections_extracted,
                datetime.now(),
                chunk_count,
                True
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✓ Saved metadata for {filing_metadata['ticker']} {filing_metadata['formType']}")
            return True
            
        except Exception as e:
            print(f"✗ Error saving filing metadata: {e}")
            return False
    
    def get_latest_filing_date(
        self, 
        ticker: str, 
        filing_type: str
    ) -> Optional[str]:
        """
        Get the date of the most recent processed filing
        
        Args:
            ticker: Company ticker
            filing_type: Filing type
            
        Returns:
            Filing date string or None
        """
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT filing_date 
                FROM filings 
                WHERE company_ticker = %s AND filing_type = %s
                ORDER BY filing_date DESC
                LIMIT 1
            """, (ticker, filing_type))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            return result[0].isoformat() if result else None
            
        except Exception as e:
            print(f"✗ Error getting latest filing date: {e}")
            return None


# # Example usage
# if __name__ == "__main__":
#     metadata_manager = MetadataManager()
    
#     # Test: Check if filing exists
#     exists = metadata_manager.check_filing_exists("0000320193-24-000123")
#     print(f"Filing exists: {exists}")
    
#     # Test: Get company filings
#     filings = metadata_manager.get_company_filings("AAPL", "10-K")
#     print(f"\nFound {len(filings)} filings for AAPL")
    
#     for filing in filings[:3]:
#         print(f"  - {filing['filing_type']} filed {filing['filing_date']}: {filing['chunk_count']} chunks")