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