"""
Test Docker Setup
Verifies that the Docker environment is properly configured
"""

import sys
import os
import time
import requests
import subprocess
from typing import Tuple

def print_header(text: str):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_status(test_name: str, passed: bool, message: str = ""):
    """Print test status"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {test_name}")
    if message:
        print(f"    {message}")

def test_python_version() -> Tuple[bool, str]:
    """Test Python version"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor} (need 3.9+)"

def test_imports() -> Tuple[bool, str]:
    """Test required package imports"""
    try:
        import numpy
        import pandas
        import qdrant_client
        import vertexai
        import sentence_transformers
        return True, "All required packages importable"
    except ImportError as e:
        return False, f"Missing package: {e}"

def test_qdrant_connection() -> Tuple[bool, str]:
    """Test Qdrant connection"""
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = os.getenv("QDRANT_PORT", "6333")
    
    try:
        url = f"http://{qdrant_host}:{qdrant_port}/healthz"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True, f"Connected to Qdrant at {qdrant_host}:{qdrant_port}"
        return False, f"Qdrant returned status {response.status_code}"
    except Exception as e:
        return False, f"Cannot connect to Qdrant: {e}"

def test_gcp_credentials() -> Tuple[bool, str]:
    """Test GCP credentials"""
    cred_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not cred_file:
        return False, "GOOGLE_APPLICATION_CREDENTIALS not set"
    
    if not os.path.exists(cred_file):
        return False, f"Credentials file not found: {cred_file}"
    
    try:
        from google.auth import default
        credentials, project = default()
        return True, f"GCP credentials valid (project: {project})"
    except Exception as e:
        return False, f"GCP credentials error: {e}"

def test_directories() -> Tuple[bool, str]:
    """Test required directories exist"""
    required_dirs = [
        "/app/agents",
        "/app/tools",
        "/app/validation",
        "/logs",
        "/data"
    ]
    
    missing = [d for d in required_dirs if not os.path.exists(d)]
    
    if missing:
        return False, f"Missing directories: {', '.join(missing)}"
    return True, "All required directories exist"

def test_agent_modules() -> Tuple[bool, str]:
    """Test agent modules can be imported"""
    try:
        from agents.analyser_agent import AnalyserAgent
        from agents.researcher_agent import ResearcherAgent
        from agents.synthesiser_agent import SynthesiserAgent
        from tools.hybrid_search import HybridSearchEngine
        from tools.reranker import Reranker
        return True, "All agent modules importable"
    except ImportError as e:
        return False, f"Cannot import agent module: {e}"

def test_validation_system() -> Tuple[bool, str]:
    """Test validation system"""
    try:
        from validation import ValidationPipeline, TestDataset
        dataset = TestDataset()
        test_cases = dataset.get_test_cases()
        return True, f"Validation system OK ({len(test_cases)} test cases)"
    except Exception as e:
        return False, f"Validation system error: {e}"

def test_qdrant_collections() -> Tuple[bool, str]:
    """Test Qdrant collections"""
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = os.getenv("QDRANT_PORT", "6333")
    
    try:
        url = f"http://{qdrant_host}:{qdrant_port}/collections"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            collections = data.get('result', {}).get('collections', [])
            if collections:
                names = [c['name'] for c in collections]
                return True, f"Collections found: {', '.join(names)}"
            return False, "No collections found (run: make generate-data)"
        return False, f"Error fetching collections: {response.status_code}"
    except Exception as e:
        return False, f"Cannot check collections: {e}"

def test_environment_config() -> Tuple[bool, str]:
    """Test environment configuration"""
    required_vars = [
        "QDRANT_HOST",
        "QDRANT_PORT",
        "PYTHONPATH"
    ]
    
    missing = [v for v in required_vars if not os.getenv(v)]
    
    if missing:
        return False, f"Missing environment variables: {', '.join(missing)}"
    
    env = os.getenv("ENVIRONMENT", "unknown")
    return True, f"Environment: {env}"

def run_all_tests():
    """Run all tests"""
    print_header("DOCKER SETUP VERIFICATION")
    
    tests = [
        ("Python Version", test_python_version),
        ("Package Imports", test_imports),
        ("Environment Config", test_environment_config),
        ("Directories", test_directories),
        ("Qdrant Connection", test_qdrant_connection),
        ("Qdrant Collections", test_qdrant_collections),
        ("GCP Credentials", test_gcp_credentials),
        ("Agent Modules", test_agent_modules),
        ("Validation System", test_validation_system),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            print_status(test_name, passed, message)
            results.append(passed)
        except Exception as e:
            print_status(test_name, False, f"Exception: {e}")
            results.append(False)
    
    # Summary
    print_header("SUMMARY")
    passed_count = sum(results)
    total_count = len(results)
    
    print(f"\nTests passed: {passed_count}/{total_count}")
    
    if all(results):
        print("\n✅ All tests passed! Docker setup is ready.")
        print("\nNext steps:")
        print("  1. Generate test data: make generate-data")
        print("  2. Run validation: make validate")
        return 0
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Ensure services are running: make up")
        print("  - Check .env configuration")
        print("  - Verify GCP credentials")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)