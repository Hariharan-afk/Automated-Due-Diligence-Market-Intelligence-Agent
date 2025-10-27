"""
Database Manager Module - FINAL VERSION
Handles SQLite database operations
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db(db_path="data/company_data.db"):
    """Initialize database with required tables"""
    logger.info(f"🔧 Initializing database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Company Info Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Company_Info (
        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        ticker TEXT,
        summary TEXT,
        wiki_url TEXT,
        timestamp TEXT NOT NULL
    )
    """)

    # News Articles Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS News_Articles (
        article_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        source TEXT,
        published_date TEXT,
        article_summary TEXT,
        FOREIGN KEY(company_id) REFERENCES Company_Info(company_id)
    )
    """)

    # SEC Filings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS SEC_Filings (
        filing_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        cik TEXT NOT NULL,
        filing_type TEXT NOT NULL,
        filing_date TEXT NOT NULL,
        fiscal_year INTEGER,
        fiscal_period TEXT,
        accession_number TEXT UNIQUE NOT NULL,
        filing_url TEXT,
        sections TEXT,
        extraction_date TEXT NOT NULL,
        FOREIGN KEY(company_id) REFERENCES Company_Info(company_id)
    )
    """)

    # Create indexes for faster lookups
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_sec_accession
    ON SEC_Filings(accession_number)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_sec_ticker_type
    ON SEC_Filings(ticker, filing_type)
    """)

    conn.commit()
    conn.close()

    logger.info("✅ Database initialized successfully")


def insert_company(conn, name, ticker, summary, url, timestamp):
    """
    Insert company record into database
    
    Args:
        conn: SQLite connection
        name: Company name
        ticker: Stock ticker symbol
        summary: Company summary from Wikipedia
        url: Wikipedia URL
        timestamp: Timestamp of data collection
    
    Returns:
        company_id: ID of inserted company
    """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Company_Info (company_name, ticker, summary, wiki_url, timestamp) VALUES (?, ?, ?, ?, ?)",
        (name, ticker, summary, url, timestamp)
    )
    conn.commit()
    
    company_id = cursor.lastrowid
    logger.info(f"✅ Inserted company: {name} (ID: {company_id})")
    
    return company_id


def insert_article(conn, company_id, title, url, source, date, summary):
    """
    Insert news article into database
    
    Args:
        conn: SQLite connection
        company_id: Foreign key to Company_Info
        title: Article title
        url: Article URL
        source: News source
        date: Publication date
        summary: Article summary
    """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO News_Articles (company_id, title, url, source, published_date, article_summary) VALUES (?, ?, ?, ?, ?, ?)",
        (company_id, title, url, source, date, summary)
    )
    conn.commit()


def get_company(conn, company_name):
    """
    Retrieve company information by name
    
    Args:
        conn: SQLite connection
        company_name: Name of company to retrieve
        
    Returns:
        Dictionary with company information or None
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM Company_Info WHERE company_name = ?",
        (company_name,)
    )
    row = cursor.fetchone()
    
    if row:
        return {
            "company_id": row[0],
            "company_name": row[1],
            "ticker": row[2],
            "summary": row[3],
            "wiki_url": row[4],
            "timestamp": row[5]
        }
    return None


def get_articles(conn, company_id):
    """
    Retrieve all articles for a company
    
    Args:
        conn: SQLite connection
        company_id: ID of company
        
    Returns:
        List of article dictionaries
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM News_Articles WHERE company_id = ?",
        (company_id,)
    )
    rows = cursor.fetchall()
    
    articles = []
    for row in rows:
        articles.append({
            "article_id": row[0],
            "company_id": row[1],
            "title": row[2],
            "url": row[3],
            "source": row[4],
            "published_date": row[5],
            "article_summary": row[6]
        })
    
    return articles


def insert_sec_filing(conn, company_id, ticker, cik, filing_type, filing_date,
                       fiscal_year, fiscal_period, accession_number, filing_url,
                       sections, extraction_date):
    """
    Insert SEC filing into database.

    Args:
        conn: SQLite connection
        company_id: Foreign key to Company_Info
        ticker: Company ticker symbol
        cik: SEC CIK number
        filing_type: Type of filing (10-K, 10-Q, etc.)
        filing_date: Date of filing
        fiscal_year: Fiscal year
        fiscal_period: Fiscal period
        accession_number: SEC accession number (unique)
        filing_url: URL to filing
        sections: JSON string of extracted sections
        extraction_date: When data was extracted

    Returns:
        filing_id: ID of inserted filing or None if duplicate
    """
    import json

    cursor = conn.cursor()

    # Convert sections dict to JSON string if needed
    if isinstance(sections, dict):
        sections_json = json.dumps(sections)
    else:
        sections_json = sections

    try:
        cursor.execute("""
            INSERT INTO SEC_Filings
            (company_id, ticker, cik, filing_type, filing_date, fiscal_year,
             fiscal_period, accession_number, filing_url, sections, extraction_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (company_id, ticker, cik, filing_type, filing_date, fiscal_year,
              fiscal_period, accession_number, filing_url, sections_json, extraction_date))

        conn.commit()
        filing_id = cursor.lastrowid
        logger.info(f"✅ Inserted SEC filing: {ticker} {filing_type} {accession_number} (ID: {filing_id})")
        return filing_id

    except sqlite3.IntegrityError as e:
        logger.warning(f"⚠️ Filing {accession_number} already exists in database")
        return None


