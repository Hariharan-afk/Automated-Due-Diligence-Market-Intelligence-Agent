#!/usr/bin/env python
"""
Bias Analysis and Configuration Script

Analyzes data coverage across companies, calculates baselines,
and generates boost configurations for fair retrieval.

Usage:
    python scripts/configure_bias_mitigation.py --data-dir data --output-dir bias_config
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bias import CoverageTracker, BaselineCalculator, BoostConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


def load_company_data(data_file: Path) -> Dict:
    """Load company data from JSON file"""
    with open(data_file, 'r') as f:
        return json.load(f)


def process_all_companies(data_dir: Path, coverage_tracker: CoverageTracker):
    """
    Process all company data files and track coverage
    
    Args:
        data_dir: Directory containing company JSON files
        coverage_tracker: CoverageTracker instance
    """
    data_files = list(data_dir.glob("*_all_data_*.json"))
    
    logger.info(f"Found {len(data_files)} company data files")
    
    for data_file in data_files:
        try:
            logger.info(f"Processing {data_file.name}")
            data = load_company_data(data_file)
            
            ticker = data.get('ticker')
            year = data.get('year')
            
            if not ticker:
                logger.warning(f"No ticker found in {data_file.name}, skipping")
                continue
            
            # Combine all chunks
            all_chunks = []
            all_chunks.extend(data.get('sec', {}).get('chunks', []))
            all_chunks.extend(data.get('wikipedia', {}).get('chunks', []))
            all_chunks.extend(data.get('news', {}).get('chunks', []))
            
            # Get company name
            company_name = data.get('sec', {}).get('filing_metadata', {}).get('company', ticker)
            
            # Track tables
            num_tables = data.get('sec', {}).get('num_tables', 0)
            
            # Track coverage
            coverage_tracker.track_company(
                ticker=ticker,
                company_name=company_name,
                chunks=all_chunks,
                num_tables=num_tables,
                metadata={'year': year, 'file': data_file.name}
            )
            
        except Exception as e:
            logger.error(f"Failed to process {data_file.name}: {e}")
            continue
    
    logger.info(f"Completed processing {len(data_files)} companies")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze data coverage and configure bias mitigation'
    )
    parser.add_argument('--data-dir', type=str, default='data',
                       help='Directory containing company data files (default: data)')
    parser.add_argument('--output-dir', type=str, default='bias_config',
                       help='Output directory for bias configuration (default: bias_config)')
    parser.add_argument('--boost-strategy', type=str, default='percentile',
                       choices=['percentile', 'ratio'],
                       help='Classification strategy (default: percentile)')
    
    args = parser.parse_args()
    
    # Setup paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / args.data_dir
    output_dir = base_dir / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("="*70)
    logger.info("BIAS MITIGATION CONFIGURATION")
    logger.info("="*70)
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    # Step 1: Track coverage for all companies
    logger.info("\n" + "="*70)
    logger.info("STEP 1: Tracking Coverage Metrics")
    logger.info("="*70)
    
    coverage_path = output_dir / "coverage_metrics.json"
    tracker = CoverageTracker(coverage_path)
    
    process_all_companies(data_dir, tracker)
    
    # Export coverage report
    report_path = output_dir / "coverage_report.json"
    tracker.export_report(report_path)
    
    logger.info(f"\nCoverage metrics saved to: {coverage_path}")
    logger.info(f"Coverage report saved to: {report_path}")
    
    # Print summary stats
    stats = tracker.get_summary_stats()
    logger.info("\nCoverage Summary:")
    logger.info(f"  Total companies: {stats['total_companies']}")
    logger.info(f"  Avg chunks: {stats['avg_total_chunks']:.1f}")
    logger.info(f"  Range: {stats['min_chunks']} - {stats['max_chunks']}")
    logger.info(f"  Avg completeness: {stats['avg_completeness']:.2f}")
    
    # Step 2: Calculate baselines and classify companies
    logger.info("\n" + "="*70)
    logger.info("STEP 2: Calculating Baselines and Classifications")
    logger.info("="*70)
    
    calculator = BaselineCalculator(tracker.get_all_metrics())
    
    # Save baseline config
    baseline_path = output_dir / "baseline_config.json"
    calculator.save_baseline_config(baseline_path)
    logger.info(f"\nBaseline config saved to: {baseline_path}")
    
    # Generate classification report
    class_report = calculator.generate_report()
    
    # Convert numpy types before saving
    class_report = convert_numpy_types(class_report)
    
    class_report_path = output_dir / "classification_report.json"
    with open(class_report_path, 'w') as f:
        json.dump(class_report, f, indent=2)
    
    logger.info(f"Classification report saved to: {class_report_path}")
    logger.info("\nClassification Counts:")
    for cls, count in class_report['classification_counts'].items():
        logger.info(f"  {cls.capitalize()}: {count}")
    
    # Step 3: Generate boost configurations
    logger.info("\n" + "="*70)
    logger.info("STEP 3: Generating Boost Configurations")
    logger.info("="*70)
    
    boost_config_path = output_dir / "boost_config.json"
    boost_manager = BoostConfigManager(boost_config_path)
    
    for ticker, metrics in tracker.get_all_metrics().items():
        # Classify company
        classification, coverage_ratio = calculator.classify_company(
            metrics, method=args.boost_strategy
        )
        
        # Get base boost
        base_boost = calculator.get_boost_factor(
            classification,
            quality_adjusted=True,
            quality_score=metrics['completeness_score']
        )
        
        # Get source-specific boosts
        source_boosts = {}
        for source in ['sec', 'wikipedia', 'news']:
            source_boosts[source] = calculator.get_boost_factor(
                classification,
                source=source,
                quality_adjusted=True,
                quality_score=metrics['completeness_score']
            )
        
        # Set boost configuration
        boost_manager.set_company_boost(
            ticker=ticker,
            classification=classification,
            coverage_ratio=coverage_ratio,
            base_boost=base_boost,
            source_boosts=source_boosts,
            metadata={
                'completeness': metrics['completeness_score'],
                'total_chunks': metrics['total_chunks']
            }
        )
    
    logger.info(f"\nBoost config saved to: {boost_config_path}")
    
    # Export boost summary
    boost_summary_path = output_dir / "boost_summary.json"
    boost_manager.export_summary(boost_summary_path)
    logger.info(f"Boost summary saved to: {boost_summary_path}")
    
    # Final summary
    logger.info("\n" + "="*70)
    logger.info("CONFIGURATION COMPLETE!")
    logger.info("="*70)
    logger.info("\nGenerated Files:")
    logger.info(f"  1. {coverage_path}")
    logger.info(f"  2. {report_path}")
    logger.info(f"  3. {baseline_path}")
    logger.info(f"  4. {class_report_path}")
    logger.info(f"  5. {boost_config_path}")
    logger.info(f"  6. {boost_summary_path}")
    logger.info("\nNext Steps:")
    logger.info("  - Use RetrievalEnhancer in your RAG pipeline")
    logger.info("  - Pass boost_config.json path to RetrievalEnhancer")
    logger.info("  - Call enhance_scores() on retrieval results")


if __name__ == "__main__":
    main()
