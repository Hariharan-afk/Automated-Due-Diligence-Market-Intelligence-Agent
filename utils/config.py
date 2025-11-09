# utils/config.py
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration management for the researcher agent"""
    
    # API Keys
    QUERY_PARSER_MODEL_API_KEY: Optional[str] = os.getenv("QUERY_PARSER_MODEL_API_KEY")
    SEC_API_KEY: Optional[str] = os.getenv("SEC_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")  # For table summaries
    
    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "researcher_db")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: Optional[str] = os.getenv("DB_PASSWORD")
    
    # Vector Database Configuration (Qdrant)
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "sec_filings")
    
    # Embedding Model Configuration
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    
    # Chunking Configuration
    TEXT_CHUNK_SIZE: int = int(os.getenv("TEXT_CHUNK_SIZE", "500"))
    TEXT_CHUNK_OVERLAP: int = int(os.getenv("TEXT_CHUNK_OVERLAP", "75"))
    
    # LLM Configuration for Table Summaries
    TABLE_SUMMARY_MODEL: str = os.getenv("TABLE_SUMMARY_MODEL", "llama-3.3-70b-versatile")
    TABLE_SUMMARY_TEMPERATURE: float = float(os.getenv("TABLE_SUMMARY_TEMPERATURE", "0.3"))
    TABLE_SUMMARY_MAX_TOKENS: int = int(os.getenv("TABLE_SUMMARY_MAX_TOKENS", "200"))
    
    # Rate Limiting
    SEC_API_RATE_LIMIT: float = float(os.getenv("SEC_API_RATE_LIMIT", "8"))  # requests per second
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that all required configurations are set"""
        required_keys = [
            'QUERY_PARSER_MODEL_API_KEY',
            'SEC_API_KEY',
            'GROQ_API_KEY',
            'DB_PASSWORD'
        ]
        
        missing_keys = []
        for key in required_keys:
            if not getattr(cls, key):
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(f"Missing required configuration: {', '.join(missing_keys)}")
        
        return True

config = Config()
QUERY_PARSER_MODEL_API_KEY = config.QUERY_PARSER_MODEL_API_KEY