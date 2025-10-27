"""
Master test runner for all SEC integration tests.
Runs all test suites in sequence and provides comprehensive summary.
"""

import subprocess
import sys
from datetime import datetime


def run_test_script(script_name, description):
    """Run a test script and return success status."""
    print("\n" + "=" * 100)
    print(f"RUNNING: {description}")
    print("=" * 100)

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=False,
            text=True,
            timeout=60
        )

        success = result.returncode == 0
        return success

    except subprocess.TimeoutExpired:
        print(f"\n[FAIL] Test timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"\n[FAIL] Error running test: {e}")
        return False


def main():
    """Run all test suites."""
    print("\n" + "=" * 100)
    print(" " * 30 + "SEC INTEGRATION TEST SUITE")
    print(" " * 35 + f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)

    # Test suite configuration
    test_suites = [
        ("test_config_logger.py", "Configuration & Logging Tests"),
        ("test_db_sec.py", "Database SEC Functions Tests"),
        ("test_chunking_sec.py", "SEC Table Extraction Tests"),
        ("test_sec_fetcher_mock.py", "SEC Fetcher Mock Tests"),
    ]

    results = []

    # Run each test suite
    for script, description in test_suites:
        try:
            success = run_test_script(script, description)
            results.append((description, success))
        except Exception as e:
            print(f"\n[ERROR] Failed to run {script}: {e}")
            results.append((description, False))

    # Print comprehensive summary
    print("\n" + "=" * 100)
    print(" " * 40 + "FINAL TEST SUMMARY")
    print("=" * 100)

    passed_count = 0
    failed_count = 0

    for test_name, success in results:
        if success:
            print(f"[PASS] {test_name}")
            passed_count += 1
        else:
            print(f"[FAIL] {test_name}")
            failed_count += 1

    print("\n" + "-" * 100)
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Success Rate: {(passed_count / len(results) * 100):.1f}%")
    print("-" * 100)

    if all(result[1] for result in results):
        print("\n" + "=" * 100)
        print(" " * 35 + "ALL TEST SUITES PASSED!")
        print("=" * 100)
        print("\n[INFO] Your SEC integration is ready for deployment!")
        print("\nNext Steps:")
        print("1. Set SEC_API_KEY in .env file for live testing")
        print("2. Download company_tickers.json to data/ directory")
        print("3. Continue with remaining implementation (preprocessing, validation, etc.)")
        return 0
    else:
        print("\n" + "=" * 100)
        print(" " * 35 + "SOME TEST SUITES FAILED!")
        print("=" * 100)
        print("\n[INFO] Please review the failures above and fix issues before proceeding.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
