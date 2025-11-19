# scripts/validation/run_complete_validation.py
"""
Master Script: Run Complete Model Validation

Runs all validation components:
1. Retrieval evaluation
2. Bias detection
3. Sensitivity analysis
4. MLflow experiment tracking

Usage:
    python scripts/validation/run_complete_validation.py
    python scripts/validation/run_complete_validation.py --alpha 0.6 --track-mlflow
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.researcher_agent import ResearcherAgent
from src.validation.retrieval_evaluator import RetrievalEvaluator
from src.validation.bias_detector import BiasDetector
from src.analysis.sensitivity_analyzer import SensitivityAnalyzer
from src.tracking.experiment_tracker import ExperimentTracker


def main():
    parser = argparse.ArgumentParser(description='Run complete model validation')
    parser.add_argument('--alpha', type=float, default=0.5, help='Hybrid search weight')
    parser.add_argument('--top-k', type=int, default=5, help='Number of results')
    parser.add_argument('--ground-truth', default='data/validation/ground_truth.json', 
                       help='Path to ground truth file')
    parser.add_argument('--track-mlflow', action='store_true', help='Log to MLflow')
    parser.add_argument('--run-sensitivity', action='store_true', help='Run sensitivity analysis')
    parser.add_argument('--output-dir', default='results/validation', help='Output directory')
    
    args = parser.parse_args()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*80)
    print("🎯 RUNNING COMPLETE MODEL VALIDATION")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Alpha: {args.alpha}")
    print(f"  Top-K: {args.top_k}")
    print(f"  Ground Truth: {args.ground_truth}")
    print(f"  MLflow Tracking: {'Enabled' if args.track_mlflow else 'Disabled'}")
    print(f"  Output Directory: {output_dir}\n")
    
    # ========== STEP 1: Initialize Components ==========
    print("\n" + "="*80)
    print("STEP 1: Initializing Components")
    print("="*80 + "\n")
    
    # Initialize agent
    agent = ResearcherAgent(
        qdrant_host='localhost',
        alpha=args.alpha,
        top_k=args.top_k
    )
    
    print("Loading corpus from Qdrant...")
    agent.load_corpus()
    
    # Initialize evaluator
    evaluator = RetrievalEvaluator(args.ground_truth)
    
    # Initialize bias detector
    detector = BiasDetector(evaluator)
    
    # Initialize MLflow tracker (if enabled)
    if args.track_mlflow:
        tracker = ExperimentTracker(experiment_name="retrieval_validation")
    
    # ========== STEP 2: Retrieval Evaluation ==========
    print("\n" + "="*80)
    print("STEP 2: Retrieval Quality Evaluation")
    print("="*80 + "\n")
    
    if args.track_mlflow:
        # Log to MLflow
        run_id = tracker.log_retrieval_experiment(
            agent,
            evaluator,
            run_name=f"validation_{timestamp}",
            tags={'validation_type': 'complete', 'timestamp': timestamp}
        )
        print(f"✓ Logged to MLflow (Run ID: {run_id})")
    else:
        # Just evaluate
        eval_results = evaluator.evaluate_all(agent, k_values=[1, 3, 5, 10])
        
        # Save results
        evaluator.save_results(
            eval_results,
            output_dir / 'retrieval_metrics.json'
        )
        
        evaluator.generate_html_report(
            eval_results,
            output_dir / 'retrieval_report.html'
        )
        
        print(f"✓ Results saved to {output_dir}")
    
    # ========== STEP 3: Bias Detection ==========
    print("\n" + "="*80)
    print("STEP 3: Bias Detection Analysis")
    print("="*80 + "\n")
    
    bias_results = detector.run_complete_bias_analysis(agent)
    
    # Save bias results
    detector.save_bias_report(
        bias_results,
        output_dir / 'bias_analysis.json'
    )
    
    detector.generate_bias_html_report(
        bias_results,
        output_dir / 'bias_report.html'
    )
    
    # Log to MLflow if enabled
    if args.track_mlflow:
        tracker.log_bias_analysis(agent, detector, run_id=run_id)
    
    # ========== STEP 4: Sensitivity Analysis (Optional) ==========
    if args.run_sensitivity:
        print("\n" + "="*80)
        print("STEP 4: Sensitivity Analysis")
        print("="*80 + "\n")
        
        analyzer = SensitivityAnalyzer(evaluator)
        
        # Alpha sensitivity
        alpha_results = analyzer.analyze_alpha_sensitivity()
        
        # Top-K sensitivity
        topk_results = analyzer.analyze_top_k_sensitivity(alpha=args.alpha)
        
        # Generate plots
        sensitivity_dir = output_dir / 'sensitivity_analysis'
        analyzer.generate_sensitivity_plots(
            alpha_results,
            topk_results,
            sensitivity_dir
        )
        
        analyzer.generate_sensitivity_report(
            alpha_results,
            topk_results,
            sensitivity_dir / 'sensitivity_report.html'
        )
        
        print(f"✓ Sensitivity analysis saved to {sensitivity_dir}")
    
    # ========== FINAL SUMMARY ==========
    print("\n" + "="*80)
    print("✅ VALIDATION COMPLETE")
    print("="*80 + "\n")
    
    print("Generated Reports:")
    print(f"  1. Retrieval Metrics: {output_dir / 'retrieval_report.html'}")
    print(f"  2. Bias Analysis:     {output_dir / 'bias_report.html'}")
    
    if args.run_sensitivity:
        print(f"  3. Sensitivity:       {output_dir / 'sensitivity_analysis/sensitivity_report.html'}")
    
    if args.track_mlflow:
        print(f"\n📊 View in MLflow UI:")
        print(f"   Run: mlflow ui")
        print(f"   Open: http://localhost:5000")
    
    # Decision gates
    print("\n" + "="*80)
    print("🚦 VALIDATION GATES")
    print("="*80 + "\n")
    
    if args.track_mlflow:
        eval_results = evaluator.evaluate_all(agent, k_values=[5])
    
    # Gate 1: Minimum performance
    ndcg5 = eval_results['overall']['ndcg@5']
    precision5 = eval_results['overall']['precision@5']
    
    gates_passed = []
    gates_failed = []
    
    if ndcg5 >= 0.6:
        gates_passed.append(f"✅ Performance Gate: nDCG@5={ndcg5:.3f} (threshold: 0.6)")
    else:
        gates_failed.append(f"❌ Performance Gate: nDCG@5={ndcg5:.3f} < 0.6")
    
    # Gate 2: No high-severity bias
    high_bias = sum(1 for d in bias_results['all_disparities'] if d['severity'] == 'high')
    
    if high_bias == 0:
        gates_passed.append(f"✅ Bias Gate: No high-severity bias detected")
    else:
        gates_failed.append(f"❌ Bias Gate: {high_bias} high-severity bias(es) detected")
    
    # Print gates
    for gate in gates_passed:
        print(gate)
    
    for gate in gates_failed:
        print(gate)
    
    # Final decision
    if gates_failed:
        print("\n🔴 VALIDATION FAILED - Do not deploy")
        print("\nAction Required:")
        for gate in gates_failed:
            print(f"  - {gate}")
        return 1
    else:
        print("\n🟢 VALIDATION PASSED - Ready for deployment")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)