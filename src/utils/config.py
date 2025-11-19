# DATA_PIPELINE/src/utils/config.py
"""Configuration management system"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class DatabaseConfig:
    """Database configuration"""
    postgres_host: str
    postgres_port: int
    postgres_database: str
    postgres_user: str
    postgres_password: str
    qdrant_host: str
    qdrant_port: int
    qdrant_collection: str

@dataclass
class PipelineConfig:
    """Pipeline configuration"""
    chunk_size: int
    chunk_overlap: int
    batch_size: int
    embedding_model: str

@dataclass
class APIConfig:
    """API configuration"""
    news_api_key: str
    sec_api_key: str
    groq_api_key: str
    sec_rate_limit: int
    sec_user_agent: str
    # SEC-specific query settings
    sec_fetch_start_date: Optional[str] = None
    sec_fetch_end_date: Optional[str] = None
    sec_max_results_per_query: int = 50
    sec_fetch_all_pages: bool = True
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.1
    groq_max_tokens: int = 1024

class Config:
    """Main configuration class"""
    
    def __init__(self, env: str = None):
        self.env = env or os.getenv("ENVIRONMENT", "development")
        self.project_root = Path(__file__).parent.parent.parent
        
        # Load YAML config
        config_file = self.project_root / f"configs/{self.env}.yaml"
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        with open(config_file, 'r') as f:
            self._yaml_config = yaml.safe_load(f)
        
        # Load companies
        companies_file = self.project_root / "configs/companies.yaml"
        if not companies_file.exists():
            raise FileNotFoundError(f"Companies file not found: {companies_file}")
            
        with open(companies_file, 'r') as f:
            self._companies_config = yaml.safe_load(f)
        
        # Load sections config (for SEC filings)
        sections_config_file = self.project_root / "configs/sections_config.yaml"
        if sections_config_file.exists():
            with open(sections_config_file, 'r') as f:
                self.sections_config = yaml.safe_load(f)
        else:
            self.sections_config = {}
        
        # Initialize configs
        self.database = self._load_database_config()
        self.pipeline = self._load_pipeline_config()
        self.api = self._load_api_config()
        self.companies = self._companies_config['companies']
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration"""
        db_yaml = self._yaml_config['database']
        return DatabaseConfig(
            postgres_host=os.getenv("POSTGRES_HOST", db_yaml['postgres']['host']),
            postgres_port=int(os.getenv("POSTGRES_PORT", db_yaml['postgres']['port'])),
            postgres_database=os.getenv("POSTGRES_DB", db_yaml['postgres']['database']),
            postgres_user=os.getenv("POSTGRES_USER", "pipeline_user"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
            qdrant_host=os.getenv("QDRANT_HOST", db_yaml['qdrant']['host']),
            qdrant_port=int(os.getenv("QDRANT_PORT", db_yaml['qdrant']['port'])),
            qdrant_collection=db_yaml['qdrant']['collection']
        )
    
    def _load_pipeline_config(self) -> PipelineConfig:
        """Load pipeline configuration"""
        pipeline_yaml = self._yaml_config['pipeline']
        return PipelineConfig(
            chunk_size=int(os.getenv("CHUNK_SIZE", pipeline_yaml['chunk_size'])),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", pipeline_yaml['chunk_overlap'])),
            batch_size=int(os.getenv("BATCH_SIZE", pipeline_yaml['batch_size'])),
            embedding_model=os.getenv("EMBEDDING_MODEL", pipeline_yaml['embedding_model'])
        )
    
    def _load_api_config(self) -> APIConfig:
        """Load API configuration"""
        api_yaml = self._yaml_config['apis']
        sec_config = api_yaml.get('sec', {})
        groq_config = api_yaml.get('groq', {})
        
        return APIConfig(
            news_api_key=os.getenv("NEWS_API_KEY", ""),
            sec_api_key=os.getenv("SEC_API_KEY", ""),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            sec_rate_limit=sec_config.get('rate_limit', 10),
            sec_user_agent=sec_config.get('user_agent', 'your-email@example.com'),
            sec_fetch_start_date=sec_config.get('fetch_start_date'),
            sec_fetch_end_date=sec_config.get('fetch_end_date'),
            sec_max_results_per_query=sec_config.get('max_results_per_query', 50),
            sec_fetch_all_pages=sec_config.get('fetch_all_pages', True),
            groq_model=groq_config.get('model', 'llama-3.1-8b-instant'),
            groq_temperature=float(groq_config.get('temperature', 0.1)),
            groq_max_tokens=int(groq_config.get('max_tokens', 500))
        )
    
    def get_company_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Get company info by ticker"""
        for company in self.companies:
            if company['ticker'] == ticker:
                return company
        return None
    
    def get_postgres_uri(self) -> str:
        """Get PostgreSQL connection URI"""
        return (f"postgresql://{self.database.postgres_user}:"
                f"{self.database.postgres_password}@"
                f"{self.database.postgres_host}:"
                f"{self.database.postgres_port}/"
                f"{self.database.postgres_database}")

# Global config instance
config = Config()