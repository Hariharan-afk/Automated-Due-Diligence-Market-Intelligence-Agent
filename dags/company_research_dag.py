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
from db_manager import init_db, insert_company, insert_article
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
    """Task 2: Acquire data from Wikipedia and News APIs"""
    logger.info("📥 Starting data acquisition...")
    
    company_input = Variable.get("target_company", default_var="Apple")
    news_api_key = Variable.get("news_api_key", default_var="d95b2db0967748a69be7b951bed9e4bc")
    
    pipeline = DataAcquisitionPipeline(
        news_api_key=news_api_key,
        ticker_file="data/company_tickers.json"
    )
    
    try:
        result = pipeline.fetch_company_data(company_input)
        
        context['task_instance'].xcom_push(key='raw_data', value=json.dumps(result))
        context['task_instance'].xcom_push(key='company_name', value=result['company_name'])
        
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
        
        conn.close()
        
        logger.info(f"✅ Stored {len(processed_data['news_articles'])} articles for {processed_data['company_name']}")
        
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
    
    statistics = {
        "company": processed_data['company_name'],
        "ticker": processed_data['ticker'],
        "pipeline_run": datetime.now().isoformat(),
        "data_sources": {
            "wikipedia": "success" if "error" not in processed_data['wikipedia'] else "failed",
            "news_articles": len(processed_data['news_articles'])
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
            "date_range": processed_data['statistics'].get('date_range', {})
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