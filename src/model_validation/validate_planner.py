"""
model_validation/validate_planner.py
Validates PlannerAgent output structure and format.
"""

import sys
sys.path.append('.')

import json
from src.agents.planner_agent import PlannerAgent

def validate_planner(test_file: str = "src/model_validation/golden_dataset.json"):
    print("\n" + "="*70)
    print("🧠 VALIDATING PLANNER AGENT (STRUCTURE TEST)")
    print("="*70)
    
    # Load test data
    try:
        with open(test_file, 'r') as f:
            data = json.load(f)
        test_cases = data['test_cases']
    except FileNotFoundError:
        print(f"❌ Test file {test_file} not found. Run generate_synthetic_test.py first.")
        return
        
    # Initialize Agent
    print("⚙️ Initializing Planner Agent...")
    planner = PlannerAgent()
    
    passed = 0
    total = len(test_cases)
    
    print(f"\n🚀 Running {total} test cases...")
    
    for i, case in enumerate(test_cases, 1):
        query = case['query']
        print(f"\nTest {i}/{total}: '{query}'")
        
        try:
            # Execute Planner
            sub_queries = planner.execute(query)
            
            # Validation Checks
            is_list = isinstance(sub_queries, list)
            is_strings = all(isinstance(sq, str) for sq in sub_queries) if is_list else False
            count = len(sub_queries) if is_list else 0
            
            if is_list and is_strings and 1 <= count <= 10:
                print(f"  ✅ PASS. Generated {count} valid sub-queries.")
                passed += 1
            else:
                print(f"  ❌ FAIL. Invalid format. List={is_list}, Strings={is_strings}, Count={count}")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            
    success_rate = passed / total if total > 0 else 0
    print("\n" + "-"*70)
    print(f"📊 RESULTS: Success Rate = {success_rate:.2%} ({passed}/{total})")
    print("-"*70)
    
    if success_rate < 0.8:
        print("❌ Validation FAILED (Success Rate < 80%)")
        sys.exit(1)
    else:
        print("✅ Validation PASSED")
        sys.exit(0)

if __name__ == "__main__":
    validate_planner()
