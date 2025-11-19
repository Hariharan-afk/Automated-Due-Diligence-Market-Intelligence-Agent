# scripts/setup/init_databases.py
"""Initialize PostgreSQL database schema"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from src.utils.config import config

def create_schema():
    """Create database schema"""
    
    print("🔌 Connecting to PostgreSQL...")
    
    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(
            host=config.database.postgres_host,
            port=config.database.postgres_port,
            database=config.database.postgres_database,
            user=config.database.postgres_user,
            password=config.database.postgres_password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print("✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    print("\n🗄️  Creating database schema...")
    
    # Create companies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            ticker VARCHAR(10) PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            cik VARCHAR(10) NOT NULL UNIQUE,
            sector VARCHAR(100),
            industry VARCHAR(100),
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Created table: companies")
    
    # Create sec_filings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sec_filings (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) REFERENCES companies(ticker),
            filing_type VARCHAR(10) NOT NULL CHECK (filing_type IN ('10-K', '10-Q')),
            filing_date DATE NOT NULL,
            fiscal_year INTEGER,
            fiscal_quarter INTEGER CHECK (fiscal_quarter BETWEEN 1 AND 4),
            fiscal_period_end DATE,
            accession_number VARCHAR(50) UNIQUE NOT NULL,
            filing_url TEXT,
            
            status VARCHAR(20) DEFAULT 'pending' 
                CHECK (status IN ('pending', 'fetched', 'processing', 'completed', 'failed')),
            error_message TEXT,
            
            sections_extracted TEXT[],
            total_chunks INTEGER DEFAULT 0,
            text_chunks INTEGER DEFAULT 0,
            table_chunks INTEGER DEFAULT 0,
            
            indexed_in_vector_db BOOLEAN DEFAULT FALSE,
            
            fetched_at TIMESTAMP,
            processed_at TIMESTAMP,
            indexed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(ticker, filing_type, fiscal_year, fiscal_quarter)
        )
    """)
    print("✅ Created table: sec_filings")
    
    # Create wikipedia_pages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wikipedia_pages (
            ticker VARCHAR(10) PRIMARY KEY REFERENCES companies(ticker),
            page_title VARCHAR(255) NOT NULL,
            page_url TEXT,
            revision_id BIGINT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            indexed_in_vector_db BOOLEAN DEFAULT FALSE,
            last_checked TIMESTAMP,
            last_updated TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Created table: wikipedia_pages")
    
    # Create news_articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) REFERENCES companies(ticker),
            article_url TEXT UNIQUE NOT NULL,
            title VARCHAR(500),
            source VARCHAR(200),
            author VARCHAR(200),
            published_date TIMESTAMP NOT NULL,
            ingested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delete_after TIMESTAMP NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            indexed_in_vector_db BOOLEAN DEFAULT FALSE,
            
            CONSTRAINT check_delete_date CHECK (delete_after > published_date)
        )
    """)
    print("✅ Created table: news_articles")
    
    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_filings_ticker_date 
        ON sec_filings(ticker, filing_date DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_filings_status 
        ON sec_filings(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_filings_accession 
        ON sec_filings(accession_number)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_ticker_published 
        ON news_articles(ticker, published_date DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_cleanup 
        ON news_articles(delete_after) WHERE indexed_in_vector_db = TRUE
    """)
    print("✅ Created indexes")
    
    # Insert companies from config
    print(f"\n📝 Inserting {len(config.companies)} companies from config...")
    inserted_count = 0
    for company in config.companies:
        try:
            cursor.execute("""
                INSERT INTO companies (ticker, company_name, cik, sector, industry)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (ticker) DO NOTHING
            """, (
                company['ticker'],
                company['name'],
                company['cik'],
                company.get('sector'),
                company.get('industry')
            ))
            if cursor.rowcount > 0:
                print(f"  ✅ {company['ticker']} - {company['name']}")
                inserted_count += 1
            else:
                print(f"  ⏭️  {company['ticker']} - already exists")
        except Exception as e:
            print(f"  ❌ {company['ticker']}: {e}")
    
    print(f"\n✅ Inserted {inserted_count} new companies")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM companies")
    total = cursor.fetchone()[0]
    print(f"✅ Total companies in database: {total}")
    
    cursor.close()
    conn.close()
    
    print("\n🎉 Database schema created successfully!")

if __name__ == "__main__":
    create_schema()