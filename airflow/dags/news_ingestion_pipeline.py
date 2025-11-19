"""News Ingestion Pipeline - Using Custom Operators"""

from airflow import DAG
from datetime import datetime, timedelta
import sys
from pathlib import Path

# ✅ FIXED: Add plugins/operators to Python path
sys.path.insert(0, '/opt/airflow/plugins')

# ✅ Now this import will work
from operators.news_process_operator import NewsProcessOperator
from utils.config import config

default_args = {
    'owner': 'data_pipeline',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'news_ingestion_pipeline',
    default_args=default_args,
    description='News ingestion every 6 hours using custom operators',
    schedule_interval='0 */6 * * *',  # Every 6 hours
    start_date=datetime(2024, 11, 1),
    catchup=False,
    tags=['news', '6-hourly', 'operators'],
) as dag:
    
    # Create task for each company
    for company in config.companies:
        NewsProcessOperator(
            task_id=f'process_news_{company["ticker"]}',
            ticker=company['ticker'],
            days_back=3
        )