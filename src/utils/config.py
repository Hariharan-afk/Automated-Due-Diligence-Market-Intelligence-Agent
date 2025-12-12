# src/utils/config.py
"""Configuration loader for the data pipeline"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file in project root
project_root = Path(__file__).parent.parent.parent.parent  # Go up to project root
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path)


print(f"📁 Loading .env from: {dotenv_path}")
print(f"🔑 SEC_API_KEY exists: {'SEC_API_KEY' in os.environ}")

@dataclass
class Company:
    """Company information"""
    ticker: str
    name: str
    cik: str

@dataclass
class APIConfig:
    """API configuration"""
    groq_api_key: str = None
    news_api_key: str = None
    sec_api_key: str = None
    
    def __post_init__(self):
        # Load from environment if not provided
        if not self.groq_api_key:
            self.groq_api_key = os.getenv('GROQ_API_KEY', '')
        if not self.news_api_key:
            self.news_api_key = os.getenv('NEWS_API_KEY', '')
        if not self.sec_api_key:
            self.sec_api_key = os.getenv('SEC_API_KEY', '')


class Config:
    """
    Central configuration manager
    
    Loads all YAML configs and provides easy access
    """
    
    def __init__(self, config_dir: str = None):
        """
        Initialize config loader
        
        Args:
            config_dir: Path to configs directory (defaults to ../configs)
        """
        if config_dir is None:
            # Default: Data_Pipeline/configs
            current_file = Path(__file__)
            self.config_dir = current_file.parent.parent.parent / 'configs'
        else:
            self.config_dir = Path(config_dir)
        
        # Load all configs
        self._load_all_configs()
    
    def _load_all_configs(self):
        """Load all configuration files"""
        # Load companies
        self.companies = self._load_companies()
        
        # Load SEC config
        self.sec_config = self._load_yaml('sec_config.yaml')
        
        # Load database config
        self.db_config = self._load_yaml('database_config.yaml')
        
        # Load API keys
        self.api = APIConfig()
        
        print(f"✅ Loaded config from: {self.config_dir}")
        print(f"   - {len(self.companies)} companies")
        print(f"   - SEC sections: {len(self.sec_config.get('sec_filing_sections', {}))} filing types")
    
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML file"""
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            print(f"⚠️  Warning: {filename} not found")
            return {}
        
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def _load_companies(self) -> List[Company]:
        """Load company list"""
        data = self._load_yaml('companies.yaml')
        
        companies = []
        for comp in data.get('companies', []):
            companies.append(Company(
                ticker=comp['ticker'],
                name=comp['name'],
                cik=comp['cik']
            ))
        
        return companies
    
    def get_company_by_ticker(self, ticker: str) -> Optional[Company]:
        """Get company info by ticker"""
        for company in self.companies:
            if company.ticker == ticker:
                return company
        return None
    
    def get_company_by_cik(self, cik: str) -> Optional[Company]:
        """Get company info by CIK"""
        # Normalize CIK (remove leading zeros)
        cik_normalized = cik.lstrip('0')
        
        for company in self.companies:
            if company.cik.lstrip('0') == cik_normalized:
                return company
        return None
    
    def get_all_tickers(self) -> List[str]:
        """Get list of all tickers"""
        return [c.ticker for c in self.companies]
    
    def get_sec_sections(self, filing_type: str) -> Dict[str, str]:
        """
        Get sections to fetch for a filing type
        
        Args:
            filing_type: '10-K' or '10-Q'
        
        Returns:
            Dict mapping section codes to section names
        """
        sections = self.sec_config.get('sec_filing_sections', {}).get(filing_type, {})
        return sections
    
    def get_sec_date_range(self) -> tuple:
        """Get SEC filing date range"""
        start_date = self.sec_config.get('fetch_start_date', '2023-01-01')
        end_date = self.sec_config.get('fetch_end_date')  # None = today
        return start_date, end_date
    
    @property
    def postgres_config(self) -> Dict[str, Any]:
        """Get PostgreSQL configuration"""
        return self.db_config.get('postgresql', {})
    
    @property
    def qdrant_config(self) -> Dict[str, Any]:
        """Get Qdrant configuration"""
        return self.db_config.get('qdrant', {})
    
    @property
    def embedding_config(self) -> Dict[str, Any]:
        """Get embedding configuration"""
        return self.db_config.get('embedding', {})
    
    @property
    def llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration"""
        llm_conf = self.db_config.get('llm', {})
        
        # Add API key from environment/APIConfig
        llm_conf['api_key'] = self.api.groq_api_key
        
        return llm_conf


# Global config instance
config = Config()


if __name__ == '__main__':
    # Test config loading
    print("\n=== Testing Config Loader ===\n")
    
    print(f"Companies: {config.get_all_tickers()}")
    print(f"\nApple: {config.get_company_by_ticker('AAPL')}")
    print(f"\n10-K Sections: {config.get_sec_sections('10-K')}")
    print(f"\nPostgreSQL: {config.postgres_config}")
    print(f"\nQdrant: {config.qdrant_config}")