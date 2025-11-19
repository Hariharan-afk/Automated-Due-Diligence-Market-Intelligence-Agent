# airflow/plugins/operators/embedding_operator.py
"""Custom operator for embedding generation"""

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import Any, List, Dict
import sys
from pathlib import Path

sys.path.insert(0, '/opt/airflow')

from src.embeddings.embedding_generator import EmbeddingGenerator
from src.embeddings.batch_processor import BatchProcessor


class EmbeddingOperator(BaseOperator):
    """
    Airflow operator for generating embeddings
    
    Takes chunks from previous task and generates embeddings
    """
    
    template_fields = ['chunks_task_id']
    ui_color = '#9B59B6'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(
        self,
        chunks_task_id: str,
        batch_size: int = None,
        use_batch_processor: bool = True,
        **kwargs
    ):
        """
        Initialize operator
        
        Args:
            chunks_task_id: Task ID that produces chunks
            batch_size: Batch size for processing
            use_batch_processor: Use batch processor for large batches
        """
        super().__init__(**kwargs)
        self.chunks_task_id = chunks_task_id
        self.batch_size = batch_size
        self.use_batch_processor = use_batch_processor
    
    def execute(self, context: Any) -> List[Dict[str, Any]]:
        """Execute embedding generation"""
        # Get chunks from previous task
        ti = context['task_instance']
        chunks = ti.xcom_pull(task_ids=self.chunks_task_id)
        
        if not chunks:
            self.log.warning("No chunks received")
            return []
        
        self.log.info(f"Generating embeddings for {len(chunks)} chunks")
        
        # Choose processor based on size
        if self.use_batch_processor and len(chunks) > 100:
            # Use batch processor for large batches
            processor = BatchProcessor(batch_size=self.batch_size)
            chunks_with_embeddings = processor.process_large_batch(chunks)
        else:
            # Use simple generator for small batches
            generator = EmbeddingGenerator()
            chunks_with_embeddings = generator.embed_chunks(chunks, batch_size=self.batch_size)
        
        self.log.info(f"✅ Generated {len(chunks_with_embeddings)} embeddings")
        
        return chunks_with_embeddings