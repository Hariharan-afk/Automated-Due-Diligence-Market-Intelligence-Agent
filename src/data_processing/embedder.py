# src/data_processing/embedder.py
"""Text embedding using FinE5 model optimized for financial text"""

from sentence_transformers import SentenceTransformer
from typing import List, Union
import numpy as np
import torch
from transformers import AutoModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class FinancialEmbedder:
    """
    Embedder using FinE5 model for financial text
    
    Features:
    - Batch processing for efficiency
    - GPU support (if available)
    - Normalized embeddings for cosine similarity
    """
    
    def __init__(self, config: dict):
        """
        Initialize embedder
        
        Args:
            config: Embedding configuration
                {
                    'model_name': 'FinanceMTEB/FinE5',
                    'device': 'cpu' or 'cuda',
                    'batch_size': 32,
                    'max_length': 512
                }
        """
        self.config = config
        self.model_name = config.get('model_name', 'FinanceMTEB/FinE5')
        self.device = config.get('device', 'cpu')
        self.batch_size = config.get('batch_size', 32)
        self.max_length = config.get('max_length', 512)
        
        # Check GPU availability
        if self.device == 'cuda' and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available, falling back to CPU")
            self.device = 'cpu'
        
        # Load model
        logger.info(f"Loading embedding model: {self.model_name} on {self.device}")
        self.model = SentenceTransformer(self.model_name)
        
        # Get embedding dimension
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        logger.info(f"Embedder initialized: dim={self.embedding_dim}, device={self.device}")
    
    def embed(self, texts: Union[str, List[str]], 
             show_progress: bool = False) -> np.ndarray:
        """
        Embed text(s) into vector representation
        
        Args:
            texts: Single text or list of texts
            show_progress: Show progress bar for large batches
        
        Returns:
            Numpy array of embeddings (n_texts, embedding_dim)
        """
        # Handle single text
        if isinstance(texts, str):
            texts = [texts]
        
        # Embed
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
            convert_to_numpy=True
        )
        
        return embeddings
    
    def embed_chunks(self, chunks: List[str], 
                    show_progress: bool = True) -> List[List[float]]:
        """
        Embed multiple chunks (convenience method)
        
        Args:
            chunks: List of text chunks
            show_progress: Show progress bar
        
        Returns:
            List of embedding vectors
        """
        logger.info(f"Embedding {len(chunks)} chunks...")
        
        embeddings = self.embed(chunks, show_progress=show_progress)
        
        # Convert to list of lists (for JSON serialization)
        embeddings_list = [emb.tolist() for emb in embeddings]
        
        logger.info(f"Embedded {len(chunks)} chunks successfully")
        
        return embeddings_list
    
    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query (for search)
        
        Args:
            query: Query text
        
        Returns:
            Embedding vector as list
        """
        embedding = self.embed(query)
        return embedding[0].tolist()
    
    def get_embedding_dim(self) -> int:
        """Get embedding dimension"""
        return self.embedding_dim
    
    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'model'):
            del self.model
            if self.device == 'cuda':
                torch.cuda.empty_cache()