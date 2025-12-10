"""
Airflow Helper Utilities

Shared functions for all DAGs
"""

import os
import yaml
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_companies_list(config_path: str = None) -> List[Dict[str, Any]]:
    """
    Load companies from companies.yaml
    
    Returns:
        List of company dicts with ticker, name, cik, etc.
    """
    if config_path is None:
        # Default to Data_Pipeline/configs/companies.yaml
        base_dir = Path(__file__).parent.parent.parent.parent
        config_path = base_dir / 'configs' / 'companies.yaml'
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config.get('companies', [])


def load_env_variables() -> Dict[str, str]:
    """
    Load environment variables needed for cloud connections
    
    Returns:
        Dict of environment variables
    """
    required_vars = [
        'GCP_BUCKET_NAME',
        'GCP_PROJECT_ID',
        'GCP_CREDENTIALS_PATH',
        'QDRANT_URL',
        'QDRANT_API_KEY',
        'POSTGRES_HOST',
        'POSTGRES_PORT',
        'POSTGRES_DB',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'GROQ_API_KEY',
        'SEC_API_KEY',
    ]
    
    env_vars = {}
    missing = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            env_vars[var] = value
        else:
            missing.append(var)
    
    if missing:
        logger.warning(f"Missing environment variables: {missing}")
    
    return env_vars


def send_notification(
    message: str,
    level: str = 'INFO',
    **kwargs
) -> None:
    """
    Send notification (log for now, can extend to email/Slack)
    
    Args:
        message: Notification message
        level: Log level (INFO, WARNING, ERROR)
        **kwargs: Additional context
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"{message} | Context: {kwargs}")


def format_dag_run_timestamp() -> str:
    """Get formatted timestamp for DAG run"""
    return datetime.utcnow().strftime('%Y%m%d_%H%M%S')


def get_collection_name() -> str:
    """Get Qdrant collection name from env or default"""
    return os.getenv('QDRANT_COLLECTION', 'company_data')
