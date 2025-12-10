"""
Boost Configuration Manager

Manages and stores boost factors for each company based on
their coverage classification.
"""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BoostConfigManager:
    """
    Manages boost configuration for fair retrieval
    
    Stores:
    - Company classifications (small/medium/large)
    - Boost factors per company
    - Source-specific boost adjustments
    """
    
    def __init__(self, config_path: Path):
        """
        Initialize boost configuration manager
        
        Args:
            config_path: Path to store boost configuration JSON
        """
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or initialize
        self.config = self._load_config()
        
        logger.info(f"BoostConfigManager initialized: {len(self.config.get('companies', {}))} companies configured")
    
    def _load_config(self) -> Dict:
        """Load existing boost configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        
        return {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'global_settings': {
                'boost_enabled': True,
                'quality_adjustment':True,
                'max_boost': 0.3
            },
            'companies': {}
        }
    
    def _save_config(self):
        """Save boost configuration to storage"""
        self.config['last_updated'] = datetime.now().isoformat()
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        logger.debug(f"Saved boost config for {len(self.config['companies'])} companies")
    
    def set_company_boost(
        self,
        ticker: str,
        classification: str,
        coverage_ratio: float,
        base_boost: float,
        source_boosts: Dict[str, float] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Set boost configuration for a company
        
        Args:
            ticker: Company ticker
            classification: 'small', 'medium', or 'large'
            coverage_ratio: Company's coverage relative to baseline
            base_boost: Base boost factor
            source_boosts: Optional dict of boosts per data source
            metadata: Additional metadata (completeness score, etc.)
        """
        self.config['companies'][ticker] = {
            'classification': classification,
            'coverage_ratio': coverage_ratio,
            'base_boost': base_boost,
            'source_boosts': source_boosts or {},
            'metadata': metadata or {},
            'updated_at': datetime.now().isoformat()
        }
        
        self._save_config()
        
        logger.info(
            f"Set boost for {ticker}: {classification} "
            f"(ratio={coverage_ratio:.2f}, boost={base_boost:.3f})"
        )
    
    def get_company_boost(
        self,
        ticker: str,
        source: str = None
    ) -> float:
        """
        Get boost factor for a company
        
        Args:
            ticker: Company ticker
            source: Optional - get source-specific boost
        
        Returns:
            Boost factor (0.0 if company not configured)
        """
        company_config = self.config['companies'].get(ticker)
        
        if not company_config:
            logger.debug(f"No boost config for {ticker}, returning 0.0")
            return 0.0
        
        # Get source-specific boost if requested
        if source and company_config.get('source_boosts'):
            boost = company_config['source_boosts'].get(source)
            if boost is not None:
                return boost
        
        # Return base boost
        return company_config.get('base_boost', 0.0)
    
    def get_company_classification(self, ticker: str) -> str:
        """Get classification for a company"""
        company_config = self.config['companies'].get(ticker)
        return company_config.get('classification', 'medium') if company_config else 'medium'
    
    def is_boost_enabled(self) -> bool:
        """Check if boosting is globally enabled"""
        return self.config['global_settings'].get('boost_enabled', True)
    
    def set_global_setting(self, key: str, value: Any):
        """Update a global setting"""
        self.config['global_settings'][key] = value
        self._save_config()
        logger.info(f"Updated global setting: {key}={value}")
    
    def get_all_boosts(self) -> Dict[str, Dict]:
        """Get boost configurations for all companies"""
        return self.config['companies']
    
    def export_summary(self, output_path: Path):
        """Export human-readable summary of boost configuration"""
        summary = {
            'generated_at': datetime.now().isoformat(),
            'total_companies': len(self.config['companies']),
            'global_settings': self.config['global_settings'],
            'classifications': {
                'small': [],
                'medium': [],
                'large': []
            }
        }
        
        # Group companies by classification
        for ticker, config in self.config['companies'].items():
            classification = config['classification']
            summary['classifications'][classification].append({
                'ticker': ticker,
                'boost': config['base_boost'],
                'coverage_ratio': config['coverage_ratio']
            })
        
        # Add counts
        summary['classification_counts'] = {
            cls: len(companies) for cls, companies in summary['classifications'].items()
        }
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Exported boost summary to {output_path}")
        
        return summary
