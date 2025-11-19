# airflow/plugins/operators/storage_operator.py
"""Custom operator for atomic storage operations"""

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import Any, List, Dict
import sys
from pathlib import Path

sys.path.insert(0, '/opt/airflow')

from src.storage.vector_store_manager import VectorStoreManager
from src.storage.metadata_store_manager import MetadataStoreManager


class StorageOperator(BaseOperator):
    """
    Airflow operator for storing data atomically
    
    Stores data in both Qdrant and PostgreSQL with rollback on failure
    """
    
    template_fields = ['embeddings_task_id']
    ui_color = '#27AE60'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(
        self,
        embeddings_task_id: str,
        metadata_update_func: callable = None,
        **kwargs
    ):
        """
        Initialize operator
        
        Args:
            embeddings_task_id: Task ID that produces chunks with embeddings
            metadata_update_func: Function to update metadata after storage
        """
        super().__init__(**kwargs)
        self.embeddings_task_id = embeddings_task_id
        self.metadata_update_func = metadata_update_func
    
    def execute(self, context: Any) -> Dict[str, Any]:
        """Execute atomic storage"""
        # Get chunks with embeddings
        ti = context['task_instance']
        chunks_with_embeddings = ti.xcom_pull(task_ids=self.embeddings_task_id)
        
        if not chunks_with_embeddings:
            self.log.warning("No chunks received")
            return {"status": "no_data"}
        
        self.log.info(f"Storing {len(chunks_with_embeddings)} chunks")
        
        vector_store = VectorStoreManager()
        metadata_store = MetadataStoreManager()
        
        try:
            # Store in Qdrant
            self.log.info("Storing in Qdrant...")
            upserted = vector_store.upsert_chunks(chunks_with_embeddings)
            
            # Update metadata
            if self.metadata_update_func:
                self.log.info("Updating metadata...")
                self.metadata_update_func(metadata_store, chunks_with_embeddings)
            
            self.log.info(f"✅ Stored {upserted} chunks successfully")
            
            metadata_store.close()
            
            return {
                "status": "success",
                "chunks_stored": upserted
            }
        
        except Exception as e:
            self.log.error(f"Storage failed: {e}")
            
            # Rollback: delete from Qdrant
            self.log.warning("Rolling back...")
            chunk_ids = [c['chunk_id'] for c in chunks_with_embeddings]
            vector_store.delete_by_chunk_ids(chunk_ids)
            
            if metadata_store:
                metadata_store.close()
            
            raise