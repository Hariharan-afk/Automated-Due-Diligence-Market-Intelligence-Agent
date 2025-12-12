"""
Model_Validation/bias_check.py
Detect performance bias across different data slices (e.g., companies/tickers).

Usage:
    python Model_Validation/bias_check.py
    # or if you're inside validation/ folder:
    python bias_check.py
"""

import sys
sys.path.append('.')  # ensure project root on path

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

# Reuse your existing validation pipeline + dataset
from src.model_validation.run_validation import ValidationPipeline
from src.model_validation.test_dataset import TestDataset
from src.config import BIAS_CONFIG


@dataclass
class GroupStats:
    group_id: str
    num_tests: int
    num_success: int
    avg_overall_score: float
    avg_groundedness: float
    avg_relevancy: float
    avg_relevancy: float
    avg_retrieval_recall: float
    success_rate: float


class NumpyEncoder(json.JSONEncoder):
    """Special json encoder for numpy types"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


class BiasDetector:
    """
    Run validation and compute bias metrics across groups (e.g., per company/ticker).

    Grouping strategy:
      - We group by ticker inferred from query_id prefix (e.g., 'TECH_01' -> 'TECH')
        which maps cleanly to companies in TestDataset.
    """

    def __init__(self, results: Optional[List[Dict]] = None):
        if results is not None:
            # Use already-computed results (e.g., loaded from JSON)
            self.results = results
        else:
            # Run a fresh validation pass
            pipeline = ValidationPipeline()
            self.results = pipeline.run_all_tests(limit=None)

        # Optional: map query_id -> metadata from TestDataset if you want richer slicing
        self.test_cases = {tc["query_id"]: tc for tc in TestDataset().get_test_cases()}

    # ─────────────────────────────────────────────────────────────
    # Grouping & stats
    # ─────────────────────────────────────────────────────────────

    def _get_group_id(self, result: Dict) -> str:
        """
        Define the 'group' for this test.

        Here we use ticker (prefix of query_id) as a group identifier:
          TECH_01 -> TECH
          FIN_02  -> FIN
          HLTH_03 -> HLTH
        """
        qid = result.get("query_id", "")
        if "_" in qid:
            return qid.split("_")[0]
        return "UNKNOWN"

    def compute_group_stats(self, min_samples: int = 1) -> Dict[str, GroupStats]:
        """
        Aggregate performance metrics per group.
        """
        buckets = defaultdict(list)

        for r in self.results:
            group_id = self._get_group_id(r)
            buckets[group_id].append(r)

        group_stats: Dict[str, GroupStats] = {}

        for group_id, group_results in buckets.items():
            if len(group_results) < min_samples:
                continue

            # Only successful runs for metric averages
            successful = [gr for gr in group_results if gr.get("status") == "success"]
            num_tests = len(group_results)
            num_success = len(successful)
            success_rate = num_success / num_tests if num_tests > 0 else 0.0

            if successful:
                overall_scores = [gr.get("overall_score", 0.0) for gr in successful]
                groundedness_scores = [gr.get("groundedness", {}).get("score", 0.0) for gr in successful]
                relevancy_scores = [gr.get("answer_relevancy", {}).get("score", 0.0) for gr in successful]
                relevancy_scores = [gr.get("answer_relevancy", {}).get("score", 0.0) for gr in successful]
                retrieval_hits = [gr.get("retrieval_hit", 0) for gr in successful]
                
                avg_overall = float(np.mean(overall_scores))
                avg_grounded = float(np.mean(groundedness_scores))
                avg_relevancy = float(np.mean(relevancy_scores))
                avg_retrieval_recall = float(np.mean(retrieval_hits))
            else:
                avg_overall = 0.0
                avg_grounded = 0.0
                avg_relevancy = 0.0
                avg_retrieval_recall = 0.0

            group_stats[group_id] = GroupStats(
                group_id=group_id,
                num_tests=num_tests,
                num_success=num_success,
                avg_overall_score=avg_overall,
                avg_groundedness=avg_grounded,
                avg_relevancy=avg_relevancy,
                avg_retrieval_recall=avg_retrieval_recall,
                success_rate=success_rate,
            )

        return group_stats

    # ─────────────────────────────────────────────────────────────
    # Bias check logic
    # ─────────────────────────────────────────────────────────────

    def check_bias(
        self,
        min_samples: int = 3,
        max_allowed_gap: float = 0.20,
        min_group_score: float = 0.60,
    ) -> Dict:
        """
        Check for bias across groups.

        Rules (simple but defensible for the assignment):
          1. Only consider groups with at least `min_samples` test cases.
          2. Compute each group's avg overall_score and success_rate.
          3. Compute global averages.
          4. Bias flags:
             - any group's avg_overall_score < `min_group_score`
             - OR (max_group_avg - min_group_avg) > `max_allowed_gap`

        Returns a dict with 'bias_passed' and per-group metrics.
        """
        group_stats = self.compute_group_stats(min_samples=min_samples)

        if not group_stats:
            return {
                "bias_passed": False,
                "reason": "No groups with sufficient samples",
                "groups": {},
            }

        # Global metrics
        all_groups = list(group_stats.values())
        global_avg_score = float(np.mean([g.avg_overall_score for g in all_groups]))
        global_success_rate = float(np.mean([g.success_rate for g in all_groups]))
        global_avg_retrieval_recall = float(np.mean([g.avg_retrieval_recall for g in all_groups]))
        global_avg_retrieval_recall = float(np.mean([g.avg_retrieval_recall for g in all_groups]))

        # Disparity metrics
        scores = [g.avg_overall_score for g in all_groups]
        max_score = max(scores)
        min_score = min(scores)
        max_gap = max_score - min_score

        # Check per-group thresholds
        per_group_failures = []
        for g in all_groups:
            if g.avg_overall_score < min_group_score:
                per_group_failures.append(
                    f"group {g.group_id} avg_overall_score={g.avg_overall_score:.3f} < {min_group_score:.3f}"
                )

        disparity_failure = max_gap > max_allowed_gap

        bias_passed = not per_group_failures and not disparity_failure

        return {
            "bias_passed": bias_passed,
            "global": {
                "global_avg_overall_score": global_avg_score,
                "global_avg_success_rate": global_success_rate,
                "global_avg_retrieval_recall": global_avg_retrieval_recall,
                "global_avg_retrieval_recall": global_avg_retrieval_recall,
                "max_group_avg_score": max_score,
                "min_group_avg_score": min_score,
                "max_gap": max_gap,
                "max_allowed_gap": max_allowed_gap,
                "min_group_score_threshold": min_group_score,
            },
            "per_group": {
                g.group_id: {
                    "num_tests": g.num_tests,
                    "num_success": g.num_success,
                    "success_rate": g.success_rate,
                    "avg_overall_score": g.avg_overall_score,
                    "avg_groundedness": g.avg_groundedness,
                    "avg_relevancy": g.avg_relevancy,
                    "avg_relevancy": g.avg_relevancy,
                    "avg_retrieval_recall": g.avg_retrieval_recall,
                }
                for g in all_groups
            },
            "failures": {
                "per_group_thresholds": per_group_failures,
                "disparity_failure": disparity_failure,
            },
        }


def main():
    print("\n" + "=" * 70)
    print("🧪 BIAS DETECTION ACROSS GROUPS (e.g., TICKERS/COMPANIES)")
    print("=" * 70)

    # For now: run a fresh validation pass and reuse its results
    pipeline = ValidationPipeline()
    results = pipeline.run_all_tests(limit=None)

    detector = BiasDetector(results=results)
    report = detector.check_bias(
        min_samples=1,        # Reduced minimum samples to ensure it runs on small datasets
        max_allowed_gap=0.20, # max 20 percentage point difference in avg scores
        min_group_score=BIAS_CONFIG["min_score_threshold"], # each group should have at least 60% avg score
    )

    if "global" not in report:
        print(f"\n❌ BIAS CHECK FAILED: {report.get('reason', 'Unknown error')}")
        sys.exit(1)

    print("\n📊 GLOBAL BIAS METRICS")
    for k, v in report["global"].items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    print("\n📊 PER-GROUP METRICS")
    for group_id, stats in report["per_group"].items():
        print(f"\n  Group: {group_id}")
        print(f"    num_tests:       {stats['num_tests']}")
        print(f"    success_rate:    {stats['success_rate']:.3f}")
        print(f"    avg_overall:     {stats['avg_overall_score']:.3f}")
        print(f"    avg_groundedness:{stats['avg_groundedness']:.3f}")
        print(f"    avg_relevancy:   {stats['avg_relevancy']:.3f}")
        print(f"    avg_relevancy:   {stats['avg_relevancy']:.3f}")
        print(f"    avg_retrieval:   {stats['avg_retrieval_recall']:.3f}")

    if report["failures"]["per_group_thresholds"] or report["failures"]["disparity_failure"]:
        print("\n❌ BIAS CHECK FAILED")
        if report["failures"]["per_group_thresholds"]:
            print("  Per-group issues:")
            for msg in report["failures"]["per_group_thresholds"]:
                print(f"   - {msg}")
        if report["failures"]["disparity_failure"]:
            print(
                f"  Score disparity too high: max_gap={report['global']['max_gap']:.3f} "
                f"> max_allowed_gap={report['global']['max_allowed_gap']:.3f}"
            )
        exit_code = 1
    else:
        print("\n✅ BIAS CHECK PASSED")
        exit_code = 0

    # Save report
    report_path = "src/model_validation/reports/bias_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, cls=NumpyEncoder)

    print(f"\n✅ Bias report saved to {report_path}")

    # Save Markdown report
    md_path = "src/model_validation/reports/bias_report.md"
    save_markdown_report(report, md_path)

    # CI/CD GATEKEEPER
    # Fail if overall score is too low
    if report["global"]["global_avg_overall_score"] < BIAS_CONFIG["min_score_threshold"]:
        print(f"❌ FAILURE: Overall score {report['global']['global_avg_overall_score']:.2f} is below threshold {BIAS_CONFIG['min_score_threshold']}")
        sys.exit(1)

    print("✅ SUCCESS: Model passed validation thresholds.")
    sys.exit(0)


def save_markdown_report(report: Dict, filepath: str):
    """
    Generate a Markdown table from the bias report.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# 📊 Model Validation & Bias Report\n\n")
        
        # Global Metrics
        f.write("## 🌍 Global Metrics\n\n")
        f.write("| Metric | Value |\n")
        f.write("| :--- | :--- |\n")
        glob = report["global"]
        f.write(f"| **Overall Score** | {glob['global_avg_overall_score']:.2%} |\n")
        f.write(f"| **Success Rate** | {glob['global_avg_success_rate']:.1%} |\n")
        f.write(f"| **Retrieval Recall** | {glob['global_avg_retrieval_recall']:.2%} |\n")
        f.write(f"| **Retrieval Recall** | {glob['global_avg_retrieval_recall']:.2%} |\n")
        f.write(f"| **Max Group Gap** | {glob['max_gap']:.2%} (Limit: {glob['max_allowed_gap']:.0%}) |\n")
        f.write("\n")

        # Per-Group Metrics
        f.write("## 👥 Per-Group Metrics\n\n")
        f.write("| Group | Tests | Success Rate | Overall Score | Groundedness | Relevancy | Retrieval Recall |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        
        for group_id, stats in report["per_group"].items():
            f.write(f"| **{group_id}** | {stats['num_tests']} | {stats['success_rate']:.1%} | "
                    f"{stats['avg_overall_score']:.2%} | {stats['avg_groundedness']:.2%} | "
                    f"{stats['avg_relevancy']:.2%} | "
                    f"{stats['avg_retrieval_recall']:.2%} |\n")
        
        f.write("\n")
        
        # Pass/Fail Status
        if report["failures"]["per_group_thresholds"] or report["failures"]["disparity_failure"]:
            f.write("## ❌ Status: FAILED\n\n")
            if report["failures"]["per_group_thresholds"]:
                f.write("### Per-Group Issues\n")
                for msg in report["failures"]["per_group_thresholds"]:
                    f.write(f"- {msg}\n")
            if report["failures"]["disparity_failure"]:
                f.write(f"\n### Disparity Issue\n")
                f.write(f"- Max gap {glob['max_gap']:.2%} exceeds limit {glob['max_allowed_gap']:.2%}\n")
        else:
            f.write("## ✅ Status: PASSED\n")

    print(f"✅ Markdown report saved to {filepath}")


if __name__ == "__main__":
    main()
