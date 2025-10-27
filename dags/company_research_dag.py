"""
Airflow DAG for Company Research Data Pipeline - FINAL FIXED VERSION
Handles numpy serialization for XCom
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable
from datetime import datetime, timedelta
import json
import logging
import sys
import os
import numpy as np
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_acquisition import DataAcquisitionPipeline
from data_preprocessing import DataPreprocessingPipeline
from schema_validator import DataQualityReport
from bias_detector import BiasDetector
from db_manager import init_db, insert_company, insert_article, insert_sec_filing
import sqlite3

logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email': ['alerts@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'company_research_pipeline',
    default_args=default_args,
    description='End-to-end company research data pipeline',
    schedule_interval='@daily',
    start_date=days_ago(1),
    catchup=False,
    tags=['research', 'data-pipeline', 'mlops'],
)


def convert_to_json_serializable(obj):
    """Convert numpy/pandas types to Python native types for JSON serialization"""
    if isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj


def initialize_database(**context):
    """Task 1: Initialize database"""
    logger.info("🔧 Initializing database...")
    
    db_path = "data/company_data.db"
    init_db(db_path)
    
    context['task_instance'].xcom_push(key='db_path', value=db_path)
    logger.info("✅ Database initialized")


def acquire_company_data(**context):
    """Task 2: Acquire data from Wikipedia, News APIs, and SEC filings"""
    logger.info("📥 Starting data acquisition...")

    company_input = Variable.get("target_company", default_var="Apple")
    news_api_key = Variable.get("news_api_key", default_var="d95b2db0967748a69be7b951bed9e4bc")
    sec_api_key = Variable.get("sec_api_key", default_var=os.getenv("SEC_API_KEY", ""))
    fetch_sec = Variable.get("fetch_sec_filings", default_var="true").lower() == "true"

    pipeline = DataAcquisitionPipeline(
        news_api_key=news_api_key,
        ticker_file="data/company_tickers.json",
        sec_api_key=sec_api_key if sec_api_key else None
    )

    try:
        result = pipeline.fetch_company_data(company_input, fetch_sec=fetch_sec)

        context['task_instance'].xcom_push(key='raw_data', value=json.dumps(result))
        context['task_instance'].xcom_push(key='company_name', value=result['company_name'])

        # Log SEC status
        if fetch_sec and 'sec_filings' in result:
            sec_count = len([f for f in result['sec_filings'].values() if f and 'error' not in f])
            logger.info(f"  📄 Fetched {sec_count} SEC filings")

        logger.info(f"✅ Data acquired for: {result['company_name']}")

    except Exception as e:
        logger.error(f"❌ Data acquisition failed: {e}")
        raise


def preprocess_data(**context):
    """Task 3: Clean and preprocess acquired data"""
    logger.info("🔄 Starting data preprocessing...")
    
    ti = context['task_instance']
    raw_data_json = ti.xcom_pull(task_ids='acquire_company_data', key='raw_data')
    raw_data = json.loads(raw_data_json)
    
    pipeline = DataPreprocessingPipeline()
    
    try:
        processed_data = pipeline.process_company_data(raw_data)
        
        ti.xcom_push(key='processed_data', value=json.dumps(processed_data))
        
        logger.info(f"✅ Data preprocessed for: {processed_data['company_name']}")
        
    except Exception as e:
        logger.error(f"❌ Preprocessing failed: {e}")
        raise


def validate_schema(**context):
    """Task 4: Validate data schema"""
    logger.info("🔍 Validating data schema...")
    
    ti = context['task_instance']
    processed_data_json = ti.xcom_pull(task_ids='preprocess_data', key='processed_data')
    processed_data = json.loads(processed_data_json)
    
    reporter = DataQualityReport()
    quality_report = reporter.generate_report(processed_data)
    
    # Convert and push to XCom
    serializable_report = convert_to_json_serializable(quality_report)
    ti.xcom_push(key='quality_report', value=json.dumps(serializable_report))
    
    if not quality_report['schema_validation']['valid']:
        logger.error("❌ Schema validation failed!")
        raise ValueError(f"Schema validation errors: {quality_report['schema_validation']['errors']}")
    
    quality_score = quality_report['overall_quality_score']
    logger.info(f"📊 Quality Score: {quality_score}/100")
    
    if quality_score < 50:
        logger.warning(f"⚠️ Low quality score: {quality_score}/100")
        ti.xcom_push(key='send_alert', value=True)
    
    logger.info("✅ Schema validation passed")


def detect_anomalies(**context):
    """Task 5: Detect data anomalies"""
    logger.info("🔍 Detecting anomalies...")
    
    ti = context['task_instance']
    quality_report_json = ti.xcom_pull(task_ids='validate_schema', key='quality_report')
    quality_report = json.loads(quality_report_json)
    
    anomalies = quality_report['anomaly_detection']
    
    if anomalies['has_anomalies']:
        logger.warning(f"⚠️ Found {anomalies['anomaly_count']} anomalies")
        
        for anomaly in anomalies['anomalies']:
            if anomaly['severity'] == 'error':
                logger.error(f"CRITICAL: {anomaly['message']}")
            elif anomaly['severity'] == 'warning':
                logger.warning(f"WARNING: {anomaly['message']}")
        
        if anomalies['severity_breakdown']['error'] > 0:
            ti.xcom_push(key='send_alert', value=True)
    else:
        logger.info("✅ No anomalies detected")


def detect_bias(**context):
    """Task 6: Detect bias in data"""
    logger.info("⚖️ Detecting bias...")
    
    ti = context['task_instance']
    processed_data_json = ti.xcom_pull(task_ids='preprocess_data', key='processed_data')
    processed_data = json.loads(processed_data_json)
    
    detector = BiasDetector()
    bias_report = detector.analyze_data(processed_data)
    
    # Convert to JSON-serializable before pushing to XCom
    serializable_report = convert_to_json_serializable(bias_report)
    ti.xcom_push(key='bias_report', value=json.dumps(serializable_report))
    
    if bias_report['bias_detected']:
        logger.warning(f"⚠️ Bias detected: {len(bias_report['bias_findings'])} issues")
        for finding in bias_report['bias_findings']:
            logger.warning(f"  - [{finding['severity']}] {finding['description']}")
    else:
        logger.info("✅ No significant bias detected")


def store_to_database(**context):
    """Task 7: Store validated data to database"""
    logger.info("💾 Storing data to database...")

    ti = context['task_instance']

    processed_data_json = ti.xcom_pull(task_ids='preprocess_data', key='processed_data')
    processed_data = json.loads(processed_data_json)

    db_path = ti.xcom_pull(task_ids='initialize_database', key='db_path')

    try:
        conn = sqlite3.connect(db_path)

        company_id = insert_company(
            conn,
            name=processed_data['company_name'],
            ticker=processed_data['ticker'],
            summary=processed_data['wikipedia']['summary'][:1000],
            url=processed_data['wikipedia']['url'],
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Store news articles
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

        logger.info(f"  📰 Stored {len(processed_data['news_articles'])} articles")

        # Store SEC filings
        sec_filings = processed_data.get('sec_filings', {})
        sec_count = 0
        for filing_type, filing_data in sec_filings.items():
            if filing_data and 'error' not in filing_data:
                insert_sec_filing(
                    conn,
                    company_id=company_id,
                    ticker=filing_data.get('ticker', processed_data['ticker']),
                    cik=filing_data.get('cik', ''),
                    filing_type=filing_data.get('filing_type', filing_type),
                    filing_date=filing_data.get('filing_date', ''),
                    fiscal_year=filing_data.get('fiscal_year', 0),
                    fiscal_period=filing_data.get('fiscal_period', ''),
                    accession_number=filing_data.get('accession_number', ''),
                    filing_url=filing_data.get('filing_url', ''),
                    sections=json.dumps(filing_data.get('sections', {})),
                    extraction_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                sec_count += 1

        if sec_count > 0:
            logger.info(f"  📄 Stored {sec_count} SEC filings")

        conn.close()

        logger.info(f"✅ Stored all data for {processed_data['company_name']}")

    except Exception as e:
        logger.error(f"❌ Database storage failed: {e}")
        raise


def generate_statistics(**context):
    """Task 8: Generate data statistics and summary"""
    logger.info("📊 Generating statistics...")
    
    ti = context['task_instance']
    processed_data_json = ti.xcom_pull(task_ids='preprocess_data', key='processed_data')
    quality_report_json = ti.xcom_pull(task_ids='validate_schema', key='quality_report')
    bias_report_json = ti.xcom_pull(task_ids='detect_bias', key='bias_report')
    
    processed_data = json.loads(processed_data_json)
    quality_report = json.loads(quality_report_json)
    bias_report = json.loads(bias_report_json)
    
    # Get SEC statistics
    sec_stats = processed_data.get('statistics', {}).get('sec_filings', {})

    statistics = {
        "company": processed_data['company_name'],
        "ticker": processed_data['ticker'],
        "pipeline_run": datetime.now().isoformat(),
        "data_sources": {
            "wikipedia": "success" if "error" not in processed_data['wikipedia'] else "failed",
            "news_articles": len(processed_data['news_articles']),
            "sec_filings": {
                "total": len([f for f in processed_data.get('sec_filings', {}).values() if f and 'error' not in f]),
                "types": sec_stats.get('filings_available', []),
                "fiscal_years": sec_stats.get('fiscal_years', [])
            }
        },
        "quality": {
            "score": quality_report['overall_quality_score'],
            "anomalies": quality_report['anomaly_detection']['anomaly_count'],
            "validation_errors": len(quality_report['schema_validation']['errors'])
        },
        "bias": {
            "fairness_score": bias_report['fairness_metrics']['overall_fairness_score'],
            "bias_detected": bias_report['bias_detected'],
            "findings_count": len(bias_report['bias_findings'])
        },
        "content_metrics": {
            "wikipedia_word_count": processed_data['wikipedia'].get('word_count', 0),
            "news_sources": processed_data['statistics'].get('news_sources', []),
            "date_range": processed_data['statistics'].get('date_range', {}),
            "sec_metrics": {
                "total_sections": sec_stats.get('total_sections', 0),
                "total_words": sec_stats.get('total_words', 0),
                "total_tables": sec_stats.get('total_tables', 0)
            }
        }
    }
    
    os.makedirs("data/statistics", exist_ok=True)
    stats_file = f"data/statistics/{processed_data['company_name'].replace(' ', '_')}_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(statistics, f, indent=4)
    
    ti.xcom_push(key='statistics', value=json.dumps(statistics))
    
    logger.info(f"✅ Statistics generated: {stats_file}")


def check_and_alert(**context):
    """Task 9: Check if alerts needed and send"""
    ti = context['task_instance']
    
    send_alert = ti.xcom_pull(task_ids='detect_anomalies', key='send_alert')
    
    if send_alert:
        logger.warning("🚨 Alerts triggered - sending notification...")
        return "alert_required"
    else:
        logger.info("✅ No alerts needed")
        return "no_alert"


# Define tasks
task_init_db = PythonOperator(
    task_id='initialize_database',
    python_callable=initialize_database,
    dag=dag,
)

task_acquire = PythonOperator(
    task_id='acquire_company_data',
    python_callable=acquire_company_data,
    dag=dag,
)

task_preprocess = PythonOperator(
    task_id='preprocess_data',
    python_callable=preprocess_data,
    dag=dag,
)

task_validate = PythonOperator(
    task_id='validate_schema',
    python_callable=validate_schema,
    dag=dag,
)

task_anomaly = PythonOperator(
    task_id='detect_anomalies',
    python_callable=detect_anomalies,
    dag=dag,
)

task_bias = PythonOperator(
    task_id='detect_bias',
    python_callable=detect_bias,
    dag=dag,
)

task_store = PythonOperator(
    task_id='store_to_database',
    python_callable=store_to_database,
    dag=dag,
)

task_stats = PythonOperator(
    task_id='generate_statistics',
    python_callable=generate_statistics,
    dag=dag,
)

task_alert = PythonOperator(
    task_id='check_and_alert',
    python_callable=check_and_alert,
    dag=dag,
)

# Define task dependencies
task_init_db >> task_acquire >> task_preprocess >> task_validate
task_validate >> task_anomaly >> task_bias >> task_store
task_store >> task_stats >> task_alert