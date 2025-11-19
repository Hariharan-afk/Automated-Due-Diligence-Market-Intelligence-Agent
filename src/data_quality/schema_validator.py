# src/data_quality/schema_validator.py
"""Validates data schemas and structure"""

from typing import Dict, Any, List, Optional
import re

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SchemaValidator:
    """
    Validates data conforms to expected schemas
    
    Validates:
    - Chunk structure (all required fields present)
    - Field formats (ticker format, dates, etc.)
    - Data types
    - Value constraints
    """
    
    def __init__(self):
        """Initialize schema validator"""
        logger.info("SchemaValidator initialized")
    
    def validate_chunk(self, chunk: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate chunk structure (PRODUCTION-READY)
        
        Args:
            chunk: Chunk dict to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields
        required_fields = ['chunk_id', 'text', 'metadata']
        for field in required_fields:
            if field not in chunk:
                errors.append(f"Missing required field: {field}")
        
        # Validate chunk_id format
        if 'chunk_id' in chunk:
            if not self._is_valid_chunk_id(chunk['chunk_id']):
                errors.append(f"Invalid chunk_id format: {chunk['chunk_id']}")
        
        # Validate text is not empty
        if 'text' in chunk:
            if not chunk['text'] or not chunk['text'].strip():
                errors.append("Text field is empty")
        
        # Validate metadata structure
        if 'metadata' in chunk:
            metadata_errors = self._validate_metadata(chunk['metadata'])
            errors.extend(metadata_errors)
        
        # Validate embedding if present
        if 'embedding' in chunk:
            emb_errors = self._validate_embedding(chunk['embedding'])
            errors.extend(emb_errors)
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Chunk validation failed: {errors}")
        
        return is_valid, errors
    
    def _is_valid_chunk_id(self, chunk_id: str) -> bool:
        """Validate chunk ID format (PRODUCTION-READY)"""
        # Format: TICKER_TYPE_..._POSITION
        # Examples:
        # AAPL_10K_2024_1A_text_001
        # AAPL_WIKI_1234567890_text_000
        # AAPL_NEWS_20241117_abc12345_text_000
        
        if not chunk_id:
            return False
        
        parts = chunk_id.split('_')
        
        # Must have at least 4 parts
        if len(parts) < 4:
            return False
        
        # First part should be ticker (1-5 uppercase letters)
        ticker = parts[0]
        if not re.match(r'^[A-Z]{1,5}$', ticker):
            return False
        
        # Last part should be position (3 digits)
        position = parts[-1]
        if not re.match(r'^\d{3}$', position):
            return False
        
        return True
    
    def _validate_metadata(self, metadata: Dict[str, Any]) -> List[str]:
        """Validate metadata structure (PRODUCTION-READY)"""
        errors = []
        
        # Required metadata fields
        required = ['source_type', 'ticker', 'company_name']
        for field in required:
            if field not in metadata:
                errors.append(f"Missing metadata field: {field}")
        
        # Validate source_type
        if 'source_type' in metadata:
            valid_sources = ['sec_filing', 'wikipedia', 'news']
            if metadata['source_type'] not in valid_sources:
                errors.append(f"Invalid source_type: {metadata['source_type']}")
        
        # Validate ticker format
        if 'ticker' in metadata:
            if not re.match(r'^[A-Z]{1,5}$', metadata['ticker']):
                errors.append(f"Invalid ticker format: {metadata['ticker']}")
        
        return errors
    
    def _validate_embedding(self, embedding: List[float]) -> List[str]:
        """Validate embedding vector (PRODUCTION-READY)"""
        errors = []
        
        # Check is list
        if not isinstance(embedding, list):
            errors.append(f"Embedding must be list, got {type(embedding)}")
            return errors
        
        # Check dimension (768 for all-mpnet-base-v2, 384 for MiniLM)
        expected_dims = [768, 384]
        if len(embedding) not in expected_dims:
            errors.append(
                f"Embedding dimension {len(embedding)} not in expected {expected_dims}"
            )
        
        # Check all values are floats
        if not all(isinstance(v, (int, float)) for v in embedding):
            errors.append("Embedding contains non-numeric values")
        
        return errors
    
    def validate_batch(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate batch of chunks (PRODUCTION-READY)
        
        Args:
            chunks: List of chunks to validate
            
        Returns:
            Validation report dict
        """
        total = len(chunks)
        valid = 0
        invalid = 0
        all_errors = []
        
        for chunk in chunks:
            is_valid, errors = self.validate_chunk(chunk)
            
            if is_valid:
                valid += 1
            else:
                invalid += 1
                all_errors.extend(errors)
        
        report = {
            "total_chunks": total,
            "valid_chunks": valid,
            "invalid_chunks": invalid,
            "validation_rate": (valid / total * 100) if total > 0 else 0,
            "errors": all_errors[:10]  # First 10 errors
        }
        
        logger.info(
            f"Validation: {valid}/{total} valid ({report['validation_rate']:.1f}%)"
        )
        
        return report