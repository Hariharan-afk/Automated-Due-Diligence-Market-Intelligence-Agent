"""
Command-line interface for running the data pipeline - FINAL VERSION
"""

import argparse
import sys
import os
import json
import logging
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_acquisition import DataAcquisitionPipeline
from data_preprocessing import DataPreprocessingPipeline
from schema_validator import DataQualityReport
from bias_detector import BiasDetector
from db_manager import init_db, insert_company, insert_article, insert_sec_filing
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrate pipeline execution"""
    
    def __init__(self, config_file: str = "config/config.yaml"):
        self.config = self._load_config(config_file)
        self.news_api_key = os.getenv("NEWS_API_KEY", "d95b2db0967748a69be7b951bed9e4bc")
        self.sec_api_key = os.getenv("SEC_API_KEY", "")
        self.fetch_sec = os.getenv("FETCH_SEC_FILINGS", "true").lower() == "true"
        self.db_path = "data/company_data.db"
    
    def _load_config(self, config_file: str) -> dict:
        """Load configuration from YAML file"""
        try:
            import yaml
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except:
            logger.warning(f"Could not load config file: {config_file}, using defaults")
            return {}
    
    def run_full_pipeline(self, company: str):
        """Run complete pipeline for a company"""
        logger.info(f"{'='*60}")
        logger.info(f"Starting full pipeline for: {company}")
        logger.info(f"{'='*60}")
        
        try:
            # Stage 1: Data Acquisition
            logger.info("\n🔄 Stage 1: Data Acquisition")
            raw_data = self.run_acquisition(company)
            
            # Stage 2: Data Preprocessing
            logger.info("\n🔄 Stage 2: Data Preprocessing")
            processed_data = self.run_preprocessing(raw_data)
            
            # Stage 3: Schema Validation
            logger.info("\n🔄 Stage 3: Schema Validation & Quality Check")
            quality_report = self.run_validation(processed_data)
            
            # Stage 4: Bias Detection
            logger.info("\n🔄 Stage 4: Bias Detection")
            bias_report = self.run_bias_detection(processed_data)
            
            # Stage 5: Database Storage
            logger.info("\n🔄 Stage 5: Database Storage")
            self.run_storage(processed_data)
            
            # Generate summary
            self._print_summary(processed_data, quality_report, bias_report)
            
            logger.info(f"\n✅ Pipeline completed successfully for: {company}")
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_acquisition(self, company: str) -> dict:
        """Run data acquisition stage"""
        pipeline = DataAcquisitionPipeline(
            news_api_key=self.news_api_key,
            ticker_file="data/company_tickers.json",
            sec_api_key=self.sec_api_key if self.sec_api_key else None
        )

        result = pipeline.fetch_company_data(company, fetch_sec=self.fetch_sec)

        # Log results
        logger.info(f"  📰 News articles fetched: {result['metadata']['news_count']}")
        if self.fetch_sec and 'sec_filings' in result:
            sec_count = len([f for f in result['sec_filings'].values() if f and 'error' not in f])
            logger.info(f"  📄 SEC filings fetched: {sec_count}")

        logger.info(f"✅ Acquisition complete")
        return result
    
    def run_preprocessing(self, raw_data: dict) -> dict:
        """Run preprocessing stage"""
        pipeline = DataPreprocessingPipeline()
        result = pipeline.process_company_data(raw_data)
        logger.info(f"✅ Preprocessing complete: {result['statistics']['total_news_articles']} articles processed")
        return result
    
    def run_validation(self, processed_data: dict) -> dict:
        """Run validation stage"""
        reporter = DataQualityReport()
        report = reporter.generate_report(processed_data)
        
        quality_score = report['overall_quality_score']
        logger.info(f"✅ Validation complete: Quality Score = {quality_score:.1f}/100")
        
        if not report['schema_validation']['valid']:
            logger.error("❌ Schema validation failed!")
            for error in report['schema_validation']['errors']:
                logger.error(f"  - {error}")
        
        return report
    
    def run_bias_detection(self, processed_data: dict) -> dict:
        """Run bias detection stage"""
        detector = BiasDetector()
        report = detector.analyze_data(processed_data)
        
        if report['bias_detected']:
            logger.warning(f"⚠️ Bias detected: {len(report['bias_findings'])} issues found")
        else:
            logger.info("✅ No significant bias detected")
        
        return report
    
    def run_storage(self, processed_data: dict):
        """Run database storage stage"""
        # Initialize database
        init_db(self.db_path)
        conn = sqlite3.connect(self.db_path)

        try:
            # Insert company
            company_id = insert_company(
                conn,
                name=processed_data['company_name'],
                ticker=processed_data['ticker'],
                summary=processed_data['wikipedia']['summary'][:1000],
                url=processed_data['wikipedia']['url'],
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # Insert articles
            for article in processed_data['news_articles']:
                insert_article(
                    conn,
                    company_id=company_id,
                    title=article['title'],
                    url=article['url'],
                    source=article['source'],
                    date=article['published_date'],
                    summary=article.get('description', '')[:500]
                )

            # Insert SEC filings
            sec_filings = processed_data.get('sec_filings', {})
            sec_count = 0
            for filing_type, filing_data in sec_filings.items():
                if filing_data and 'error' not in filing_data:
                    insert_sec_filing(
                        conn,
                        company_id=company_id,
                        ticker=filing_data['ticker'],
                        cik=filing_data['cik'],
                        filing_type=filing_data['filing_type'],
                        filing_date=filing_data['filing_date'],
                        fiscal_year=filing_data.get('fiscal_year', 0),
                        fiscal_period=filing_data.get('fiscal_period', ''),
                        accession_number=filing_data['accession_number'],
                        filing_url=filing_data.get('filing_url', ''),
                        sections=json.dumps(filing_data['sections'])
                    )
                    sec_count += 1

            conn.commit()
            logger.info(f"✅ Storage complete: {len(processed_data['news_articles'])} articles, {sec_count} SEC filings stored")

        finally:
            conn.close()
    
    def _print_summary(self, processed_data: dict, quality_report: dict, bias_report: dict):
        """Print pipeline summary"""
        print("\n" + "="*60)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*60)
        print(f"\nCompany: {processed_data['company_name']}")
        print(f"Ticker: {processed_data['ticker']}")
        print(f"\n📊 Data Collection:")
        print(f"  • Wikipedia: {'✓' if 'error' not in processed_data['wikipedia'] else '✗'}")
        print(f"  • News Articles: {processed_data['statistics']['total_news_articles']}")
        print(f"  • News Sources: {len(processed_data['statistics']['news_sources'])}")

        # SEC filings summary
        sec_stats = processed_data.get('statistics', {}).get('sec_filings', {})
        if sec_stats.get('filings_available'):
            print(f"  • SEC Filings: {', '.join(sec_stats['filings_available'])}")
            print(f"    - Total Sections: {sec_stats.get('total_sections', 0)}")
            print(f"    - Total Words: {sec_stats.get('total_words', 0):,}")
            print(f"    - Total Tables: {sec_stats.get('total_tables', 0)}")
            print(f"    - Fiscal Years: {sec_stats.get('fiscal_years', [])}")

        print(f"\n📈 Quality Metrics:")
        print(f"  • Quality Score: {quality_report['overall_quality_score']:.1f}/100")
        print(f"  • Validation Errors: {len(quality_report['schema_validation']['errors'])}")
        print(f"  • Anomalies: {quality_report['anomaly_detection']['anomaly_count']}")
        print(f"\n⚖️ Bias Analysis:")
        print(f"  • Bias Detected: {'Yes' if bias_report['bias_detected'] else 'No'}")
        print(f"  • Fairness Score: {bias_report['fairness_metrics']['overall_fairness_score']:.1f}/100")
        print(f"  • Issues Found: {len(bias_report['bias_findings'])}")

        if bias_report['bias_findings']:
            print(f"\n  Issues:")
            for finding in bias_report['bias_findings']:
                print(f"    - [{finding['severity'].upper()}] {finding['description']}")

        print(f"\n💾 Output Files:")
        print(f"  • Database: {self.db_path}")
        print(f"  • Processed Data: data/processed/")
        print(f"  • Quality Report: data/quality_reports/")
        print(f"  • Bias Report: data/bias_reports/")
        print("="*60 + "\n")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Company Research Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline for a company
  python run_pipeline.py --company "Apple Inc"
  
  # Run specific stage
  python run_pipeline.py --stage acquisition --company "Microsoft"
  
  # Run with custom config
  python run_pipeline.py --company "Tesla" --config custom_config.yaml
        """
    )
    
    parser.add_argument(
        '--company',
        type=str,
        help='Company name or ticker symbol'
    )
    
    parser.add_argument(
        '--stage',
        type=str,
        choices=['acquisition', 'preprocessing', 'validation', 'bias', 'storage', 'full'],
        default='full',
        help='Pipeline stage to run'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        help='Input file for specific stages'
    )
    
    args = parser.parse_args()
    
    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("data/quality_reports", exist_ok=True)
    os.makedirs("data/bias_reports", exist_ok=True)
    
    # Initialize runner
    runner = PipelineRunner(args.config)
    
    # Get company input
    if not args.company and args.stage == 'full':
        args.company = input("Enter company name or ticker: ")
    
    # Run pipeline
    if args.stage == 'full':
        if not args.company:
            print("Error: --company required for full pipeline")
            sys.exit(1)
        success = runner.run_full_pipeline(args.company)
    
    elif args.stage == 'acquisition':
        if not args.company:
            print("Error: --company required for acquisition")
            sys.exit(1)
        runner.run_acquisition(args.company)
        success = True
    
    elif args.stage == 'preprocessing':
        if not args.input:
            print("Error: --input required for preprocessing stage")
            sys.exit(1)
        with open(args.input, 'r') as f:
            raw_data = json.load(f)
        runner.run_preprocessing(raw_data)
        success = True
    
    elif args.stage == 'validation':
        if not args.input:
            print("Error: --input required for validation stage")
            sys.exit(1)
        with open(args.input, 'r') as f:
            processed_data = json.load(f)
        runner.run_validation(processed_data)
        success = True
    
    elif args.stage == 'bias':
        if not args.input:
            print("Error: --input required for bias detection stage")
            sys.exit(1)
        with open(args.input, 'r') as f:
            processed_data = json.load(f)
        runner.run_bias_detection(processed_data)
        success = True
    
    elif args.stage == 'storage':
        if not args.input:
            print("Error: --input required for storage stage")
            sys.exit(1)
        with open(args.input, 'r') as f:
            processed_data = json.load(f)
        runner.run_storage(processed_data)
        success = True
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()