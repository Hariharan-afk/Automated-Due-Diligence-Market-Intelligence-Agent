# src/embeddings/embedding_generator.py
"""Generate vector embeddings from text using sentence transformers"""

from typing import List, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingGenerator:
    """
    Generates vector embeddings from text
    
    Features:
    - Uses SentenceTransformer models
    - Batch processing for efficiency
    - L2 normalization for cosine similarity
    - GPU support (automatic detection)
    - Configurable model selection
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding generator
        
        Args:
            model_name: Sentence-transformer model name
                       (default from config: all-mpnet-base-v2)
        """
        self.model_name = model_name or config.pipeline.embedding_model
        
        # GPU detection
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading embedding model: {self.model_name} on {self.device}")
        
        # Load model
        self.model = SentenceTransformer(self.model_name, device=self.device)
        
        # Get dimension
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        logger.info(
            f"EmbeddingGenerator ready "
            f"(model: {self.model_name}, dim: {self.dimension}, device: {self.device})"
        )
    
    def generate_embeddings(
        self,
        texts: Union[str, List[str]],
        batch_size: Optional[int] = None,
        normalize: bool = True,
        show_progress: bool = False
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for text(s) (PRODUCTION-READY)
        
        Args:
            texts: Single text string or list of texts
            batch_size: Batch size for processing (default from config: 32)
            normalize: L2-normalize embeddings for cosine similarity (default True)
            show_progress: Show progress bar for large batches
            
        Returns:
            Numpy array of embeddings
            - Single text input: shape (dimension,)
            - Multiple texts input: shape (n_texts, dimension)
        """
        # Handle single string
        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]
        
        if not texts:
            logger.warning("Empty text list provided")
            return np.array([])
        
        batch_size = batch_size or config.pipeline.batch_size
        
        logger.info(
            f"Generating embeddings for {len(texts)} texts "
            f"(batch_size: {batch_size}, normalize: {normalize})"
        )
        
        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=normalize
        )
        
        logger.info(f"Generated {len(embeddings)} embeddings of dimension {self.dimension}")
        
        # Return single array if single input
        if single_input:
            return embeddings[0]
        
        return embeddings
    
    def generate_embedding(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Generate embedding for single text (PRODUCTION-READY)
        
        Convenience method for single text
        
        Args:
            text: Text to embed
            normalize: Whether to normalize
            
        Returns:
            Embedding vector (dimension,)
        """
        return self.generate_embeddings(text, normalize=normalize)
    
    @staticmethod
    def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
        """
        L2-normalize embedding vector (PRODUCTION-READY)
        
        Args:
            embedding: Embedding vector
            
        Returns:
            Normalized embedding (norm = 1.0)
        """
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm
    
    def get_model_info(self) -> dict:
        """
        Get model information (PRODUCTION-READY)
        
        Returns:
            Dict with model specifications
        """
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "device": self.device,
            "max_seq_length": self.model.max_seq_length
        }
    
    def embed_chunks(
        self,
        chunks: List[dict],
        text_field: str = "text",
        batch_size: Optional[int] = None
    ) -> List[dict]:
        """
        Generate embeddings for chunk dicts (PRODUCTION-READY)
        
        Convenience method that takes chunk dicts and adds embeddings
        
        Args:
            chunks: List of chunk dicts with text field
            text_field: Name of field containing text (default "text")
            batch_size: Batch size
            
        Returns:
            Chunks with added "embedding" field
        """
        # Extract texts
        texts = [chunk.get(text_field, "") for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.generate_embeddings(
            texts,
            batch_size=batch_size,
            show_progress=len(texts) > 100
        )
        
        # Add embeddings to chunks
        chunks_with_embeddings = []
        for chunk, embedding in zip(chunks, embeddings):
            chunk_with_emb = chunk.copy()
            chunk_with_emb['embedding'] = embedding.tolist()  # Convert to list for JSON
            chunks_with_embeddings.append(chunk_with_emb)
        
        return chunks_with_embeddings
