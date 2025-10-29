"""
Bias Detection and Mitigation Module - FINAL FIXED VERSION
Includes fairness metrics, bias detection, mitigation, and recommendations.
"""

import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, List
from datetime import datetime
from collections import Counter
from pathlib import Path
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BiasDetector:
    """Detect, analyze, and mitigate bias in collected data."""

    def __init__(self):
        self.slicing_features = ['source', 'published_date', 'fiscal_year', 'filing_type']
        self.sec_expected_sections = {'10-K': 4, '10-Q': 3}

    # ==============================================================
    # MAIN ENTRY
    # ==============================================================

    def analyze_data(self, data: Dict) -> Dict:
        """Perform bias analysis on processed company data."""
        logger.info(f"🔍 Analyzing bias for: {data.get('company_name')}")

        news_articles = data.get('news_articles', [])
        sec_filings = data.get('sec_filings', {})

        if not news_articles and not sec_filings:
            return {"error": "No data to analyze", "bias_detected": False}

        # --- Analyze News ---
        news_analysis = {}
        if news_articles:
            df = pd.DataFrame(news_articles)
            news_analysis = {
                "source_distribution": self._analyze_by_source(df),
                "temporal_distribution": self._analyze_by_time(df),
                "quality_across_slices": self._analyze_quality_across_slices(df),
            }

        # --- Analyze SEC ---
        sec_analysis = {}
        if sec_filings:
            sec_analysis = {
                "fiscal_year_distribution": self._analyze_sec_fiscal_years(sec_filings),
                "filing_type_coverage": self._analyze_sec_filing_types(sec_filings),
                "section_completeness": self._analyze_sec_sections(sec_filings),
                "company_size_indicators": self._analyze_sec_complexity(sec_filings),
            }

        # --- Fairness metrics ---
        fairness_scores = self._calculate_fairness_metrics(
            news_analysis.get("source_distribution", {}),
            news_analysis.get("temporal_distribution", {}),
            sec_analysis,
        )

        # --- Bias findings ---
        bias_findings = self._detect_bias_issues(
            news_analysis.get("source_distribution", {}),
            news_analysis.get("temporal_distribution", {}),
            news_analysis.get("quality_across_slices", {}),
            sec_analysis,
        )

        # --- Generate recommendations ---
        recommendations = self._generate_recommendations(bias_findings)

        # --- Compile final report ---
        report = {
            "company_name": data.get('company_name'),
            "total_articles": len(news_articles),
            "total_sec_filings": len([f for f in sec_filings.values() if f and "error" not in f]),
            "analysis": {"news": news_analysis, "sec": sec_analysis},
            "fairness_metrics": fairness_scores,
            "bias_findings": bias_findings,
            "bias_detected": len(bias_findings) > 0,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
        }

        # --- Mitigation ---
        if bias_findings:
            data = self.mitigate_bias(bias_findings, data)
            report["mitigation_actions"] = data.get("mitigation_actions", [])
        else:
            report["mitigation_actions"] = ["No mitigation required."]

        self._save_report(report)
        logger.info(f"✅ Bias analysis complete. Findings: {len(bias_findings)}")

        return report

    # ==============================================================
    # ANALYSIS HELPERS
    # ==============================================================

    def _analyze_by_source(self, df: pd.DataFrame) -> Dict:
        counts = df['source'].value_counts()
        total = len(df)
        stats = {
            "total_sources": len(counts),
            "distribution": counts.to_dict(),
            "percentages": (counts / total * 100).to_dict() if total > 0 else {},
            "dominance_ratio": counts.iloc[0] / total if len(counts) > 0 else 0,
        }
        stats["gini_coefficient"] = self._calculate_gini_coefficient(counts.values)
        return stats

    def _analyze_by_time(self, df: pd.DataFrame) -> Dict:
        df['date'] = pd.to_datetime(df['published_date'], errors='coerce')
        df = df.dropna(subset=['date'])
        if len(df) == 0:
            return {"error": "No valid dates found", "recency_bias": 0.0}
        monthly_counts = df['date'].dt.to_period('M').value_counts().sort_index()
        recency_bias = self._calculate_recency_bias(df['date'])
        return {
            "date_range": {
                "earliest": df['date'].min().strftime('%Y-%m-%d'),
                "latest": df['date'].max().strftime('%Y-%m-%d'),
            },
            "monthly_distribution": {str(k): int(v) for k, v in monthly_counts.items()},
            "recency_bias": recency_bias,
        }

    def _analyze_quality_across_slices(self, df: pd.DataFrame) -> Dict:
        if 'word_count' not in df:
            df['word_count'] = 0
        return {
            "mean_word_count": float(df['word_count'].mean()),
            "std_word_count": float(df['word_count'].std() or 0),
        }

    def _analyze_sec_fiscal_years(self, sec: Dict) -> Dict:
        years = [f.get("fiscal_year") for f in sec.values() if f and "error" not in f]
        years = [y for y in years if y]
        if not years:
            return {"error": "No fiscal years found", "is_continuous": True}
        return {
            "years_covered": sorted(set(years)),
            "is_continuous": self._check_fiscal_year_continuity(sorted(set(years))),
        }

    def _analyze_sec_filing_types(self, sec: Dict) -> Dict:
        types = [k for k, v in sec.items() if v and "error" not in v]
        return {
            "types_available": types,
            "has_10k": "10-K" in types,
            "has_10q": "10-Q" in types,
            "has_both": "10-K" in types and "10-Q" in types,
            "balance_score": 1.0 if len(types) >= 2 else 0.5,
        }

    def _analyze_sec_sections(self, sec: Dict) -> Dict:
        result = {}
        for t, f in sec.items():
            if not f or "error" in f:
                continue
            expected = self.sec_expected_sections.get(t, 0)
            actual = len(f.get("sections", {}))
            result[t] = {
                "expected": expected,
                "actual": actual,
                "completeness_ratio": actual / expected if expected > 0 else 1.0,
            }
        return result

    def _analyze_sec_complexity(self, sec: Dict) -> Dict:
        result = {}
        for t, f in sec.items():
            if f and "statistics" in f:
                s = f["statistics"]
                result[t] = {"total_words": s.get("total_words", 0)}
        return result

    # ==============================================================
    # METRICS AND DETECTION
    # ==============================================================

    def _calculate_fairness_metrics(self, source, temporal, sec) -> Dict:
        """Compute fairness metrics across source, time, and SEC."""
        try:
            fairness = {}

            dominance = source.get("dominance_ratio", 0)
            gini = source.get("gini_coefficient", 0)
            fairness["source_balance_score"] = max(0, 100 * (1 - dominance * 0.7 - gini * 0.3))

            recency = temporal.get("recency_bias", 0)
            fairness["temporal_fairness_score"] = max(0, 100 * (1 - recency))

            sec_cov = sec.get("filing_type_coverage", {})
            fairness["filing_coverage_score"] = sec_cov.get("balance_score", 0.5) * 100

            sec_sections = sec.get("section_completeness", {})
            completeness = [v.get("completeness_ratio", 1) for v in sec_sections.values()]
            fairness["section_completeness_score"] = np.mean(completeness) * 100 if completeness else 100

            fairness["overall_fairness_score"] = round(np.mean(list(fairness.values())), 2)
            return fairness
        except Exception as e:
            logger.error(f"Fairness metric calculation failed: {e}")
            return {"overall_fairness_score": 0}

    def _detect_bias_issues(self, source, temporal, quality, sec) -> List[Dict]:
        findings = []
        dominance = source.get("dominance_ratio", 0)
        if dominance and dominance > 0.6:
            findings.append({
                "type": "source_dominance",
                "severity": "high",
                "description": "One news source dominates the dataset (>60% of articles)"
            })

        total_sources = source.get("total_sources", 0)
        if total_sources < 3:
            findings.append({
                "type": "low_source_diversity",
                "severity": "medium",
                "description": "Low source diversity - less than 3 unique news sources"
            })

        recency = temporal.get("recency_bias", 0) or 0
        if recency > 0.7:
            findings.append({
                "type": "recency_bias",
                "severity": "medium",
                "description": "Recent articles dominate the dataset (recency bias detected)"
            })

        coverage = sec.get("filing_type_coverage", {})
        if not coverage.get("has_both", True):
            findings.append({
                "type": "incomplete_filing_coverage",
                "severity": "medium",
                "description": "Missing either 10-K or 10-Q filings"
            })

        for t, s in sec.get("section_completeness", {}).items():
            if s.get("completeness_ratio", 1) < 0.8:
                findings.append({
                    "type": "incomplete_sections",
                    "severity": "low",
                    "description": f"SEC {t} filing has incomplete sections (<80% completeness)"
                })

        fiscal = sec.get("fiscal_year_distribution", {})
        if not fiscal.get("is_continuous", True):
            findings.append({
                "type": "discontinuous_fiscal_years",
                "severity": "low",
                "description": "Fiscal year data has gaps (not continuous)"
            })

        return findings

    def _generate_recommendations(self, findings: List[Dict]) -> List[str]:
        """Generate human-readable recommendations."""
        if not findings:
            return ["✅ No significant bias detected."]

        recs = []
        for f in findings:
            t = f["type"]
            if t == "source_dominance":
                recs.append("Diversify sources to reduce dominance by one outlet.")
            elif t == "low_source_diversity":
                recs.append("Collect data from more publishers to improve diversity.")
            elif t == "recency_bias":
                recs.append("Include older articles to reduce recency skew.")
            elif t == "incomplete_filing_coverage":
                recs.append("Fetch both 10-K and 10-Q filings.")
            elif t == "incomplete_sections":
                recs.append("Retry extraction to include missing SEC sections.")
            elif t == "discontinuous_fiscal_years":
                recs.append("Backfill missing fiscal years.")
        return list(set(recs))

    # ==============================================================
    # MITIGATION AND UTILS
    # ==============================================================

    def mitigate_bias(self, findings: List[Dict], data: Dict) -> Dict:
        actions = []
        if any(f["type"] == "source_dominance" for f in findings):
            df = pd.DataFrame(data.get("news_articles", []))
            if not df.empty and "source" in df.columns:
                dom = df["source"].value_counts().idxmax()
                balanced_df = pd.concat([df[df["source"] != dom],
                                         df[df["source"] == dom].sample(frac=0.5, random_state=42)])
                data["news_articles"] = balanced_df.to_dict(orient="records")
                actions.append(f"Reduced dominance of source '{dom}'.")
        if not actions:
            actions = ["No mitigation required."]
        data["mitigation_actions"] = actions
        return data

    # ==============================================================
    # UTILITY FUNCTIONS
    # ==============================================================

    @staticmethod
    def _calculate_recency_bias(dates: pd.Series) -> float:
        if len(dates) == 0:
            return 0.0
        latest = dates.max()
        recent = (dates >= (latest - pd.Timedelta(days=30))).sum()
        return float(round(recent / len(dates), 3))

    @staticmethod
    def _calculate_gini_coefficient(values) -> float:
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n == 0:
            return 0.0
        cum = sum((n - i) * val for i, val in enumerate(sorted_vals))
        return (2 * cum) / (n * sum(sorted_vals)) - (n + 1) / n

    @staticmethod
    def _check_fiscal_year_continuity(years: List[int]) -> bool:
        if len(years) <= 1:
            return True
        return all(years[i + 1] - years[i] == 1 for i in range(len(years) - 1))

    def _save_report(self, report: Dict):
        """Save report to data/bias_reports."""
        path = Path("data/bias_reports")
        path.mkdir(parents=True, exist_ok=True)
        fname = path / f"{report['company_name'].replace(' ', '_')}_bias_report.json"
        try:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
            logger.info(f"💾 Bias report saved to: {fname}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save bias report: {e}")
