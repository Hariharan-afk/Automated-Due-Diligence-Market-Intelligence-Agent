"""
Retrieval Enhancer

Applies coverage-based boosts during RAG retrieval to ensure
fair representation of companies with sparse data coverage.
"""

from typing import List, Dict, Any, Tuple
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.bias.boost_manager import BoostConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class RetrievalEnhancer:
    """
    Enhances retrieval scores to address coverage bias
    
    Applies adaptive boosting based on:
    - Company size/coverage classification
    - Data source type
    - Quality metrics
    """
    
    def __init__(self, boost_config_path: Path):
        """
        Initialize retrieval enhancer
        
        Args:
            boost_config_path: Path to boost configuration file
        """
        self.boost_manager = BoostConfigManager(boost_config_path)
        
        logger.info("RetrievalEnhancer initialized")
    
    def enhance_scores(
        self,
        results: List[Dict[str, Any]],
        score_key: str = 'score',
        boost_strategy: str = 'additive'
    ) -> List[Dict[str, Any]]:
        """
        Apply coverage boosts to retrieval results
        
        Args:
            results: List of retrieval results with metadata
            score_key: Key name for the similarity score
            boost_strategy: 'additive' or 'multiplicative'
        
        Returns:
            Results with enhanced scores
        """
        if not self.boost_manager.is_boost_enabled():
            logger.debug("Boosting disabled, returning original scores")
            return results
        
        enhanced_results = []
        
        for result in results:
            # Extract metadata
            ticker = result.get('ticker') or result.get('metadata', {}).get('ticker')
            source = result.get('data_source') or result.get('metadata', {}).get('data_source')
            original_score = result.get(score_key, 0.0)
            
            if not ticker:
                logger.warning(f"Result missing ticker, skipping boost: {result.get('chunk_id', 'unknown')}")
                enhanced_results.append(result)
                continue
            
            # Get boost factor
            boost = self.boost_manager.get_company_boost(ticker, source)
            
            # Apply boost based on strategy
            if boost_strategy == 'additive':
                enhanced_score = min(original_score + boost, 1.0)  # Cap at 1.0
            elif boost_strategy == 'multiplicative':
                enhanced_score = min(original_score * (1.0 + boost), 1.0)
            else:
                logger.warning(f"Unknown boost strategy: {boost_strategy}, using additive")
                enhanced_score = min(original_score + boost, 1.0)
            
            # Create enhanced result
            enhanced_result = result.copy()
            enhanced_result[score_key] = enhanced_score
            enhanced_result['original_score'] = original_score
            enhanced_result['applied_boost'] = boost
            enhanced_result['boost_strategy'] = boost_strategy
            
            enhanced_results.append(enhanced_result)
        
        # Re-sort by enhanced score if needed
        enhanced_results.sort(key=lambda x: x[score_key], reverse=True)
        
        logger.debug(f"Enhanced {len(results)} results (boosting enabled)")
        
        return enhanced_results
    
    def analyze_boost_impact(
        self,
        original_results: List[Dict[str, Any]],
        enhanced_results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze the impact of boosting on retrieval results
        
        Args:
            original_results: Results before boosting
            enhanced_results: Results after boosting
            top_k: Number of top results to analyze
        
        Returns:
            Analysis dict with statistics
        """
        # Get top-k for each
        orig_top_k = [r.get('chunk_id') for r in original_results[:top_k]]
        enh_top_k = [r.get('chunk_id') for r in enhanced_results[:top_k]]
        
        # Calculate changes
        unchanged = len(set(orig_top_k) & set(enh_top_k))
        new_entries = len(set(enh_top_k) - set(orig_top_k))
        dropped_entries = len(set(orig_top_k) - set(enh_top_k))
        
        # Count companies in top-k
        orig_companies = set(r.get('ticker') for r in original_results[:top_k] if r.get('ticker'))
        enh_companies = set(r.get('ticker') for r in enhanced_results[:top_k] if r.get('ticker'))
        
        # Measure diversity improvement
        diversity_improvement = len(enh_companies) - len(orig_companies)
        
        # Get classification distribution in top-k
        enh_classifications = {}
        for result in enhanced_results[:top_k]:
            ticker = result.get('ticker')
            if ticker:
                classification = self.boost_manager.get_company_classification(ticker)
                enh_classifications[classification] = enh_classifications.get(classification, 0) + 1
        
        analysis = {
            'top_k': top_k,
            'unchanged_results': unchanged,
            'new_results': new_entries,
            'dropped_results': dropped_entries,
            'original_company_count': len(orig_companies),
            'enhanced_company_count': len(enh_companies),
            'diversity_improvement': diversity_improvement,
            'classification_distribution': enh_classifications,
            'avg_boost_applied': sum(r.get('applied_boost', 0) for r in enhanced_results[:top_k]) / top_k
        }
        
        return analysis
    
    def get_boost_for_chunk(
        self,
        chunk_metadata: Dict[str, Any]
    ) -> float:
        """
        Get boost factor for a specific chunk
        
        Args:
            chunk_metadata: Chunk metadata with ticker and source
        
        Returns:
            Boost factor
        """
        ticker = chunk_metadata.get('ticker')
        source = chunk_metadata.get('data_source')
        
        if not ticker:
            return 0.0
        
        return self.boost_manager.get_company_boost(ticker, source)
    
    def enable_boosting(self):
        """Enable coverage-based boosting"""
        self.boost_manager.set_global_setting('boost_enabled', True)
        logger.info("Coverage boosting enabled")
    
    def disable_boosting(self):
        """Disable coverage-based boosting"""
        self.boost_manager.set_global_setting('boost_enabled', False)
        logger.info("Coverage boosting disabled")
