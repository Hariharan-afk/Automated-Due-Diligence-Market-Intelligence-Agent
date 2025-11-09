# researcher_agent/database/setup_database.py
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import os

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, parent_dir)

from utils.config import config


def create_database():
    """Create the database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server (default postgres database)
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{config.DB_NAME}'")
        exists = cur.fetchone()
        
        if not exists:
            cur.execute(f'CREATE DATABASE {config.DB_NAME}')
            print(f"✓ Created database: {config.DB_NAME}")
        else:
            print(f"✓ Database {config.DB_NAME} already exists")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ Error creating database: {e}")
        raise


def initialize_schema():
    """Initialize database schema from SQL file"""
    try:
        # Read SQL file
        sql_file_path = os.path.join(
            os.path.dirname(__file__),
            'init_db.sql'
        )
        
        print(f"Reading SQL file from: {sql_file_path}")
        
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Connect to the database
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        
        cur = conn.cursor()
        
        # Execute the entire script at once
        # psycopg2 can handle multi-statement scripts
        try:
            cur.execute(sql_script)
            conn.commit()
            print("✓ Database schema initialized successfully")
        except Exception as e:
            conn.rollback()
            print(f"✗ Error executing SQL script: {e}")
            raise
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ Error initializing schema: {e}")
        import traceback
        traceback.print_exc()
        raise


def verify_setup():
    """Verify that database and tables are set up correctly"""
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        cur = conn.cursor()
        
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        
        print("\n✓ Database setup verified")
        print(f"  Found {len(tables)} tables:")
        for table in tables:
            print(f"    - {table[0]}")
        
        # Check if required tables exist
        required_tables = ['company_metadata', 'filings']
        table_names = [t[0] for t in tables]
        
        for req_table in required_tables:
            if req_table in table_names:
                print(f"  ✓ Required table '{req_table}' exists")
            else:
                print(f"  ✗ Required table '{req_table}' missing!")
                return False
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"✗ Error verifying setup: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("PostgreSQL Database Setup for Researcher Agent")
    print("="*60 + "\n")
    
    try:
        # Validate configuration
        print("Validating configuration...")
        config.validate()
        print("✓ Configuration valid\n")
        
        # Create database
        print("Step 1: Creating database...")
        create_database()
        print()
        
        # Initialize schema
        print("Step 2: Initializing schema...")
        initialize_schema()
        print()
        
        # Verify setup
        print("Step 3: Verifying setup...")
        if verify_setup():
            print("\n" + "="*60)
            print("✓ Database setup complete!")
            print("="*60 + "\n")
        else:
            print("\n" + "="*60)
            print("✗ Database setup verification failed")
            print("="*60 + "\n")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ Setup failed: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)