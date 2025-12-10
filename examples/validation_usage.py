"""
Example: Using DataValidator in Other Scripts

This shows how to use the validation module in your own code.
"""

from pathlib import Path
import json
from src.validation import DataValidator

# Example 1: Validate in fetch script
def fetch_and_validate():
    """Fetch data and validate immediately"""
    
    # ... your fetch logic ...
    data = {
        'ticker': 'AAPL',
        'year': 2024,
        'sec': {'chunks': [...]},
        'wikipedia': {'chunks': [...]},
        'news': {'chunks': [...]}
    }
    
    # Validate
    validator = DataValidator()
    results = validator.run_all_validations(data)
    
    if not results['overall_valid']:
        print(f"❌ Validation failed!")
        for issue in results['critical_issues']:
            print(f"  - {issue}")
        return None
    
    print(f"✅ Validation passed!")
    return data


# Example 2: Validate specific aspects only
def check_token_sizes(chunks):
    """Just check token sizes"""
    validator = DataValidator()
    result = validator.validate_token_sizes(chunks)
    
    if not result['valid']:
        print(f"Found {result['oversized_chunks']} oversized chunks")
    
    return result


# Example 3: Batch validation
def validate_all_files(data_dir):
    """Validate all company data files"""
    
    validator = DataValidator()
    results = {}
    
    for data_file in Path(data_dir).glob("*_all_data_*.json"):
        print(f"Validating {data_file.name}...")
        
        with open(data_file) as f:
            data = json.load(f)
        
        validation_result = validator.run_all_validations(data)
        results[data_file.stem] = validation_result
    
    # Summary
    passed = sum(1 for r in results.values() if r['overall_valid'])
    print(f"\n✅ {passed}/{len(results)} files passed validation")
    
    return results


# Example 4: Custom validation threshold
def validate_with_custom_thresholds(data):
    """Validate with custom quality thresholds"""
    
    validator = DataValidator()
    results = validator.run_all_validations(data)
    
    # Custom checks
    completeness = results['checks']['completeness']['completeness_score']
    oversized = results['checks']['token_sizes']['oversized_chunks']
    
    # Your thresholds
    if completeness < 0.8:
        print("❌ Completeness too low")
        return False
    
    if oversized > 5:
        print("❌ Too many oversized chunks")
        return False
    
    print("✅ Meets custom thresholds")
    return True


if __name__ == "__main__":
    # Example usage
    data_dir = Path("data")
    validate_all_files(data_dir)
