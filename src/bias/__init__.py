"""
Bias Mitigation Module

Provides tools to track, analyze, and mitigate data coverage bias
in the Due Diligence pipeline.

Components:
- CoverageTracker: Monitor per-company data metrics
- BaselineCalculator: Calculate baselines and classify companies
- BoostConfigManager: Manage boost configurations
- RetrievalEnhancer: Apply boosts during RAG retrieval
"""

from .coverage_tracker import CoverageTracker
from .baseline_calculator import BaselineCalculator
from .boost_manager import BoostConfigManager
from .retrieval_enhancer import RetrievalEnhancer

__all__ = [
    'CoverageTracker',
    'BaselineCalculator',
    'BoostConfigManager',
    'RetrievalEnhancer'
]
