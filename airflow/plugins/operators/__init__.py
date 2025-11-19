# airflow/plugins/operators/__init__.py
"""Custom Airflow operators"""

import sys
sys.path.insert(0, '/opt/airflow/plugins')

# ✅ Use absolute imports (no dots)
from operators.wikipedia_process_operator import WikipediaProcessOperator
from operators.news_process_operator import NewsProcessOperator
from operators.embedding_operator import EmbeddingOperator
from operators.storage_operator import StorageOperator

__all__ = [
    'WikipediaProcessOperator',
    'NewsProcessOperator',
    'EmbeddingOperator',
    'StorageOperator'
]