def is_filing_cached(accession_number, db_path="data/company_data.db"):
    """
    Check if SEC filing is already in database cache.

    Args:
        accession_number: SEC accession number
        db_path: Path to database

    Returns:
        True if cached, False otherwise
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT filing_id FROM SEC_Filings
        WHERE accession_number = ?
    """, (accession_number,))

    result = cursor.fetchone()
    conn.close()

    return result is not None


def get_sec_filing(conn, accession_number):
    """
    Retrieve SEC filing by accession number.

    Args:
        conn: SQLite connection
        accession_number: SEC accession number

    Returns:
        Dictionary with filing information or None
    """
    import json

    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM SEC_Filings
        WHERE accession_number = ?
    """, (accession_number,))

    row = cursor.fetchone()

    if row:
        # Parse sections JSON
        sections = json.loads(row[9]) if row[9] else {}

        return {
            "filing_id": row[0],
            "company_id": row[1],
            "ticker": row[2],
            "cik": row[3],
            "filing_type": row[4],
            "filing_date": row[5],
            "fiscal_year": row[6],
            "fiscal_period": row[7],
            "accession_number": row[8],
            "filing_url": row[9],
            "sections": sections,
            "extraction_date": row[11]
        }
    return None


def get_sec_filings(conn, ticker=None, filing_type=None, company_id=None):
    """
    Retrieve SEC filings with optional filters.

    Args:
        conn: SQLite connection
        ticker: Filter by ticker symbol (optional)
        filing_type: Filter by filing type (optional)
        company_id: Filter by company ID (optional)

    Returns:
        List of filing dictionaries
    """
    import json

    cursor = conn.cursor()

    # Build query based on filters
    query = "SELECT * FROM SEC_Filings WHERE 1=1"
    params = []

    if company_id:
        query += " AND company_id = ?"
        params.append(company_id)

    if ticker:
        query += " AND ticker = ?"
        params.append(ticker.upper())

    if filing_type:
        query += " AND filing_type = ?"
        params.append(filing_type)

    query += " ORDER BY filing_date DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    filings = []
    for row in rows:
        sections = json.loads(row[10]) if row[10] else {}

        filings.append({
            "filing_id": row[0],
            "company_id": row[1],
            "ticker": row[2],
            "cik": row[3],
            "filing_type": row[4],
            "filing_date": row[5],
            "fiscal_year": row[6],
            "fiscal_period": row[7],
            "accession_number": row[8],
            "filing_url": row[9],
            "sections": sections,
            "extraction_date": row[11]
        })

    return filings


def export_to_csv(db_path="data/company_data.db", export_dir="exports"):
    """
    Export database tables to CSV files
    
    Args:
        db_path: Path to SQLite database
        export_dir: Directory to save CSV files
    """
    import os
    import csv
    
    os.makedirs(export_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Export Company_Info table
    cursor.execute("SELECT * FROM Company_Info")
    company_rows = cursor.fetchall()
    company_headers = [desc[0] for desc in cursor.description]

    with open(os.path.join(export_dir, "company_info.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(company_headers)
        writer.writerows(company_rows)

    # Export News_Articles table
    cursor.execute("SELECT * FROM News_Articles")
    news_rows = cursor.fetchall()
    news_headers = [desc[0] for desc in cursor.description]

    with open(os.path.join(export_dir, "news_articles.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(news_headers)
        writer.writerows(news_rows)

    # Export SEC_Filings table
    cursor.execute("SELECT * FROM SEC_Filings")
    sec_rows = cursor.fetchall()
    sec_headers = [desc[0] for desc in cursor.description]

    with open(os.path.join(export_dir, "sec_filings.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(sec_headers)
        writer.writerows(sec_rows)

    conn.close()
    logger.info(f"📤 Export complete! CSVs saved in '{export_dir}/' directory")


def main():
    """Example usage"""
    import os
    from datetime import datetime
    
    # Initialize database
    db_path = "data/company_data.db"
    os.makedirs("data", exist_ok=True)
    
    init_db(db_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Insert sample company
    company_id = insert_company(
        conn,
        name="Apple Inc",
        ticker="AAPL",
        summary="Apple is a technology company...",
        url="https://en.wikipedia.org/wiki/Apple_Inc",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Insert sample article
    insert_article(
        conn,
        company_id=company_id,
        title="Apple announces new product",
        url="https://example.com/article1",
        source="TechCrunch",
        date="2024-10-24",
        summary="Apple has announced..."
    )
    
    # Retrieve company
    company = get_company(conn, "Apple Inc")
    print(f"\nRetrieved Company: {company}")
    
    # Retrieve articles
    articles = get_articles(conn, company_id)
    print(f"Articles: {len(articles)}")
    
    conn.close()
    
    # Export to CSV
    export_to_csv(db_path)
    
    print("\n✅ Database operations complete!")


if __name__ == "__main__":
    main()