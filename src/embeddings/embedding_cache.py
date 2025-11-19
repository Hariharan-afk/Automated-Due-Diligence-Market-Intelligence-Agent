"""Cache embeddings to avoid recomputation"""

from typing import Optional, Dict, Any
import numpy as np
import hashlib
import pickle
from pathlib import Path
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """
    Caches embeddings to disk for reuse
    
    Features:
    - Hash-based caching (deterministic keys)
    - Disk persistence
    - LRU eviction (optional)
    - Statistics tracking
    """
    
    def __init__(self, cache_dir: Optional[str] = None, max_size_mb: int = 1000):
        """
        Initialize embedding cache
        
        Args:
            cache_dir: Directory for cache files (default: data/cache/embedding_cache)
            max_size_mb: Maximum cache size in MB (default: 1000 MB = 1 GB)
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            project_root = Path(__file__).parent.parent.parent
            self.cache_dir = project_root / "data" / "cache" / "embedding_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # Stats
        self.hits = 0
        self.misses = 0
        
        logger.info(f"EmbeddingCache initialized (dir: {self.cache_dir}, max: {max_size_mb}MB)")
    
    def get(self, text: str) -> Optional[np.ndarray]:
        """
        Get cached embedding for text (PRODUCTION-READY)
        
        Args:
            text: Text to lookup
            
        Returns:
            Cached embedding or None if not found
        """
        cache_key = self._compute_hash(text)
        cache_file = self.cache_dir / f"{cache_key}.npy"
        
        if cache_file.exists():
            try:
                embedding = np.load(cache_file)
                self.hits += 1
                logger.debug(f"Cache hit: {cache_key}")
                return embedding
            except Exception as e:
                logger.warning(f"Failed to load cache {cache_key}: {e}")
                self.misses += 1
                return None
        
        self.misses += 1
        logger.debug(f"Cache miss: {cache_key}")
        return None
    
    def set(self, text: str, embedding: np.ndarray):
        """
        Cache embedding for text (PRODUCTION-READY)
        
        Args:
            text: Text key
            embedding: Embedding to cache
        """
        cache_key = self._compute_hash(text)
        cache_file = self.cache_dir / f"{cache_key}.npy"
        
        try:
            np.save(cache_file, embedding)
            logger.debug(f"Cached embedding: {cache_key}")
            
            # Check cache size and evict if needed
            self._check_and_evict()
            
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")
    
    def get_or_generate(
        self,
        text: str,
        generator: 'EmbeddingGenerator'
    ) -> np.ndarray:
        """
        Get from cache or generate and cache (PRODUCTION-READY)
        
        Args:
            text: Text to embed
            generator: EmbeddingGenerator instance
            
        Returns:
            Embedding (from cache or newly generated)
        """
        # Try cache first
        cached = self.get(text)
        if cached is not None:
            return cached
        
        # Generate new embedding
        embedding = generator.generate_embedding(text)
        
        # Cache it
        self.set(text, embedding)
        
        return embedding
    
    @staticmethod
    def _compute_hash(text: str) -> str:
        """
        Compute deterministic hash of text (PRODUCTION-READY)
        
        Args:
            text: Text to hash
            
        Returns:
            Hex hash string
        """
        # Use MD5 for speed (not cryptographic use)
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _check_and_evict(self):
        """
        Check cache size and evict old entries if needed (PRODUCTION-READY)
        
        Uses LRU (Least Recently Used) eviction
        """
        # Calculate current cache size
        cache_files = list(self.cache_dir.glob("*.npy"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        if total_size > self.max_size_bytes:
            logger.info(
                f"Cache size {total_size/1024/1024:.1f}MB exceeds limit "
                f"{self.max_size_bytes/1024/1024:.1f}MB - evicting old entries"
            )
            
            # Sort by access time (oldest first)
            cache_files_sorted = sorted(cache_files, key=lambda f: f.stat().st_atime)
            
            # Delete oldest until under limit
            for cache_file in cache_files_sorted:
                if total_size <= self.max_size_bytes:
                    break
                
                file_size = cache_file.stat().st_size
                cache_file.unlink()
                total_size -= file_size
                logger.debug(f"Evicted: {cache_file.name}")
            
            logger.info(f"Cache size after eviction: {total_size/1024/1024:.1f}MB")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics (PRODUCTION-READY)
        
        Returns:
            Dict with cache stats
        """
        cache_files = list(self.cache_dir.glob("*.npy"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            "cache_dir": str(self.cache_dir),
            "num_entries": len(cache_files),
            "total_size_mb": total_size / 1024 / 1024,
            "max_size_mb": self.max_size_bytes / 1024 / 1024,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": hit_rate
        }
        
        return stats
    
    def clear_cache(self):
        """
        Clear all cached embeddings (PRODUCTION-READY)
        
        Use with caution - deletes all cached data
        """
        cache_files = list(self.cache_dir.glob("*.npy"))
        
        for cache_file in cache_files:
            cache_file.unlink()
        
        logger.info(f"Cleared {len(cache_files)} cache entries")
        
        # Reset stats
        self.hits = 0
        self.misses = 0
    
    def _save_checkpoint(self, checkpoint_file: Path, data: Dict):
        """Save checkpoint (PRODUCTION-READY)"""
        with open(checkpoint_file, 'w') as f:
            json.dump(data, f)
    
    def _load_checkpoint(self, checkpoint_file: Path) -> Dict:
        """Load checkpoint (PRODUCTION-READY)"""
        with open(checkpoint_file, 'r') as f:
            return json.load(f)