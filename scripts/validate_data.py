#!/usr/bin/env python
"""
Data Validation CLI Script

Command-line interface for validating fetched company data.

Usage:
    python scripts/validate_data.py --input data/AAPL_2024_all_data_*.json
    python scripts/validate_data.py --input data/AAPL_2024_all_data_*.json --output validation_report.json
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation import DataValidator
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Validate fetched company data'
    )
    parser.add_argument('--input', type=str, required=True,
                       help='Path to company data JSON file')
    parser.add_argument('--output', type=str, default=None,
                       help='Optional: Path to save validation report')
    parser.add_argument('--tables-dir', type=str, default='data/tables',
                       help='Directory containing table files (default: data/tables)')
    
    args = parser.parse_args()
    
    # Load data
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1
    
    logger.info(f"Loading data from: {input_path}")
    with open(input_path) as f:
        data = json.load(f)
    
    # Run validation
    validator = DataValidator()
    tables_dir = Path(args.tables_dir) if args.tables_dir else None
    
    results = validator.run_all_validations(data, tables_dir)
    
    # Print summary
    logger.info("\n" + "="*70)
    logger.info("VALIDATION SUMMARY")
    logger.info("="*70)
    logger.info(f"Overall Valid: {'✅ PASS' if results['overall_valid'] else '❌ FAIL'}")
    logger.info(f"Total Chunks: {results['stats']['total_chunks']}")
    
    if results['critical_issues']:
        logger.info(f"\n❌ Critical Issues ({len(results['critical_issues'])}):")
        for issue in results['critical_issues'][:10]:
            logger.info(f"  - {issue}")
    
    if results['warnings']:
        logger.info(f"\n⚠️  Warnings ({len(results['warnings'])}):")
        for warning in results['warnings'][:10]:
            logger.info(f"  - {warning}")
    
    # Print check results
    logger.info("\n" + "="*70)
    logger.info("CHECK RESULTS")
    logger.info("="*70)
    
    for check_name, check_result in results['checks'].items():
        status = "✅ PASS" if check_result.get('valid', True) else "❌ FAIL"
        logger.info(f"{check_name.upper()}: {status}")
        
        # Print stats if available
        if 'stats' in check_result:
            logger.info(f"  Stats: {check_result['stats']}")
    
    # Save report if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"\n📄 Validation report saved to: {output_path}")
    
    logger.info("\n" + "="*70)
    logger.info("VALIDATION COMPLETE")
    logger.info("="*70)
    
    return 0 if results['overall_valid'] else 1


if __name__ == "__main__":
    exit(main())
