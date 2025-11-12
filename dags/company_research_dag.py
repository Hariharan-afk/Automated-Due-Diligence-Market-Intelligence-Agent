"""
Airflow DAG for Company Research Data Pipeline - FIXED VERSION
Proper XCom serialization handling with PathResolver
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
from decimal import Decimal
from pathlib import Path

# Add src to path using proper path resolution
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from data_acquisition import DataAcquisitionPipeline
from data_preprocessing import DataPreprocessingPipeline
from schema_validator import DataQualityReport
from bias_detector import BiasDetector
from db_manager import init_db, insert_company, insert_article, insert_sec_filing
from utils.path_resolver import PathResolver
from alert_manager import AlertManager
import sqlite3

logger = logging.getLogger(__name__)

# Initialize path resolver for the DAG
path_resolver = PathResolver()


def convert_to_json_serializable(obj):
    """
    Recursively convert numpy/pandas types to Python native types
    for JSON serialization in XCom
    """
    if isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict('records')
    elif isinstance(obj, pd.Series):
        return obj.to_list()
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif pd.isna(obj):
        return None
    else:
        return obj


def safe_xcom_push(ti, key: str, value: any):
    """Safely push data to XCom with serialization"""
    try:
        serialized_value = convert_to_json_serializable(value)
        ti.xcom_push(key=key, value=serialized_value)
        logger.info(f"Successfully pushed {key} to XCom")
    except Exception as e:
        logger.error(f"Failed to push {key} to XCom: {e}")
        raise


def safe_xcom_pull(ti, key: str, task_ids: str = None):
    """Safely pull data from XCom"""
    try:
        value = ti.xcom_pull(key=key, task_ids=task_ids)
        logger.info(f"Successfully pulled {key} from XCom")
        return value
    except Exception as e:
        logger.error(f"Failed to pull {key} from XCom: {e}")
        raise


# Default arguments
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email': ['alerts@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}

# DAG definition
dag = DAG(
    'Research_Data_Pipeline',
    default_args=default_args,
    description='End-to-end company research data pipeline with proper XCom handling',
    schedule_interval='@daily',
    start_date=days_ago(1),
    catchup=False,
    tags=['research', 'data-pipeline', 'mlops'],
    max_active_runs=1,
)


def initialize_database_task(**context):
    """Initialize the SQLite database"""
    try:
        logger.info("Initializing database...")

        # Use PathResolver for database path
        db_path = str(path_resolver.get_db_path())
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        init_db(db_path)
        logger.info(f"✅ Database initialized successfully at: {db_path}")
        return {"status": "success", "db_path": db_path}
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
        raise


def acquire_company_data_task(**context):
    """Fetch company data from multiple sources"""
    ti = context['ti']

    try:
        # Get company from Airflow Variables
        target_company = Variable.get("target_company", default_var="Apple Inc")
        logger.info(f"📥 Acquiring data for: {target_company}")

        # Get API keys from Airflow Variables or environment
        news_api_key = Variable.get("news_api_key", default_var=os.getenv("NEWS_API_KEY"))
        sec_api_key = Variable.get("sec_api_key", default_var=os.getenv("SEC_API_KEY"))

        if not news_api_key:
            raise ValueError("NEWS_API_KEY not found in Airflow Variables or environment")

        # Initialize pipeline with API keys
        pipeline = DataAcquisitionPipeline(
            news_api_key=news_api_key,
            sec_api_key=sec_api_key
        )

        # Fetch data
        result = pipeline.fetch_company_data(target_company)
        
        # Safe XCom push
        safe_xcom_push(ti, 'raw_data', result)
        safe_xcom_push(ti, 'company_name', result.get('company_name'))
        safe_xcom_push(ti, 'ticker', result.get('ticker'))
        
        # Log metrics
        news_count = result.get('metadata', {}).get('news_count', 0)
        sec_count = len(result.get('sec_filings', {}))
        logger.info(f"✅ Acquired {news_count} news articles and {sec_count} SEC filings")
        
        return {"status": "success", "news_count": news_count, "sec_count": sec_count}
        
    except Exception as e:
        logger.error(f"❌ Data acquisition failed: {e}", exc_info=True)
        raise


def preprocess_data_task(**context):
    """Preprocess the raw data"""
    ti = context['ti']
    
    try:
        # Pull raw data from XCom
        raw_data = safe_xcom_pull(ti, 'raw_data', task_ids='acquire_company_data')
        
        if not raw_data:
            raise ValueError("No raw data received from acquisition task")
        
        logger.info(f"🔄 Preprocessing data for: {raw_data.get('company_name')}")
        
        # Process data
        pipeline = DataPreprocessingPipeline()
        processed_data = pipeline.process_company_data(raw_data)
        
        # Safe XCom push
        safe_xcom_push(ti, 'processed_data', processed_data)
        
        # Log metrics
        article_count = processed_data.get('statistics', {}).get('total_news_articles', 0)
        logger.info(f"✅ Processed {article_count} articles")
        
        return {"status": "success", "article_count": article_count}
        
    except Exception as e:
        logger.error(f"❌ Preprocessing failed: {e}", exc_info=True)
        raise


def validate_schema_task(**context):
    """Validate data schema and quality"""
    ti = context['ti']
    
    try:
        # Pull processed data
        processed_data = safe_xcom_pull(ti, 'processed_data', task_ids='preprocess_data')
        
        logger.info("🔍 Validating data schema and quality...")
        
        # Generate quality report
        reporter = DataQualityReport()
        report = reporter.generate_report(processed_data)
        
        # Safe XCom push
        safe_xcom_push(ti, 'quality_report', report)
        safe_xcom_push(ti, 'quality_score', report.get('overall_quality_score'))
        
        quality_score = report.get('overall_quality_score', 0)
        logger.info(f"✅ Quality Score: {quality_score:.1f}/100")
        
        return {"status": "success", "quality_score": quality_score}
        
    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}", exc_info=True)
        raise


def detect_anomalies_task(**context):
    """Detect anomalies in the data"""
    ti = context['ti']
    
    try:
        # Pull processed data
        processed_data = safe_xcom_pull(ti, 'processed_data', task_ids='preprocess_data')
        
        logger.info("🔍 Detecting anomalies...")
        
        # Pull quality report for anomalies
        quality_report = safe_xcom_pull(ti, 'quality_report', task_ids='validate_schema')
        anomalies = quality_report.get('anomaly_detection', {}).get('anomalies', [])
        
        # Safe XCom push
        safe_xcom_push(ti, 'anomalies', anomalies)
        safe_xcom_push(ti, 'anomaly_count', len(anomalies))
        
        logger.info(f"✅ Found {len(anomalies)} anomalies")
        
        return {"status": "success", "anomaly_count": len(anomalies)}
        
    except Exception as e:
        logger.error(f"❌ Anomaly detection failed: {e}", exc_info=True)
        raise


def detect_bias_task(**context):
    """Detect bias in the data"""
    ti = context['ti']
    
    try:
        # Pull processed data
        processed_data = safe_xcom_pull(ti, 'processed_data', task_ids='preprocess_data')
        
        logger.info("⚖️ Detecting bias...")
        
        # Run bias detection
        detector = BiasDetector()
        bias_report = detector.analyze_data(processed_data)
        
        # Safe XCom push
        safe_xcom_push(ti, 'bias_report', bias_report)
        safe_xcom_push(ti, 'bias_detected', bias_report.get('bias_detected', False))
        
        fairness_score = bias_report.get('fairness_metrics', {}).get('overall_fairness_score', 0)
        logger.info(f"✅ Fairness Score: {fairness_score:.1f}/100")
        
        return {"status": "success", "fairness_score": fairness_score}
        
    except Exception as e:
        logger.error(f"❌ Bias detection failed: {e}", exc_info=True)
        raise

def mitigate_bias_task(**context):
    """Mitigate bias in the data and return cleaned data"""
    ti = context['ti']

    try:
        logger.info("🧩 Mitigating bias in processed data...")

        # Pull the bias report and processed data
        bias_report = safe_xcom_pull(ti, 'bias_report', task_ids='detect_bias')
        processed_data = safe_xcom_pull(ti, 'processed_data', task_ids='preprocess_data')

        if not bias_report or not processed_data:
            logger.warning("No bias report or data found – skipping mitigation.")
            safe_xcom_push(ti, 'mitigated_data', processed_data)  # Pass through original
            return {"status": "skipped"}

        # Apply mitigation if bias was detected
        if bias_report.get('bias_detected', False):
            logger.info("⚖️ Bias detected. Applying mitigation strategies...")
            
            # Get bias findings from the report
            bias_findings = bias_report.get('bias_findings', [])
            
            # Use the BiasDetector's mitigation method
            detector = BiasDetector()
            mitigated_data = detector.mitigate_bias(bias_findings, processed_data)
            
            # Get mitigation actions that were applied
            mitigation_actions = mitigated_data.get('mitigation_actions', [])
            mitigation_summary = '; '.join(mitigation_actions)
            
            logger.info(f"✅ Applied {len(mitigation_actions)} mitigation actions")
            
        else:
            logger.info("✅ No bias detected – no mitigation required.")
            mitigated_data = processed_data
            mitigation_summary = "No bias detected – no mitigation required."

        # Push mitigated data to XCom for storage task
        safe_xcom_push(ti, 'mitigated_data', mitigated_data)
        safe_xcom_push(ti, 'mitigation_summary', mitigation_summary)
        
        logger.info(f"✅ Bias mitigation complete: {mitigation_summary}")

        return {
            "status": "success", 
            "message": mitigation_summary,
            "actions_count": len(mitigated_data.get('mitigation_actions', []))
        }

    except Exception as e:
        logger.error(f"❌ Bias mitigation failed: {e}", exc_info=True)
        # If mitigation fails, pass through original data
        processed_data = safe_xcom_pull(ti, 'processed_data', task_ids='preprocess_data')
        safe_xcom_push(ti, 'mitigated_data', processed_data)
        raise

def store_to_database_task(**context):
    """Store processed data to database"""
    ti = context['ti']

    try:
        # Pull MITIGATED data instead of processed data
        processed_data = safe_xcom_pull(ti, 'mitigated_data', task_ids='mitigate_bias')
        
        # Fallback to original processed data if mitigation failed
        if not processed_data:
            logger.warning("Mitigated data not found, using original processed data")
            processed_data = safe_xcom_pull(ti, 'processed_data', task_ids='preprocess_data')

        logger.info("💾 Storing data to database...")

        # Rest of your storage code remains the same...
        db_path = str(path_resolver.get_db_path())

        with sqlite3.connect(db_path, timeout=30.0) as conn:
            # Insert company
            company_id = insert_company(
                conn,
                name=processed_data['company_name'],
                ticker=processed_data['ticker'],
                summary=processed_data.get('wikipedia', {}).get('summary', ''),
                url=processed_data.get('wikipedia', {}).get('url', ''),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # Insert articles (now potentially mitigated)
            article_count = 0
            for article in processed_data.get('news_articles', []):
                insert_article(
                    conn,
                    company_id=company_id,
                    title=article['title'],
                    url=article['url'],
                    source=article['source'],
                    date=article['published_date'],
                    summary=article.get('description', '')[:500]
                )
                article_count += 1

            # Insert SEC filings
            sec_count = 0
            for filing_type, filing_data in processed_data.get('sec_filings', {}).items():
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

            conn.commit()
        
        logger.info(f"✅ Stored {article_count} articles and {sec_count} SEC filings")
        
        return {"status": "success", "article_count": article_count, "sec_count": sec_count}
        
    except Exception as e:
        logger.error(f"❌ Database storage failed: {e}", exc_info=True)
        raise


def generate_statistics_task(**context):
    """Generate final statistics"""
    ti = context['ti']

    try:
        logger.info("📊 Generating statistics...")

        # Pull all metrics
        quality_score = safe_xcom_pull(ti, 'quality_score', task_ids='validate_schema')
        anomaly_count = safe_xcom_pull(ti, 'anomaly_count', task_ids='detect_anomalies')
        bias_report = safe_xcom_pull(ti, 'bias_report', task_ids='detect_bias')
        mitigation_summary = safe_xcom_pull(ti, 'mitigation_summary', task_ids='mitigate_bias')

        statistics = {
            "quality_score": quality_score,
            "anomaly_count": anomaly_count,
            "fairness_score": bias_report.get('fairness_metrics', {}).get('overall_fairness_score', 0),
            "bias_detected": bias_report.get('bias_detected', False),
            "mitigation_applied": mitigation_summary or "N/A",
            "timestamp": datetime.now().isoformat()
        }

        # Save statistics using PathResolver
        metrics_dir = path_resolver.get_data_path('metrics')
        metrics_dir.mkdir(parents=True, exist_ok=True)
        stats_file = metrics_dir / "pipeline_statistics.json"

        with open(stats_file, "w", encoding='utf-8') as f:
            json.dump(statistics, f, indent=2)
        
        logger.info("✅ Statistics generated")
        
        return statistics
        
    except Exception as e:
        logger.error(f"❌ Statistics generation failed: {e}", exc_info=True)
        raise


def check_and_alert_task(**context):
    """Check quality thresholds and send alerts if needed"""
    ti = context['ti']
    
    try:
        logger.info("🔔 Checking alert conditions...")
        
        # Pull metrics from previous tasks
        quality_score = safe_xcom_pull(ti, 'quality_score', task_ids='validate_schema')
        anomaly_count = safe_xcom_pull(ti, 'anomaly_count', task_ids='detect_anomalies')
        company_name = safe_xcom_pull(ti, 'company_name', task_ids='acquire_company_data')
        bias_report = safe_xcom_pull(ti, 'bias_report', task_ids='detect_bias')
        
        # Get article and SEC counts from raw data
        raw_data = safe_xcom_pull(ti, 'raw_data', task_ids='acquire_company_data')
        article_count = raw_data.get('metadata', {}).get('news_count', 0) if raw_data else 0
        sec_count = len(raw_data.get('sec_filings', {})) if raw_data else 0
        
        # Initialize alert manager
        alert_manager = AlertManager()
        
        # Check thresholds and collect alerts
        alerts = []
        
        if quality_score < 70:
            alerts.append(f"⚠️ Low quality score: {quality_score:.1f}/100 (threshold: 70)")
        
        if anomaly_count > 5:
            alerts.append(f"⚠️ High anomaly count: {anomaly_count} (threshold: 5)")
        
        # Check for bias
        bias_detected = False
        fairness_score = 0
        if bias_report:
            bias_detected = bias_report.get('bias_detected', False)
            fairness_score = bias_report.get('fairness_metrics', {}).get('overall_fairness_score', 0)
            
            if bias_detected and fairness_score < 70:
                alerts.append(f"⚠️ Bias detected - Fairness score: {fairness_score:.1f}/100")
        
        # Determine what to do based on alerts
        if alerts:
            logger.warning(f"⚠️ {len(alerts)} alert(s) triggered: {', '.join(alerts)}")
            
            # Prepare additional info for email
            additional_info = {
                'articles_processed': article_count,
                'sec_filings_processed': sec_count,
                'bias_detected': bias_detected,
                'fairness_score': f"{fairness_score:.1f}/100" if bias_detected else 'N/A'
            }
            
            # Send combined alert email
            email_sent = alert_manager.send_combined_alert(
                company_name=company_name or "Unknown Company",
                quality_score=quality_score,
                anomaly_count=anomaly_count,
                alerts=alerts,
                additional_info=additional_info
            )
            
            if email_sent:
                logger.info("✅ Alert email sent successfully")
            else:
                logger.warning("⚠️ Alert email not sent (disabled or failed)")
            
            return {
                "status": "alerts_triggered",
                "alert_count": len(alerts),
                "alerts": alerts,
                "email_sent": email_sent
            }
                
        else:
            logger.info("✅ All quality checks passed - no alerts needed")
            
            # Optionally send success notification
            # Uncomment these lines if you want success emails:
            alert_manager.send_success_notification(
                company_name=company_name or "Unknown Company",
                quality_score=quality_score,
                article_count=article_count,
                sec_count=sec_count
            )
            
            return {
                "status": "success",
                "alert_count": 0,
                "quality_score": quality_score,
                "anomaly_count": anomaly_count
            }
        
    except Exception as e:
        logger.error(f"❌ Alert check failed: {e}", exc_info=True)
        
        # Try to send failure notification
        try:
            alert_manager = AlertManager()
            company_name = safe_xcom_pull(ti, 'company_name', task_ids='acquire_company_data') or "Unknown"
            
            # Send simple error email
            alert_manager.send_email(
                subject=f"❌ Pipeline Error: {company_name}",
                body=f"The alert check task failed with error:\n\n{str(e)}\n\nPlease check Airflow logs for details.",
                html_body=f"""
                <html>
                <body>
                    <h2 style="color: #f44336;">❌ Pipeline Error</h2>
                    <p><strong>Company:</strong> {company_name}</p>
                    <p><strong>Error:</strong></p>
                    <pre style="background-color: #f5f5f5; padding: 10px;">{str(e)}</pre>
                    <p>Please check Airflow logs for details.</p>
                </body>
                </html>
                """
            )
        except Exception as email_error:
            logger.error(f"Failed to send failure notification: {email_error}")
        
        raise


# Define tasks
init_db_task = PythonOperator(
    task_id='initialize_database',
    python_callable=initialize_database_task,
    dag=dag,
)

acquire_data = PythonOperator(
    task_id='acquire_company_data',
    python_callable=acquire_company_data_task,
    dag=dag,
)

preprocess = PythonOperator(
    task_id='preprocess_data',
    python_callable=preprocess_data_task,
    dag=dag,
)

validate = PythonOperator(
    task_id='validate_schema',
    python_callable=validate_schema_task,
    dag=dag,
)

detect_anomalies = PythonOperator(
    task_id='detect_anomalies',
    python_callable=detect_anomalies_task,
    dag=dag,
)

detect_bias = PythonOperator(
    task_id='detect_bias',
    python_callable=detect_bias_task,
    dag=dag,
)

mitigate_bias = PythonOperator(
    task_id='mitigate_bias',
    python_callable=mitigate_bias_task,
    dag=dag,
)

store_db = PythonOperator(
    task_id='store_to_database',
    python_callable=store_to_database_task,
    dag=dag,
)

generate_stats = PythonOperator(
    task_id='generate_statistics',
    python_callable=generate_statistics_task,
    dag=dag,
)

check_alerts = PythonOperator(
    task_id='check_and_alert',
    python_callable=check_and_alert_task,
    dag=dag,
)


# Task dependency definitions
init_db_task >> acquire_data >> preprocess

# Parallel validation and bias detection
preprocess >> validate >> detect_anomalies
preprocess >> detect_bias >> mitigate_bias

# Wait for both branches before storing
[detect_anomalies, mitigate_bias] >> store_db >> generate_stats >> check_alerts
