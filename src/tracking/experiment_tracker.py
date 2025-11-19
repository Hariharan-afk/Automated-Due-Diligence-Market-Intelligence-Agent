# src/tracking/experiment_tracker.py
"""
MLflow Experiment Tracking for Retrieval System

Tracks:
- Different alpha values (hybrid search weights)
- Different embedding models
- Chunking strategies
- Performance metrics
- Bias analysis results
"""

import mlflow
import mlflow.pyfunc
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.researcher_agent import ResearcherAgent
from src.validation.retrieval_evaluator import RetrievalEvaluator
from src.validation.bias_detector import BiasDetector
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ExperimentTracker:
    """
    Track retrieval experiments with MLflow
    
    Automatically logs:
    - Parameters (alpha, model, chunk_size)
    - Metrics (precision, recall, nDCG)
    - Artifacts (bias reports, visualizations)
    - Model versions
    """
    
    def __init__(
        self,
        experiment_name: str = "retrieval_optimization",
        tracking_uri: str = None
    ):
        """
        Initialize experiment tracker
        
        Args:
            experiment_name: MLflow experiment name
            tracking_uri: MLflow tracking server (default: local)
        """
        # Set tracking URI
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        else:
            # Use local directory
            mlflow.set_tracking_uri("file:./mlruns")
        
        # Create/set experiment
        mlflow.set_experiment(experiment_name)
        
        self.experiment_name = experiment_name
        
        logger.info(f"✓ MLflow tracker initialized: {experiment_name}")
        logger.info(f"  Tracking URI: {mlflow.get_tracking_uri()}")
    
    def log_retrieval_experiment(
        self,
        agent: ResearcherAgent,
        evaluator: RetrievalEvaluator,
        run_name: str = None,
        tags: Dict[str, str] = None
    ) -> str:
        """
        Run and log a complete retrieval experiment
        
        Args:
            agent: ResearcherAgent configured with specific params
            evaluator: RetrievalEvaluator with ground truth
            run_name: Name for this run
            tags: Additional tags
        
        Returns:
            MLflow run ID
        """
        run_name = run_name or f"alpha_{agent.alpha}_k_{agent.top_k}"
        
        with mlflow.start_run(run_name=run_name) as run:
            logger.info(f"\n🚀 Starting MLflow run: {run_name}")
            logger.info(f"   Run ID: {run.info.run_id}\n")
            
            # Log parameters
            mlflow.log_param("alpha", agent.alpha)
            mlflow.log_param("top_k", agent.top_k)
            mlflow.log_param("embedding_model", str(agent.embedding_model))
            mlflow.log_param("collection_name", agent.collection_name)
            mlflow.log_param("qdrant_host", agent.qdrant_host)
            
            # Log tags
            if tags:
                mlflow.set_tags(tags)
            
            mlflow.set_tag("timestamp", datetime.now().isoformat())
            
            # Run evaluation
            logger.info("Running retrieval evaluation...")
            eval_results = evaluator.evaluate_all(agent, k_values=[1, 3, 5, 10])
            
            # Log metrics (replace @ with _ for MLflow compatibility)
            for metric_name, value in eval_results['overall'].items():
                # MLflow doesn't allow @ in metric names
                safe_metric_name = metric_name.replace('@', '_at_')
                mlflow.log_metric(safe_metric_name, value)
            
            # Log per-category metrics
            for category, metrics in eval_results.get('by_category', {}).items():
                for metric_name, value in metrics.items():
                    safe_metric_name = metric_name.replace('@', '_at_')
                    mlflow.log_metric(f"{category}_{safe_metric_name}", value)
            
            # Save and log evaluation report
            report_path = Path(f"temp_reports/eval_{run.info.run_id}.json")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            evaluator.save_results(eval_results, str(report_path))
            mlflow.log_artifact(str(report_path), "evaluation_reports")
            
            # Generate and log HTML report
            html_path = Path(f"temp_reports/eval_{run.info.run_id}.html")
            evaluator.generate_html_report(eval_results, str(html_path))
            mlflow.log_artifact(str(html_path), "evaluation_reports")
            
            logger.info(f"✓ Logged {len(eval_results['overall'])} metrics")
            logger.info(f"✓ Run ID: {run.info.run_id}\n")
            
            return run.info.run_id
    
    def log_bias_analysis(
        self,
        agent: ResearcherAgent,
        bias_detector: BiasDetector,
        run_id: str = None
    ):
        """
        Log bias detection results to existing or new run
        
        Args:
            agent: ResearcherAgent instance
            bias_detector: BiasDetector instance
            run_id: Existing run ID (or None for new run)
        """
        if run_id:
            # Add to existing run
            with mlflow.start_run(run_id=run_id):
                self._log_bias_metrics(agent, bias_detector)
        else:
            # Create new run
            with mlflow.start_run(run_name=f"bias_analysis_{agent.alpha}"):
                mlflow.log_param("alpha", agent.alpha)
                self._log_bias_metrics(agent, bias_detector)
    
    def _log_bias_metrics(
        self,
        agent: ResearcherAgent,
        bias_detector: BiasDetector
    ):
        """Internal method to log bias metrics"""
        logger.info("Running bias detection...")
        
        bias_results = bias_detector.run_complete_bias_analysis(agent)
        
        # Log bias flags
        mlflow.log_metric("bias_detected", 1 if bias_results['overall_bias_detected'] else 0)
        mlflow.log_metric("total_disparities", bias_results['total_disparities'])
        
        # Log disparity counts by severity
        high_severity = sum(1 for d in bias_results['all_disparities'] if d['severity'] == 'high')
        medium_severity = sum(1 for d in bias_results['all_disparities'] if d['severity'] == 'medium')
        
        mlflow.log_metric("high_severity_disparities", high_severity)
        mlflow.log_metric("medium_severity_disparities", medium_severity)
        
        # Save and log bias report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = Path(f"temp_reports/bias_{timestamp}.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        bias_detector.save_bias_report(bias_results, str(report_path))
        mlflow.log_artifact(str(report_path), "bias_reports")
        
        # Generate and log HTML
        html_path = Path(f"temp_reports/bias_{timestamp}.html")
        bias_detector.generate_bias_html_report(bias_results, str(html_path))
        mlflow.log_artifact(str(html_path), "bias_reports")
        
        logger.info(f"✓ Logged bias analysis (disparities: {bias_results['total_disparities']})")
    
    def run_ablation_study(
        self,
        evaluator: RetrievalEvaluator,
        alpha_values: List[float] = None,
        top_k_values: List[int] = None
    ) -> Dict[str, Any]:
        """
        Run ablation study testing different configurations
        
        Args:
            evaluator: RetrievalEvaluator instance
            alpha_values: List of alpha values to test
            top_k_values: List of top-K values to test
        
        Returns:
            Summary of all experiments
        """
        alpha_values = alpha_values or [0.0, 0.3, 0.5, 0.7, 1.0]
        top_k_values = top_k_values or [5]
        
        logger.info("\n" + "="*80)
        logger.info("🔬 STARTING ABLATION STUDY")
        logger.info("="*80 + "\n")
        logger.info(f"Testing {len(alpha_values)} alpha values: {alpha_values}")
        logger.info(f"Testing {len(top_k_values)} top-K values: {top_k_values}\n")
        
        all_results = []
        
        for alpha in alpha_values:
            for top_k in top_k_values:
                logger.info(f"\n{'='*80}")
                logger.info(f"Experiment: alpha={alpha}, top_k={top_k}")
                logger.info(f"{'='*80}\n")
                
                # Create agent with these params
                agent = ResearcherAgent(
                    qdrant_host='localhost',
                    alpha=alpha,
                    top_k=top_k
                )
                
                # Load corpus
                agent.load_corpus()
                
                # Run and log experiment
                run_id = self.log_retrieval_experiment(
                    agent,
                    evaluator,
                    run_name=f"alpha_{alpha}_topk_{top_k}",
                    tags={
                        'experiment_type': 'ablation',
                        'alpha': str(alpha),
                        'top_k': str(top_k)
                    }
                )
                
                # Evaluate
                eval_results = evaluator.evaluate_all(agent, k_values=[5])
                
                all_results.append({
                    'run_id': run_id,
                    'alpha': alpha,
                    'top_k': top_k,
                    'precision@5': eval_results['overall']['precision@5'],
                    'recall@5': eval_results['overall']['recall@5'],
                    'ndcg@5': eval_results['overall']['ndcg@5'],
                    'mrr': eval_results['overall']['mrr']
                })
        
        # Find best configuration
        best_result = max(all_results, key=lambda x: x['ndcg@5'])
        
        logger.info("\n" + "="*80)
        logger.info("🏆 BEST CONFIGURATION")
        logger.info("="*80 + "\n")
        logger.info(f"  Alpha: {best_result['alpha']}")
        logger.info(f"  Top-K: {best_result['top_k']}")
        logger.info(f"  nDCG@5: {best_result['ndcg@5']:.3f}")
        logger.info(f"  Precision@5: {best_result['precision@5']:.3f}")
        logger.info(f"  Recall@5: {best_result['recall@5']:.3f}")
        logger.info(f"\n  MLflow Run ID: {best_result['run_id']}")
        logger.info("\n" + "="*80 + "\n")
        
        return {
            'all_experiments': all_results,
            'best_config': best_result
        }
    
    def compare_embedding_models(
        self,
        evaluator: RetrievalEvaluator,
        models: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare different embedding models
        
        Args:
            evaluator: RetrievalEvaluator instance
            models: List of model names to test
        
        Returns:
            Comparison results
        """
        models = models or [
            "sentence-transformers/all-mpnet-base-v2",  # 768-dim (current)
            "sentence-transformers/all-MiniLM-L6-v2",   # 384-dim (faster)
            "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"  # Multilingual
        ]
        
        logger.info("\n" + "="*80)
        logger.info("🔬 COMPARING EMBEDDING MODELS")
        logger.info("="*80 + "\n")
        
        results = []
        
        for model_name in models:
            logger.info(f"\nTesting: {model_name}")
            logger.info("-" * 80)
            
            try:
                agent = ResearcherAgent(
                    qdrant_host='localhost',
                    embedding_model=model_name,
                    alpha=0.5,
                    top_k=5
                )
                
                agent.load_corpus()
                
                run_id = self.log_retrieval_experiment(
                    agent,
                    evaluator,
                    run_name=f"model_{model_name.split('/')[-1]}",
                    tags={'experiment_type': 'model_comparison'}
                )
                
                eval_results = evaluator.evaluate_all(agent, k_values=[5])
                
                results.append({
                    'model': model_name,
                    'run_id': run_id,
                    'metrics': eval_results['overall']
                })
                
                logger.info(f"✓ Completed: {model_name}")
                
            except Exception as e:
                logger.error(f"❌ Failed for {model_name}: {e}")
                continue
        
        return {'model_comparisons': results}


# ==================== STANDALONE TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING MLFLOW EXPERIMENT TRACKER")
    print("="*80 + "\n")
    
    # Initialize tracker
    tracker = ExperimentTracker(
        experiment_name="retrieval_optimization"
    )
    
    # Initialize evaluator
    evaluator = RetrievalEvaluator(
        ground_truth_file='data/validation/ground_truth.json'
    )
    
    # Run ablation study
    print("\n1. Running Ablation Study...")
    print("-" * 80)
    
    ablation_results = tracker.run_ablation_study(
        evaluator,
        alpha_values=[0.0, 0.3, 0.5, 0.7, 1.0],
        top_k_values=[5]
    )
    
    print(f"\n✅ Ablation study complete!")
    print(f"   Tested {len(ablation_results['all_experiments'])} configurations")
    print(f"   Best alpha: {ablation_results['best_config']['alpha']}")
    print(f"   Best nDCG@5: {ablation_results['best_config']['ndcg@5']:.3f}")
    
    print("\n" + "="*80)
    print("📊 View results in MLflow UI:")
    print("   cd to project root, then run: mlflow ui")
    print("   Open: http://localhost:5000")
    print("="*80 + "\n")