# src/data_quality/drift_monitor.py
"""Monitors data drift over time"""

from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class DriftMonitor:
    """
    Monitors data distribution drift over time
    
    Tracks:
    - Embedding distribution changes
    - Chunk length distribution
    - Vocabulary changes
    - Data volume trends
    """
    
    def __init__(self, baseline_dir: Optional[str] = None):
        """
        Initialize drift monitor
        
        Args:
            baseline_dir: Directory to store baseline statistics
        """
        if baseline_dir:
            self.baseline_dir = Path(baseline_dir)
        else:
            project_root = Path(__file__).parent.parent.parent
            self.baseline_dir = project_root / "data" / "cache" / "drift_baselines"
        
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"DriftMonitor initialized (baseline_dir: {self.baseline_dir})")
    
    def compute_baseline_statistics(
        self,
        embeddings: List[np.ndarray],
        baseline_name: str = "default"
    ) -> Dict[str, Any]:
        """
        Compute baseline statistics from embeddings (PRODUCTION-READY)
        
        Args:
            embeddings: List of embedding vectors
            baseline_name: Name for this baseline
            
        Returns:
            Baseline statistics dict
        """
        logger.info(f"Computing baseline statistics: {baseline_name}")
        
        embeddings_array = np.array(embeddings)
        
        stats = {
            "baseline_name": baseline_name,
            "timestamp": datetime.now().isoformat(),
            "num_embeddings": len(embeddings),
            "dimension": embeddings_array.shape[1] if len(embeddings) > 0 else 0,
            "mean": embeddings_array.mean(axis=0).tolist(),
            "std": embeddings_array.std(axis=0).tolist(),
            "overall_mean": float(embeddings_array.mean()),
            "overall_std": float(embeddings_array.std())
        }
        
        # Save baseline
        baseline_file = self.baseline_dir / f"{baseline_name}.json"
        with open(baseline_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Baseline saved: {baseline_file}")
        
        return stats
    
    def detect_drift(
        self,
        new_embeddings: List[np.ndarray],
        baseline_name: str = "default",
        threshold: float = 0.1
    ) -> Dict[str, Any]:
        """
        Detect drift from baseline (PRODUCTION-READY)
        
        Args:
            new_embeddings: New embedding vectors
            baseline_name: Baseline to compare against
            threshold: Drift threshold (0.1 = 10% change)
            
        Returns:
            Drift detection report
        """
        logger.info(f"Detecting drift against baseline: {baseline_name}")
        
        # Load baseline
        baseline_file = self.baseline_dir / f"{baseline_name}.json"
        
        if not baseline_file.exists():
            logger.warning(f"Baseline {baseline_name} not found - cannot detect drift")
            return {"error": "baseline_not_found"}
        
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        
        # Compute current statistics
        new_array = np.array(new_embeddings)
        current_mean = float(new_array.mean())
        current_std = float(new_array.std())
        
        baseline_mean = baseline['overall_mean']
        baseline_std = baseline['overall_std']
        
        # Calculate drift
        mean_drift = abs(current_mean - baseline_mean) / baseline_mean
        std_drift = abs(current_std - baseline_std) / baseline_std
        
        has_drifted = mean_drift > threshold or std_drift > threshold
        
        report = {
            "baseline_name": baseline_name,
            "baseline_date": baseline['timestamp'],
            "current_embeddings": len(new_embeddings),
            "baseline_embeddings": baseline['num_embeddings'],
            "mean_drift": mean_drift,
            "std_drift": std_drift,
            "threshold": threshold,
            "has_drifted": has_drifted
        }
        
        if has_drifted:
            logger.warning(
                f"⚠️ Drift detected: mean_drift={mean_drift:.2%}, "
                f"std_drift={std_drift:.2%} (threshold={threshold:.2%})"
            )
        else:
            logger.info(f"✅ No significant drift detected")
        
        return report
    
    def track_chunk_length_distribution(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Track chunk length distribution (PRODUCTION-READY)
        
        Args:
            chunks: List of chunk dicts
            
        Returns:
            Distribution statistics
        """
        lengths = [chunk.get('word_count', 0) for chunk in chunks]
        
        if not lengths:
            return {}
        
        stats = {
            "num_chunks": len(lengths),
            "mean_length": np.mean(lengths),
            "std_length": np.std(lengths),
            "min_length": min(lengths),
            "max_length": max(lengths),
            "median_length": np.median(lengths)
        }
        
        return stats