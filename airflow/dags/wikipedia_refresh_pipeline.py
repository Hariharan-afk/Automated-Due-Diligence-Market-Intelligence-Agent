"""Wikipedia Refresh Pipeline - Using Custom Operators"""

from airflow import DAG
from datetime import datetime, timedelta
import sys
from pathlib import Path

# ✅ FIXED: Add plugins/operators to Python path
sys.path.insert(0, '/opt/airflow/plugins')

# ✅ Now this import will work
from operators.wikipedia_process_operator import WikipediaProcessOperator
from utils.config import config

# Define DAG
default_args = {
    'owner': 'data_pipeline',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'wikipedia_refresh_pipeline',
    default_args=default_args,
    description='Weekly Wikipedia refresh using custom operators',
    schedule_interval='0 3 * * 0',  # Every Sunday at 3 AM
    start_date=datetime(2024, 11, 1),
    catchup=False,
    tags=['wikipedia', 'weekly', 'operators'],
) as dag:
    
    # Create task for each company using custom operator
    for company in config.companies:
        WikipediaProcessOperator(
            task_id=f'process_wiki_{company["ticker"]}',
            ticker=company['ticker']
        )