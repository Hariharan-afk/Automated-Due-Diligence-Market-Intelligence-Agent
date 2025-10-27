"""
Test configuration and logging utilities.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.logger import get_logger
from utils.config import get_config


def test_logger():
    """Test logger initialization."""
    print("\n" + "=" * 80)
    print("TEST 1: Logger Initialization")
    print("=" * 80)

    try:
        logger = get_logger("test_module")
        logger.info("This is an info message")
        logger.warning("This is a warning message")
        logger.error("This is an error message")

        print("[PASS] Logger initialized successfully")
        print("[PASS] Log messages written (check logs/ directory)")
        return True
    except Exception as e:
        print(f"[FAIL] Logger test failed: {e}")
        return False


def test_config():
    """Test configuration loading."""
    print("\n" + "=" * 80)
    print("TEST 2: Configuration Loading")
    print("=" * 80)

    try:
        config = get_config()

        # Test SEC API config
        print(f"\nSEC API Configuration:")
        print(f"  Base URL: {config.sec_api.base_url}")
        print(f"  Use Free API: {config.sec_api.use_free_api}")
        print(f"  Cache Enabled: {config.sec_api.cache_enabled}")
        print(f"  Rate Limit: {config.sec_api.rate_limit.calls_per_minute} calls/min")
        print(f"  Filing Types: {config.sec_api.filings.types}")
        print(f"  Years to Fetch: {config.sec_api.filings.years_to_fetch}")

        # Test Chunking config
        print(f"\nChunking Configuration:")
        print(f"  Chunk Size: {config.chunking.chunk_size} tokens")
        print(f"  Overlap: {config.chunking.overlap} tokens")
        print(f"  Preserve Tables: {config.chunking.preserve_tables}")
        print(f"  Table Context Paragraphs: {config.chunking.table_context_paragraphs}")

        # Test Vector Store config
        print(f"\nVector Store Configuration:")
        print(f"  Type: {config.vector_store.type}")
        print(f"  Embedding Model: {config.vector_store.embedding_model}")
        print(f"  Dimension: {config.vector_store.dimension}")

        # Test Database config
        print(f"\nDatabase Configuration:")
        print(f"  Path: {config.database.path}")

        # Verification checks
        checks = [
            (config.sec_api.base_url == "https://api.sec-api.io", "SEC API base URL correct"),
            (config.sec_api.use_free_api == True, "Use free API enabled"),
            (config.chunking.chunk_size == 500, "Chunk size is 500 tokens"),
            (config.chunking.preserve_tables == True, "Table preservation enabled"),
            (config.vector_store.type == "faiss", "Vector store is FAISS"),
            ("10-K" in config.sec_api.filings.types, "10-K filing type configured"),
            ("10-Q" in config.sec_api.filings.types, "10-Q filing type configured"),
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

        if all_passed:
            print("\n[PASS] All configuration tests passed")
        else:
            print("\n[FAIL] Some configuration tests failed")

        return all_passed

    except Exception as e:
        print(f"[FAIL] Config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_env_loading():
    """Test environment variable loading."""
    print("\n" + "=" * 80)
    print("TEST 3: Environment Variables")
    print("=" * 80)

    try:
        # Check if .env exists
        env_path = ".env"
        if not os.path.exists(env_path):
            print(f"[WARN] .env file not found at {env_path}")
            print("[INFO] Create .env file with SEC_API_KEY to test")
            return True

        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()

        # Check SEC API key
        sec_api_key = os.getenv("SEC_API_KEY")
        if sec_api_key and sec_api_key != "your_sec_api_key_here":
            print(f"[PASS] SEC_API_KEY loaded: {sec_api_key[:10]}...")
        else:
            print("[WARN] SEC_API_KEY not set or using placeholder value")
            print("[INFO] Set your actual API key in .env file")

        # Check other variables
        vars_to_check = [
            "ALERT_EMAIL_SENDER",
            "ALERT_EMAIL_PASSWORD",
            "ALERT_EMAIL_RECIPIENT",
            "SLACK_WEBHOOK_URL"
        ]

        print("\nOptional Environment Variables:")
        for var in vars_to_check:
            value = os.getenv(var)
            if value:
                print(f"  [SET] {var}")
            else:
                print(f"  [NOT SET] {var}")

        return True

    except Exception as e:
        print(f"[FAIL] Environment test failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("CONFIGURATION & LOGGING TESTS")
    print("=" * 80)

    results = []

    # Run tests
    results.append(("Logger", test_logger()))
    results.append(("Config", test_config()))
    results.append(("Environment", test_env_loading()))

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
