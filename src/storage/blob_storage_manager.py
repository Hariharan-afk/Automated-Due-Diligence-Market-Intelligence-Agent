# src/storage/blob_storage_manager.py
"""Manager for blob/file storage operations"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BlobStorageManager:
    """
    Manages file storage for raw documents and processed data
    
    For MVP: Uses local filesystem
    For Production: Can be extended to use GCS/S3
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize blob storage manager
        
        Args:
            base_path: Base directory for storage (default from config)
        """
        self.base_path = Path(base_path or config.project_root / "data")
        
        # Create directory structure
        self.raw_path = self.base_path / "raw"
        self.processed_path = self.base_path / "processed"
        self.cache_path = self.base_path / "cache"
        
        self._ensure_directories()
        
        logger.info(f"BlobStorageManager initialized: {self.base_path}")
    
    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [
            self.raw_path / "sec_filings",
            self.raw_path / "wikipedia",
            self.raw_path / "news",
            self.processed_path / "chunks",
            self.processed_path / "embeddings",
            self.cache_path / "table_summaries",
            self.cache_path / "embedding_cache"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    # ==================== SEC FILINGS ====================
    
    def save_sec_filing(
        self,
        ticker: str,
        filing_type: str,
        filing_date: str,
        accession_number: str,
        content: str,
        file_format: str = "html"
    ) -> str:
        """
        Save raw SEC filing
        
        Args:
            ticker: Company ticker
            filing_type: Filing type (10-K, 10-Q)
            filing_date: Filing date (YYYY-MM-DD)
            accession_number: SEC accession number
            content: Raw filing content
            file_format: File format (html, json, txt)
            
        Returns:
            Path to saved file
        """
        # Create company directory
        company_dir = self.raw_path / "sec_filings" / ticker / filing_type
        company_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename: YYYY-MM-DD_accession.format
        filename = f"{filing_date}_{accession_number}.{file_format}"
        filepath = company_dir / filename
        
        # Save content
        if file_format == "json":
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        logger.info(f"Saved SEC filing: {ticker} {filing_type} to {filepath}")
        return str(filepath)
    
    def load_sec_filing(
        self,
        ticker: str,
        filing_type: str,
        filing_date: str,
        accession_number: str,
        file_format: str = "html"
    ) -> Optional[str]:
        """
        Load raw SEC filing
        
        Args:
            ticker: Company ticker
            filing_type: Filing type
            filing_date: Filing date
            accession_number: Accession number
            file_format: File format
            
        Returns:
            Filing content or None if not found
        """
        filename = f"{filing_date}_{accession_number}.{file_format}"
        filepath = self.raw_path / "sec_filings" / ticker / filing_type / filename
        
        if not filepath.exists():
            logger.warning(f"Filing not found: {filepath}")
            return None
        
        if file_format == "json":
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
    
    def filing_exists(
        self,
        ticker: str,
        filing_type: str,
        filing_date: str,
        accession_number: str
    ) -> bool:
        """Check if filing already exists in storage"""
        filename = f"{filing_date}_{accession_number}.html"
        filepath = self.raw_path / "sec_filings" / ticker / filing_type / filename
        return filepath.exists()
    
    # ==================== WIKIPEDIA ====================
    
    def save_wikipedia_page(
        self,
        ticker: str,
        page_title: str,
        content: str,
        revision_id: int
    ) -> str:
        """
        Save Wikipedia page content
        
        Args:
            ticker: Company ticker
            page_title: Wikipedia page title
            content: Page content
            revision_id: Wikipedia revision ID
            
        Returns:
            Path to saved file
        """
        wiki_dir = self.raw_path / "wikipedia" / ticker
        wiki_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{page_title}_{revision_id}.json"
        filepath = wiki_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved Wikipedia page: {ticker} to {filepath}")
        return str(filepath)
    
    def load_wikipedia_page(
        self,
        ticker: str,
        page_title: str,
        revision_id: int
    ) -> Optional[str]:
        """Load Wikipedia page content"""
        filename = f"{page_title}_{revision_id}.txt"
        filepath = self.raw_path / "wikipedia" / ticker / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    # ==================== NEWS ====================
    
    def save_news_article(
        self,
        ticker: str,
        article_id: str,
        content: str,
        published_date: str
    ) -> str:
        """
        Save news article
        
        Args:
            ticker: Company ticker
            article_id: Unique article identifier
            content: Article content
            published_date: Publication date (YYYY-MM-DD)
            
        Returns:
            Path to saved file
        """
        # Organize by date
        date_dir = self.raw_path / "news" / published_date
        date_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{ticker}_{article_id}.json"
        filepath = date_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

        logger.debug(f"Saved news article: {filepath}")
        return str(filepath)
    
    def delete_old_news(self, days_old: int = 3) -> int:
        """
        Delete news articles older than specified days
        
        Args:
            days_old: Delete articles older than this many days
            
        Returns:
            Number of files deleted
        """
        news_dir = self.raw_path / "news"
        if not news_dir.exists():
            return 0
        
        deleted_count = 0
        cutoff_date = datetime.now().date()
        
        # Iterate through date directories
        for date_dir in news_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            try:
                # Parse date from directory name (YYYY-MM-DD)
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d").date()
                
                # Check if older than cutoff
                age_days = (cutoff_date - dir_date).days
                if age_days > days_old:
                    # Delete entire directory
                    import shutil
                    shutil.rmtree(date_dir)
                    deleted_count += 1
                    logger.info(f"Deleted old news directory: {date_dir.name}")
            
            except ValueError:
                # Invalid directory name format
                continue
        
        return deleted_count
    
    # ==================== PROCESSED DATA ====================
    
    def save_chunks(
        self,
        ticker: str,
        filing_type: str,
        accession_number: str,
        chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Save processed chunks to JSON
        
        Args:
            ticker: Company ticker
            filing_type: Filing type
            accession_number: Accession number
            chunks: List of chunk dictionaries
            
        Returns:
            Path to saved file
        """
        chunks_dir = self.processed_path / "chunks" / ticker
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{filing_type}_{accession_number}_chunks.json"
        filepath = chunks_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2)
        
        logger.info(f"Saved {len(chunks)} chunks to {filepath}")
        return str(filepath)
    
    def load_chunks(
        self,
        ticker: str,
        filing_type: str,
        accession_number: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load processed chunks"""
        filename = f"{filing_type}_{accession_number}_chunks.json"
        filepath = self.processed_path / "chunks" / ticker / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # ==================== CACHE ====================
    
    def save_table_summary(
        self,
        table_hash: str,
        summary: str
    ) -> str:
        """
        Cache table summary
        
        Args:
            table_hash: Hash of table content (for deduplication)
            summary: Generated summary text
            
        Returns:
            Path to cached file
        """
        cache_dir = self.cache_path / "table_summaries"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{table_hash}.txt"
        filepath = cache_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        logger.debug(f"Cached table summary: {table_hash}")
        return str(filepath)
    
    def get_table_summary(self, table_hash: str) -> Optional[str]:
        """
        Get cached table summary
        
        Args:
            table_hash: Hash of table content
            
        Returns:
            Cached summary or None
        """
        filepath = self.cache_path / "table_summaries" / f"{table_hash}.txt"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    @staticmethod
    def compute_table_hash(table_data: str) -> str:
        """
        Compute hash of table content for caching
        
        Args:
            table_data: Table content as string
            
        Returns:
            MD5 hash
        """
        return hashlib.md5(table_data.encode('utf-8')).hexdigest()
    
    # ==================== UTILITIES ====================
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        
        def get_dir_size(path: Path) -> int:
            """Calculate directory size in bytes"""
            total = 0
            for item in path.rglob('*'):
                if item.is_file():
                    total += item.stat().st_size
            return total
        
        def count_files(path: Path) -> int:
            """Count files in directory"""
            return sum(1 for _ in path.rglob('*') if _.is_file())
        
        stats = {
            "base_path": str(self.base_path),
            "sec_filings": {
                "count": count_files(self.raw_path / "sec_filings"),
                "size_mb": get_dir_size(self.raw_path / "sec_filings") / (1024 * 1024)
            },
            "wikipedia": {
                "count": count_files(self.raw_path / "wikipedia"),
                "size_mb": get_dir_size(self.raw_path / "wikipedia") / (1024 * 1024)
            },
            "news": {
                "count": count_files(self.raw_path / "news"),
                "size_mb": get_dir_size(self.raw_path / "news") / (1024 * 1024)
            },
            "processed_chunks": {
                "count": count_files(self.processed_path / "chunks"),
                "size_mb": get_dir_size(self.processed_path / "chunks") / (1024 * 1024)
            },
            "cache": {
                "table_summaries": count_files(self.cache_path / "table_summaries")
            }
        }
        
        return stats
    
    def cleanup_cache(self, max_age_days: int = 30) -> int:
        """
        Clean up old cache files
        
        Args:
            max_age_days: Remove files older than this
            
        Returns:
            Number of files deleted
        """
        deleted = 0
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        
        for cache_dir in [self.cache_path / "table_summaries", self.cache_path / "embedding_cache"]:
            if not cache_dir.exists():
                continue
            
            for filepath in cache_dir.glob('*'):
                if filepath.is_file() and filepath.stat().st_mtime < cutoff_time:
                    filepath.unlink()
                    deleted += 1
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old cache files")
        
        return deleted
