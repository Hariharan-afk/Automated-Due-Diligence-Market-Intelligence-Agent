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
            "max_days_old": 365
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