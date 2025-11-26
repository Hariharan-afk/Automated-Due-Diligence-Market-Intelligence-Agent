"""
validation/test_dataset.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generate test dataset from Qdrant data for validation
"""

import sys
sys.path.append('.')

import json
from typing import List, Dict
from datetime import datetime

class TestDataset:
    """Generate and manage test queries with ground truth"""
    
    def __init__(self, filepath: str = "src/model_validation/test_dataset.json"):
        import os
        
        if os.path.exists(filepath):
            print(f"📂 Loading test dataset from {filepath}...")
            self.test_cases = self.load_from_file(filepath)
        else:
            print("⚠️ Synthetic test dataset not found. Falling back to hardcoded fake data.")
            # These match the fake companies in generate_and_store.py
            self.companies = [
                {"name": "TechCorp", "ticker": "TECH", "cik": "0001234567"},
                {"name": "FinanceInc", "ticker": "FIN", "cik": "0001234568"},
                {"name": "HealthPlus", "ticker": "HLTH", "cik": "0001234569"},
            ]
            self.test_cases = self._generate_test_cases()
    
    def _generate_test_cases(self) -> List[Dict]:
        """Generate test cases with ground truth"""
        cases = []
        
        for company in self.companies:
            # Test Case 1: Basic company info (from Wikipedia)
            cases.append({
                "query_id": f"{company['ticker']}_01",
                "query": f"What is {company['name']}?",
                "company": company['name'],
                "ticker": company['ticker'],
                "expected_answer_contains": [
                    company['name'],
                    "leading company",
                    "Founded"
                ],
                "required_sources": ["wikipedia"],
                "required_sections": ["Company Overview"],
                "evaluation_type": "contains"  # Check if expected strings are present
            })
            
            # Test Case 2: Financial performance (from SEC filings)
            cases.append({
                "query_id": f"{company['ticker']}_02",
                "query": f"What was {company['name']}'s revenue in Q1 2024?",
                "company": company['name'],
                "ticker": company['ticker'],
                "expected_answer_contains": [
                    "revenue",
                    "Q1 2024",
                    "$",
                    "M"  # Millions
                ],
                "required_sources": ["sec"],
                "required_sections": ["Financial Performance"],
                "evaluation_type": "contains"
            })
            
            # Test Case 3: Growth analysis (requires calculation from SEC)
            cases.append({
                "query_id": f"{company['ticker']}_03",
                "query": f"Analyze {company['name']}'s revenue growth over the past year",
                "company": company['name'],
                "ticker": company['ticker'],
                "expected_answer_contains": [
                    "growth",
                    "revenue",
                    "%"
                ],
                "required_sources": ["sec"],
                "required_sections": ["Financial Performance", "Growth Analysis"],
                "evaluation_type": "contains"
            })
            
            # Test Case 4: Recent news (from news data)
            cases.append({
                "query_id": f"{company['ticker']}_04",
                "query": f"What are the latest developments at {company['name']}?",
                "company": company['name'],
                "ticker": company['ticker'],
                "expected_answer_contains": [
                    company['name'],
                    "news"
                ],
                "required_sources": ["news"],
                "required_sections": ["Recent Developments"],
                "evaluation_type": "contains"
            })
            
            # Test Case 5: Comprehensive due diligence
            cases.append({
                "query_id": f"{company['ticker']}_05",
                "query": f"Provide a comprehensive due diligence report for {company['name']}",
                "company": company['name'],
                "ticker": company['ticker'],
                "expected_answer_contains": [
                    company['name'],
                    "revenue",
                    "founded"
                ],
                "required_sources": ["sec", "wikipedia", "news"],
                "required_sections": [
                    "Company Overview",
                    "Financial Performance",
                    "Recent Developments"
                ],
                "evaluation_type": "comprehensive"
            })
        
        return cases
    
    def get_test_cases(self, query_ids: List[str] = None) -> List[Dict]:
        """Get all or specific test cases"""
        if query_ids:
            return [tc for tc in self.test_cases if tc['query_id'] in query_ids]
        return self.test_cases
    
    def save_to_file(self, filepath: str = "Model_Validation/test_dataset.json"):
        """Save test dataset to JSON file"""
        with open(filepath, 'w') as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "num_test_cases": len(self.test_cases),
                "test_cases": self.test_cases
            }, f, indent=2)
        print(f"✅ Test dataset saved to {filepath}")
    
    @staticmethod
    def load_from_file(filepath: str = "src/model_validation/test_dataset.json") -> List[Dict]:
        """Load test dataset from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data['test_cases']


if __name__ == "__main__":
    # Generate and save test dataset
    dataset = TestDataset()
    dataset.save_to_file()
    
    print(f"\n📊 Generated {len(dataset.test_cases)} test cases")
    print("\nSample test case:")
    if dataset.test_cases:
        print(json.dumps(dataset.test_cases[0], indent=2))