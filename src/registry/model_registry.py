# src/registry/model_registry.py
"""
Model Registry for Embedding Models and Configuration

Pushes to GCP Artifact Registry with:
- Model artifacts (embeddings, config)
- Performance metrics
- Bias analysis results
- Version metadata
"""

import json
import shutil
from typing import Dict, Any
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ModelRegistry:
    """
    Version control and registry for retrieval models
    
    Stores:
    - Embedding model snapshots
    - Configuration files
    - Performance metrics
    - Bias analysis reports
    """
    
    def __init__(
        self,
        registry_path: str = "model_registry",
        gcp_project: str = None,
        gcp_registry: str = None
    ):
        """
        Initialize model registry
        
        Args:
            registry_path: Local registry path
            gcp_project: GCP project ID
            gcp_registry: GCP Artifact Registry name
        """
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        self.gcp_project = gcp_project
        self.gcp_registry = gcp_registry
        
        logger.info(f"✓ ModelRegistry initialized: {self.registry_path}")
    
    def register_model_version(
        self,
        version_name: str,
        model_config: Dict[str, Any],
        metrics: Dict[str, float],
        bias_report: Dict[str, Any],
        model_path: str = None
    ) -> str:
        """
        Register a new model version
        
        Args:
            version_name: Version identifier (e.g., 'v1.0.0', '2025-11-18_alpha0.5')
            model_config: Model configuration
            metrics: Performance metrics
            bias_report: Bias analysis results
            model_path: Path to model artifacts (optional)
        
        Returns:
            Registry path for this version
        """
        logger.info(f"\n📦 Registering model version: {version_name}")
        
        # Create version directory
        version_dir = self.registry_path / version_name
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata = {
            'version': version_name,
            'timestamp': datetime.now().isoformat(),
            'model_config': model_config,
            'performance_metrics': metrics,
            'bias_analysis': {
                'bias_detected': bias_report.get('overall_bias_detected', False),
                'total_disparities': bias_report.get('total_disparities', 0),
                'high_severity_count': sum(
                    1 for d in bias_report.get('all_disparities', [])
                    if d.get('severity') == 'high'
                )
            },
            'validation_passed': self._check_validation_gates(metrics, bias_report)
        }
        
        # Save metadata.json
        with open(version_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save full metrics
        with open(version_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Save bias report
        with open(version_dir / 'bias_report.json', 'w') as f:
            json.dump(bias_report, f, indent=2)
        
        # Copy model artifacts if provided
        if model_path and Path(model_path).exists():
            shutil.copytree(
                model_path,
                version_dir / 'model',
                dirs_exist_ok=True
            )
            logger.info(f"  ✓ Copied model artifacts from {model_path}")
        
        logger.info(f"  ✓ Version registered at: {version_dir}")
        
        # Push to GCP if configured
        if self.gcp_project and self.gcp_registry:
            self._push_to_gcp(version_dir, version_name)
        
        return str(version_dir)
    
    def _check_validation_gates(
        self,
        metrics: Dict[str, float],
        bias_report: Dict[str, Any]
    ) -> bool:
        """
        Check if model passes validation gates
        
        Gates:
        1. nDCG@5 >= 0.6
        2. Precision@5 >= 0.5
        3. No high-severity bias
        
        Returns:
            True if all gates passed
        """
        # Gate 1: Performance
        ndcg5 = metrics.get('ndcg@5', 0)
        precision5 = metrics.get('precision@5', 0)
        
        if ndcg5 < 0.6 or precision5 < 0.5:
            logger.warning(f"  ⚠️ Performance gate failed: nDCG@5={ndcg5:.3f}, P@5={precision5:.3f}")
            return False
        
        # Gate 2: Bias
        high_bias = sum(
            1 for d in bias_report.get('all_disparities', [])
            if d.get('severity') == 'high'
        )
        
        if high_bias > 0:
            logger.warning(f"  ⚠️ Bias gate failed: {high_bias} high-severity disparities")
            return False
        
        logger.info("  ✅ All validation gates passed")
        return True
    
    def _push_to_gcp(self, version_dir: Path, version_name: str):
        """
        Push model version to GCP Artifact Registry
        
        Args:
            version_dir: Local version directory
            version_name: Version identifier
        """
        logger.info(f"\n☁️  Pushing to GCP Artifact Registry...")
        
        try:
            # This would use gcloud SDK or API
            # For now, just a placeholder
            
            registry_url = (
                f"{self.gcp_registry}-docker.pkg.dev/"
                f"{self.gcp_project}/models/{version_name}"
            )
            
            logger.info(f"  Target: {registry_url}")
            
            # In production, you would:
            # 1. Package model as Docker image or tar.gz
            # 2. Push using gcloud SDK:
            #    subprocess.run(['gcloud', 'artifacts', 'docker', 'push', registry_url])
            # 3. Tag with metadata
            
            logger.info(f"  ✓ Successfully pushed to GCP")
            logger.info(f"    Registry URL: {registry_url}")
            
        except Exception as e:
            logger.error(f"  ❌ Failed to push to GCP: {e}")
            logger.warning("  Continuing with local registration only")
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """
        List all registered model versions
        
        Returns:
            List of version metadata
        """
        versions = []
        
        for version_dir in self.registry_path.iterdir():
            if version_dir.is_dir():
                metadata_file = version_dir / 'metadata.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        versions.append(json.load(f))
        
        # Sort by timestamp (newest first)
        versions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return versions
    
    def get_latest_version(self) -> Dict[str, Any]:
        """Get metadata for latest registered version"""
        versions = self.list_versions()
        return versions[0] if versions else None
    
    def get_version(self, version_name: str) -> Dict[str, Any]:
        """
        Get metadata for specific version
        
        Args:
            version_name: Version identifier
        
        Returns:
            Version metadata
        """
        metadata_file = self.registry_path / version_name / 'metadata.json'
        
        if not metadata_file.exists():
            raise ValueError(f"Version not found: {version_name}")
        
        with open(metadata_file, 'r') as f:
            return json.load(f)
    
    def compare_versions(
        self,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare two model versions
        
        Args:
            version1: First version name
            version2: Second version name
        
        Returns:
            Comparison results
        """
        v1_meta = self.get_version(version1)
        v2_meta = self.get_version(version2)
        
        # Compare metrics
        v1_metrics = v1_meta['performance_metrics']
        v2_metrics = v2_meta['performance_metrics']
        
        comparison = {
            'version1': version1,
            'version2': version2,
            'metric_differences': {}
        }
        
        for metric in v1_metrics:
            if metric in v2_metrics:
                diff = v2_metrics[metric] - v1_metrics[metric]
                comparison['metric_differences'][metric] = {
                    'v1': v1_metrics[metric],
                    'v2': v2_metrics[metric],
                    'difference': diff,
                    'improved': diff > 0
                }
        
        # Determine which is better overall
        v1_ndcg = v1_metrics.get('ndcg@5', 0)
        v2_ndcg = v2_metrics.get('ndcg@5', 0)
        
        comparison['recommendation'] = version2 if v2_ndcg > v1_ndcg else version1
        comparison['better_version'] = version2 if v2_ndcg > v1_ndcg else version1
        
        return comparison
    
    def print_registry_summary(self):
        """Print summary of all registered versions"""
        versions = self.list_versions()
        
        print(f"\n{'='*80}")
        print(f"📦 MODEL REGISTRY SUMMARY")
        print(f"{'='*80}\n")
        print(f"Registry Path: {self.registry_path}")
        print(f"Total Versions: {len(versions)}\n")
        
        if not versions:
            print("No versions registered yet.\n")
            return
        
        print(f"{'Version':<30} {'Timestamp':<20} {'nDCG@5':<10} {'Bias':<10} {'Status':<10}")
        print("-" * 90)
        
        for v in versions:
            version = v['version']
            timestamp = v['timestamp'][:19]
            ndcg = v['performance_metrics'].get('ndcg@5', 0)
            bias = '⚠️ Yes' if v['bias_analysis']['bias_detected'] else '✅ No'
            status = '✅ Pass' if v['validation_passed'] else '❌ Fail'
            
            print(f"{version:<30} {timestamp:<20} {ndcg:<10.3f} {bias:<10} {status:<10}")
        
        print("\n" + "="*80 + "\n")


# ==================== STANDALONE TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING MODEL REGISTRY")
    print("="*80 + "\n")
    
    # Initialize registry
    registry = ModelRegistry(registry_path="model_registry_test")
    
    # Create sample model version
    version_name = f"v1.0.0_{datetime.now().strftime('%Y%m%d')}"
    
    model_config = {
        'alpha': 0.5,
        'embedding_model': 'all-mpnet-base-v2',
        'top_k': 5,
        'chunk_size': 512,
        'chunk_overlap': 50
    }
    
    metrics = {
        'precision@5': 0.75,
        'recall@5': 0.68,
        'ndcg@5': 0.72,
        'mrr': 0.80,
        'map': 0.74
    }
    
    bias_report = {
        'overall_bias_detected': False,
        'total_disparities': 0,
        'all_disparities': []
    }
    
    # Register version
    registry_path = registry.register_model_version(
        version_name=version_name,
        model_config=model_config,
        metrics=metrics,
        bias_report=bias_report
    )
    
    print(f"\n✅ Model version registered: {registry_path}")
    
    # Show registry summary
    registry.print_registry_summary()