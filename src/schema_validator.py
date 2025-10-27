"""
Schema Validation and Anomaly Detection Module - FINAL VERSION
"""

import json
import logging
from typing import Dict, List, Any
from datetime import datetime
import statistics
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validate data against expected schema"""
    
    def __init__(self):
        self.schema = {
            "company_name": {"type": str, "required": True},
            "ticker": {"type": (str, type(None)), "required": False},
            "wikipedia": {
                "type": dict,
                "required": True,
                "fields": {
                    "title": {"type": str},
                    "summary": {"type": str},
                    "url": {"type": str}
                }
            },
            "news_articles": {
                "type": list,
                "required": True,
                "min_items": 0
            },
            "sec_filings": {
                "type": dict,
                "required": False,  # Optional since not all companies may have SEC filings fetched
                "fields": {
                    "10-K": {"type": dict},
                    "10-Q": {"type": dict}
                }
            }
        }
    
    def validate(self, data: Dict) -> Dict:
        """
        Validate data against schema
        
        Returns:
            Dictionary with validation results and errors
        """
        logger.info(f"🔍 Validating schema for: {data.get('company_name')}")
        
        errors = []
        warnings = []
        
        # Check required fields
        for field, rules in self.schema.items():
            if rules.get("required", False) and field not in data:
                errors.append(f"Missing required field: {field}")
                continue
            
            if field in data:
                # Type validation
                expected_type = rules.get("type")
                actual_value = data[field]
                
                if not isinstance(actual_value, expected_type):
                    errors.append(f"Field '{field}' has wrong type. Expected {expected_type}, got {type(actual_value)}")
                
                # Nested field validation
                if rules.get("fields") and isinstance(actual_value, dict):
                    for subfield, subrules in rules["fields"].items():
                        if subfield not in actual_value:
                            warnings.append(f"Missing recommended field: {field}.{subfield}")
        
        # Validate news articles structure
        if "news_articles" in data:
            articles = data["news_articles"]
            if len(articles) == 0:
                warnings.append("No news articles found")

            for idx, article in enumerate(articles):
                if not isinstance(article, dict):
                    errors.append(f"Article {idx} is not a dictionary")
                elif "title" not in article or "url" not in article:
                    errors.append(f"Article {idx} missing required fields")

        # Validate SEC filings structure
        if "sec_filings" in data:
            sec_filings = data["sec_filings"]
            if not isinstance(sec_filings, dict):
                errors.append("sec_filings must be a dictionary")
            else:
                # Validate each filing type
                for filing_type in ["10-K", "10-Q"]:
                    if filing_type in sec_filings:
                        filing = sec_filings[filing_type]

                        # Skip if filing is None or empty
                        if filing is None:
                            continue

                        if "error" in filing:
                            warnings.append(f"{filing_type} contains error: {filing.get('error')}")
                            continue

                        # Check required SEC filing fields
                        required_sec_fields = ["ticker", "filing_type", "sections"]
                        for field in required_sec_fields:
                            if field not in filing:
                                errors.append(f"{filing_type} missing required field: {field}")

                        # Validate sections
                        if "sections" in filing:
                            sections = filing["sections"]
                            if not isinstance(sections, dict):
                                errors.append(f"{filing_type} sections must be a dictionary")
                            elif len(sections) == 0:
                                warnings.append(f"{filing_type} has no sections")
                            else:
                                # Check each section has content
                                for section_name, section_text in sections.items():
                                    if not section_text or len(section_text.strip()) < 50:
                                        warnings.append(f"{filing_type} section '{section_name}' has minimal content")

                        # Validate fiscal year
                        fiscal_year = filing.get("fiscal_year", 0)
                        if fiscal_year:
                            current_year = datetime.now().year
                            if fiscal_year < 2000 or fiscal_year > current_year + 1:
                                warnings.append(f"{filing_type} has unusual fiscal year: {fiscal_year}")

                        # Validate CIK format
                        cik = filing.get("cik", "")
                        if cik and (not cik.isdigit() or len(cik) != 10):
                            warnings.append(f"{filing_type} CIK format may be incorrect: {cik}")

        validation_result = {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "timestamp": datetime.now().isoformat()
        }
        
        if validation_result["valid"]:
            logger.info("✅ Schema validation passed")
        else:
            logger.error(f"❌ Schema validation failed: {len(errors)} errors")
        
        return validation_result


class AnomalyDetector:
    """Detect anomalies in data"""
    
    def __init__(self):
        self.thresholds = {
            "min_wiki_word_count": 100,
            "max_wiki_word_count": 100000,
            "min_news_articles": 1,
            "max_news_articles": 100,
            "min_article_word_count": 10,
            "max_days_old": 365,
            # SEC filing thresholds
            "min_sec_section_word_count": 500,
            "max_sec_section_word_count": 500000,
            "min_sec_sections": 2,
            "expected_10k_sections": 4,  # Items 1, 1A, 7, 8
            "expected_10q_sections": 3,  # part1item1, part1item2, part2item1a
            "min_sec_tables_per_filing": 5,
            "max_sec_tables_per_filing": 500
        }
    
    def detect(self, data: Dict) -> Dict:
        """
        Detect anomalies in data
        
        Returns:
            Dictionary with anomaly detection results
        """
        logger.info(f"🔍 Detecting anomalies for: {data.get('company_name')}")
        
        anomalies = []
        
        # Wikipedia anomalies
        wiki_data = data.get("wikipedia", {})
        if wiki_data and "error" not in wiki_data:
            word_count = wiki_data.get("word_count", 0)
            
            if word_count < self.thresholds["min_wiki_word_count"]:
                anomalies.append({
                    "type": "wikipedia_too_short",
                    "severity": "warning",
                    "message": f"Wikipedia content unusually short: {word_count} words",
                    "value": word_count
                })
            elif word_count > self.thresholds["max_wiki_word_count"]:
                anomalies.append({
                    "type": "wikipedia_too_long",
                    "severity": "info",
                    "message": f"Wikipedia content unusually long: {word_count} words",
                    "value": word_count
                })
        
        # News article anomalies
        news_articles = data.get("news_articles", [])
        
        if len(news_articles) < self.thresholds["min_news_articles"]:
            anomalies.append({
                "type": "insufficient_news",
                "severity": "error",
                "message": f"Too few news articles: {len(news_articles)}",
                "value": len(news_articles)
            })
        elif len(news_articles) > self.thresholds["max_news_articles"]:
            anomalies.append({
                "type": "excessive_news",
                "severity": "warning",
                "message": f"Unusually high number of articles: {len(news_articles)}",
                "value": len(news_articles)
            })
        
        # Check article quality
        article_word_counts = [a.get("word_count", 0) for a in news_articles]
        if article_word_counts:
            avg_words = statistics.mean(article_word_counts)
            
            if avg_words < self.thresholds["min_article_word_count"]:
                anomalies.append({
                    "type": "low_article_quality",
                    "severity": "warning",
                    "message": f"Articles have low word count: {avg_words:.1f} avg words",
                    "value": avg_words
                })
        
        # Check for missing content
        articles_without_content = sum(1 for a in news_articles if not a.get("has_content", False))
        if articles_without_content > len(news_articles) * 0.5:
            anomalies.append({
                "type": "missing_content",
                "severity": "warning",
                "message": f"{articles_without_content}/{len(news_articles)} articles missing content",
                "value": articles_without_content
            })
        
        # Check data freshness
        stats = data.get("statistics", {})
        date_range = stats.get("date_range", {})
        if date_range.get("latest"):
            try:
                latest_date = datetime.strptime(date_range["latest"], "%Y-%m-%d")
                days_old = (datetime.now() - latest_date).days

                if days_old > self.thresholds["max_days_old"]:
                    anomalies.append({
                        "type": "stale_data",
                        "severity": "warning",
                        "message": f"Most recent article is {days_old} days old",
                        "value": days_old
                    })
            except:
                pass

        # SEC filings anomalies
        sec_filings = data.get("sec_filings", {})
        if sec_filings:
            for filing_type, filing_data in sec_filings.items():
                if filing_data and "error" not in filing_data:
                    # Check section count
                    sections = filing_data.get("sections", {})
                    num_sections = len(sections)

                    expected_sections = (
                        self.thresholds["expected_10k_sections"]
                        if filing_type == "10-K"
                        else self.thresholds["expected_10q_sections"]
                    )

                    if num_sections < self.thresholds["min_sec_sections"]:
                        anomalies.append({
                            "type": f"sec_{filing_type.lower()}_few_sections",
                            "severity": "error",
                            "message": f"{filing_type} has only {num_sections} sections",
                            "value": num_sections
                        })
                    elif num_sections < expected_sections:
                        anomalies.append({
                            "type": f"sec_{filing_type.lower()}_missing_sections",
                            "severity": "warning",
                            "message": f"{filing_type} has {num_sections}/{expected_sections} expected sections",
                            "value": num_sections
                        })

                    # Check section word counts
                    filing_stats = filing_data.get("statistics", {})
                    for section_name, section_stats in filing_stats.items():
                        if isinstance(section_stats, dict) and "word_count" in section_stats:
                            word_count = section_stats["word_count"]

                            if word_count < self.thresholds["min_sec_section_word_count"]:
                                anomalies.append({
                                    "type": f"sec_{filing_type.lower()}_short_section",
                                    "severity": "warning",
                                    "message": f"{filing_type} section '{section_name}' unusually short: {word_count} words",
                                    "value": word_count
                                })
                            elif word_count > self.thresholds["max_sec_section_word_count"]:
                                anomalies.append({
                                    "type": f"sec_{filing_type.lower()}_long_section",
                                    "severity": "info",
                                    "message": f"{filing_type} section '{section_name}' unusually long: {word_count} words",
                                    "value": word_count
                                })

                    # Check table counts
                    total_tables = filing_stats.get("total_tables", 0)
                    if total_tables < self.thresholds["min_sec_tables_per_filing"]:
                        anomalies.append({
                            "type": f"sec_{filing_type.lower()}_few_tables",
                            "severity": "warning",
                            "message": f"{filing_type} has only {total_tables} tables",
                            "value": total_tables
                        })
                    elif total_tables > self.thresholds["max_sec_tables_per_filing"]:
                        anomalies.append({
                            "type": f"sec_{filing_type.lower()}_many_tables",
                            "severity": "info",
                            "message": f"{filing_type} has {total_tables} tables (unusually high)",
                            "value": total_tables
                        })

                    # Check fiscal year consistency
                    fiscal_year = filing_data.get("fiscal_year", 0)
                    if fiscal_year:
                        current_year = datetime.now().year
                        if fiscal_year > current_year:
                            anomalies.append({
                                "type": f"sec_{filing_type.lower()}_future_fiscal_year",
                                "severity": "error",
                                "message": f"{filing_type} fiscal year in future: {fiscal_year}",
                                "value": fiscal_year
                            })
                        elif current_year - fiscal_year > 5:
                            anomalies.append({
                                "type": f"sec_{filing_type.lower()}_old_fiscal_year",
                                "severity": "warning",
                                "message": f"{filing_type} fiscal year is old: {fiscal_year} ({current_year - fiscal_year} years ago)",
                                "value": fiscal_year
                            })

        result = {
            "has_anomalies": len(anomalies) > 0,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "severity_breakdown": self._count_by_severity(anomalies),
            "timestamp": datetime.now().isoformat()
        }
        
        if result["has_anomalies"]:
            logger.warning(f"⚠️ Detected {len(anomalies)} anomalies")
        else:
            logger.info("✅ No anomalies detected")
        
        return result
    
    @staticmethod
    def _count_by_severity(anomalies: List[Dict]) -> Dict:
        """Count anomalies by severity"""
        counts = {"error": 0, "warning": 0, "info": 0}
        for anomaly in anomalies:
            severity = anomaly.get("severity", "info")
            counts[severity] = counts.get(severity, 0) + 1
        return counts


class DataQualityReport:
    """Generate comprehensive data quality report"""
    
    def __init__(self):
        self.validator = SchemaValidator()
        self.anomaly_detector = AnomalyDetector()
    
    def generate_report(self, data: Dict) -> Dict:
        """Generate complete data quality report"""
        logger.info(f"📊 Generating quality report for: {data.get('company_name')}")
        
        validation_result = self.validator.validate(data)
        anomaly_result = self.anomaly_detector.detect(data)
        
        report = {
            "company_name": data.get("company_name"),
            "ticker": data.get("ticker"),
            "schema_validation": validation_result,
            "anomaly_detection": anomaly_result,
            "overall_quality_score": self._calculate_quality_score(validation_result, anomaly_result),
            "recommendations": self._generate_recommendations(validation_result, anomaly_result),
            "timestamp": datetime.now().isoformat()
        }
        
        # Save report
        self._save_report(report)
        
        logger.info(f"✅ Quality report complete. Score: {report['overall_quality_score']}/100")
        return report
    
    @staticmethod
    def _calculate_quality_score(validation: Dict, anomalies: Dict) -> float:
        """Calculate overall quality score (0-100)"""
        score = 100.0
        
        # Deduct for validation errors
        score -= len(validation.get("errors", [])) * 20
        score -= len(validation.get("warnings", [])) * 5
        
        # Deduct for anomalies
        severity_breakdown = anomalies.get("severity_breakdown", {})
        score -= severity_breakdown.get("error", 0) * 15
        score -= severity_breakdown.get("warning", 0) * 5
        score -= severity_breakdown.get("info", 0) * 2
        
        return max(0.0, min(100.0, score))
    
    @staticmethod
    def _generate_recommendations(validation: Dict, anomalies: Dict) -> List[str]:
        """Generate recommendations based on findings"""
        recommendations = []
        
        if not validation.get("valid"):
            recommendations.append("Fix schema validation errors before proceeding")
        
        for anomaly in anomalies.get("anomalies", []):
            if anomaly["severity"] == "error":
                recommendations.append(f"CRITICAL: {anomaly['message']}")
            elif anomaly["severity"] == "warning":
                recommendations.append(f"Review: {anomaly['message']}")
        
        if not recommendations:
            recommendations.append("Data quality is good. No issues detected.")
        
        return recommendations
    
    @staticmethod
    def _save_report(report: Dict):
        """Save quality report to file"""
        os.makedirs("data/quality_reports", exist_ok=True)
        filename = f"data/quality_reports/{report['company_name'].replace(' ', '_')}_quality_report.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        logger.info(f"💾 Quality report saved to: {filename}")


def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python schema_validator.py <processed_data_file.json>")
        sys.exit(1)
    
    data_file = sys.argv[1]
    
    if os.path.exists(data_file):
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        reporter = DataQualityReport()
        report = reporter.generate_report(data)
        
        print(f"\n{'='*50}")
        print(f"Quality Report: {report['company_name']}")
        print(f"Quality Score: {report['overall_quality_score']}/100")
        print(f"Validation: {'✅ Pass' if report['schema_validation']['valid'] else '❌ Fail'}")
        print(f"Anomalies: {report['anomaly_detection']['anomaly_count']}")
        print(f"\nRecommendations:")
        for rec in report['recommendations']:
            print(f"  • {rec}")
        print(f"{'='*50}\n")
    else:
        print(f"File not found: {data_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()