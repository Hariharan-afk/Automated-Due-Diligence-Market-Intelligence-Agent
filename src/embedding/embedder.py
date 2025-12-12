"""
Text Embedder using BGE-large-en-v1.5

Generates high-quality embeddings optimized for financial/business documents.
"""

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union
import torch
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class Embedder:
    """
    Text embedder using BGE-large-en-v1.5
    
    Features:
    - 1024-dimensional embeddings
    - Optimized for retrieval tasks
    - Support for batch processing
    - Instruction-based queries for better retrieval
    - GPU acceleration (if available)
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-large-en-v1.5",
        device: str = None,
        cache_folder: str = None
    ):
        """
        Initialize embedder
        
        Args:
            model_name: HuggingFace model name
            device: 'cuda', 'cpu', or None (auto-detect)
            cache_folder: Where to cache the model
        """
        # Auto-detect device
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        self.device = device
        self.model_name = model_name
        
        logger.info(f"Loading embedding model: {model_name}")
        logger.info(f"Device: {device}")
        
        # Load model
        self.model = SentenceTransformer(
            model_name,
            device=device,
            cache_folder=cache_folder
        )
        
        # Get embedding dimension
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        logger.info(f"Model loaded successfully")
        logger.info(f"Embedding dimension: {self.dimension}")
        logger.info(f"Max sequence length: {self.model.max_seq_length}")
    
    def embed(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Embed a single text
        
        Args:
            text: Text to embed
            normalize: Whether to normalize embedding to unit length
        
        Returns:
            numpy array of shape (dimension,)
        """
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=normalize
        )
        return embedding
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Embed multiple texts efficiently
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar
            normalize: Whether to normalize embeddings
        
        Returns:
            numpy array of shape (len(texts), dimension)
        """
        logger.info(f"Embedding {len(texts)} texts in batches of {batch_size}")
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=normalize
        )
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def embed_with_instruction(
        self,
        text: str,
        instruction: str = None,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Embed text with instruction prefix (for queries)
        
        For BGE models, instruction improves retrieval quality:
        - Queries: "Represent this sentence for searching relevant passages: "
        - Documents: No instruction needed
        
        Args:
            text: Text to embed
            instruction: Instruction prefix
            normalize: Whether to normalize embedding
        
        Returns:
            numpy array of shape (dimension,)
        """
        if instruction:
            text = f"{instruction}{text}"
        
        return self.embed(text, normalize=normalize)
    
    def embed_query(self, query: str, normalize: bool = True) -> np.ndarray:
        """
        Embed a search query (with default instruction)
        
        Args:
            query: Search query
            normalize: Whether to normalize embedding
        
        Returns:
            numpy array of shape (dimension,)
        """
        instruction = "Represent this sentence for searching relevant passages: "
        return self.embed_with_instruction(query, instruction, normalize)
    
    def embed_documents(
        self,
        documents: List[str],
        batch_size: int = 32,
        show_progress: bool = True,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Embed documents (no instruction prefix)
        
        Args:
            documents: List of documents to embed
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar
            normalize: Whether to normalize embeddings
        
        Returns:
            numpy array of shape (len(documents), dimension)
        """
        return self.embed_batch(
            documents,
            batch_size=batch_size,
            show_progress=show_progress,
            normalize=normalize
        )
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension
    
    def get_model_info(self) -> dict:
        """Get model information"""
        return {
            'model_name': self.model_name,
            'dimension': self.dimension,
            'max_seq_length': self.model.max_seq_length,
            'device': self.device
        }


if __name__ == "__main__":
    # Example usage
    print("Testing Embedder...")
    
    # Initialize
    embedder = Embedder()
    
    # Test single embedding
    query = "What are Apple's revenue trends?"
    query_emb = embedder.embed_query(query)
    print(f"\nQuery embedding shape: {query_emb.shape}")
    print(f"Query embedding (first 5): {query_emb[:5]}")
    
    # Test batch embedding
    documents = [
        "Apple's revenue increased by 15% YoY to $394.3 billion.",
        "Microsoft reported quarterly earnings of $62.0 billion.",
        "Tesla delivered 1.8 million vehicles in 2024.",
    ]
    doc_embs = embedder.embed_documents(documents, show_progress=True)
    print(f"\nDocument embeddings shape: {doc_embs.shape}")
    
    # Test similarity
    similarities = np.dot(doc_embs, query_emb)
    print(f"\nSimilarities with query:")
    for i, (doc, sim) in enumerate(zip(documents, similarities)):
        print(f"  {i+1}. [{sim:.4f}] {doc[:50]}...")
    
    print(f"\n✅ Embedder test complete!")
    print(f"Model info: {embedder.get_model_info()}")
