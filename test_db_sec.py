"""
Test database manager SEC functions.
"""

import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from db_manager import (
    init_db,
    insert_company,
    is_filing_cached,
    insert_sec_filing,
    get_sec_filings
)


def test_database_creation():
    """Test database creation with SEC_Filings table."""
    print("\n" + "=" * 80)
    print("TEST 1: Database Creation")
    print("=" * 80)

    try:
        # Use test database
        test_db = "test_company_data.db"

        # Remove existing test db
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"[INFO] Removed existing test database: {test_db}")

        # Create database
        init_db(test_db)

        # Connect to database
        import sqlite3
        conn = sqlite3.connect(test_db)

        # Check if tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"\nTables created: {tables}")

        expected_tables = ['Company_Info', 'SEC_Filings']
        checks = [
            ('Company_Info' in tables, "Company_Info table exists"),
            ('SEC_Filings' in tables, "SEC_Filings table exists"),
        ]

        # Check SEC_Filings schema
        cursor.execute("PRAGMA table_info(SEC_Filings)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        print(f"\nSEC_Filings columns: {column_names}")

        required_columns = [
            'filing_id', 'company_id', 'ticker', 'cik', 'filing_type',
            'filing_date', 'fiscal_year', 'fiscal_period', 'accession_number',
            'filing_url', 'sections', 'extraction_date'
        ]

        for col in required_columns:
            checks.append((col in column_names, f"Column '{col}' exists"))

        print("\n" + "-" * 80)
        print("Verification Checks:")
        print("-" * 80)

        all_passed = True
        for passed, description in checks:
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status}: {description}")
            if not passed:
                all_passed = False

        conn.close()

        if all_passed:
            print("\n[PASS] Database creation test passed")
        else:
            print("\n[FAIL] Database creation test failed")

        return all_passed, test_db

    except Exception as e:
        print(f"[FAIL] Database creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_sec_filing_operations(test_db):
    """Test SEC filing insert and cache check."""
    print("\n" + "=" * 80)
    print("TEST 2: SEC Filing Operations")
    print("=" * 80)

    try:
        import sqlite3
        conn = sqlite3.connect(test_db)

        # First, insert a test company
        company_id = insert_company(
            conn,
            name="Apple Inc.",
            ticker="AAPL",
            summary="Apple Inc. designs and manufactures consumer electronics.",
            url="https://en.wikipedia.org/wiki/Apple_Inc.",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        print(f"[INFO] Inserted test company with ID: {company_id}")

        # Test data
        test_sections = {
            "Item 1": "Business section text with ##TABLE_START data ##TABLE_END",
            "Item 1A": "Risk factors text",
            "Item 7": "MD&A text",
            "Item 8": "Financial statements with tables"
        }

        # Insert SEC filing
        accession_number = "0000320193-24-000123"
        filing_id = insert_sec_filing(
            conn,
            company_id=company_id,
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date="2024-10-26",
            fiscal_year=2024,
            fiscal_period="FY",
            accession_number=accession_number,
            filing_url="https://www.sec.gov/Archives/edgar/data/320193/...",
            sections=json.dumps(test_sections),
            extraction_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        print(f"[INFO] Inserted SEC filing with ID: {filing_id}")

        # Test cache check
        is_cached = is_filing_cached(accession_number, test_db)
        print(f"[INFO] Cache check result: {is_cached}")

        # Test retrieval
        filings = get_sec_filings(conn, ticker="AAPL")
        print(f"[INFO] Retrieved {len(filings)} filings for AAPL")

        if filings:
            filing = filings[0]
            print(f"\nRetrieved Filing Details:")
            print(f"  Ticker: {filing['ticker']}")
            print(f"  Filing Type: {filing['filing_type']}")
            print(f"  Filing Date: {filing['filing_date']}")
            print(f"  Accession Number: {filing['accession_number']}")
            print(f"  Sections: {list(filing['sections'].keys())}")

        # Verification checks
        checks = [
            (filing_id is not None, "Filing inserted successfully"),
            (is_cached == True, "Filing cache check works"),
            (len(filings) == 1, "Retrieved 1 filing for AAPL"),
            (filings[0]['ticker'] == 'AAPL', "Ticker matches"),
            (filings[0]['filing_type'] == '10-K', "Filing type matches"),
            (filings[0]['accession_number'] == accession_number, "Accession number matches"),
        ]

        print("\n" + "-" * 80)
        print("Verification Checks:")
        print("-" * 80)

        all_passed = True
        for passed, description in checks:
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status}: {description}")
            if not passed:
                all_passed = False

        # Test duplicate prevention
        print("\n" + "-" * 80)
        print("Testing Duplicate Prevention:")
        print("-" * 80)

        try:
            # Try to insert same filing again
            duplicate_id = insert_sec_filing(
                conn,
                company_id=company_id,
                ticker="AAPL",
                cik="0000320193",
                filing_type="10-K",
                filing_date="2024-10-26",
                fiscal_year=2024,
                fiscal_period="FY",
                accession_number=accession_number,  # Same accession number
                filing_url="https://www.sec.gov/Archives/edgar/data/320193/...",
                sections=json.dumps(test_sections),
                extraction_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # Should return None (duplicate detected)
            if duplicate_id is None:
                print(f"[PASS] Duplicate prevention works - returned None (duplicate detected)")
            else:
                print(f"[WARN] Inserted duplicate with ID: {duplicate_id}")
                all_passed = False

        except Exception as e:
            print(f"[INFO] Duplicate insert raised exception: {e}")
            # This is actually expected behavior in some implementations
            checks.append((True, "Duplicate prevention raises exception"))

        conn.close()

        if all_passed:
            print("\n[PASS] SEC filing operations test passed")
        else:
            print("\n[FAIL] SEC filing operations test failed")

        return all_passed

    except Exception as e:
        print(f"[FAIL] SEC filing operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("DATABASE SEC FUNCTIONS TESTS")
    print("=" * 80)

    results = []

    # Test 1: Database creation
    passed1, test_db = test_database_creation()
    results.append(("Database Creation", passed1))

    # Test 2: SEC filing operations (only if DB created successfully)
    if passed1 and test_db:
        passed2 = test_sec_filing_operations(test_db)
        results.append(("SEC Filing Operations", passed2))

        # Cleanup
        print("\n" + "-" * 80)
        print(f"[INFO] Test database '{test_db}' created for inspection")
        print(f"[INFO] You can delete it manually or keep it for reference")
    else:
        print("\n[FAIL] Skipping SEC filing operations test due to DB creation failure")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80 + "\n")
    else:
        print("\n" + "=" * 80)
        print("SOME TESTS FAILED!")
        print("=" * 80 + "\n")
