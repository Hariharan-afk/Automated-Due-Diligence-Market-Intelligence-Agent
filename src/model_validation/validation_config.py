"""
validation/validation_report.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generate human-readable validation reports
"""

from datetime import datetime
from typing import List, Dict


class ValidationReport:
    """Generate validation reports in multiple formats"""
    
    def __init__(self, results: List[Dict], summary: Dict, acceptance: Dict):
        self.results = results
        self.summary = summary
        self.acceptance = acceptance
        self.timestamp = datetime.now()
    
    def generate_html_report(self, filepath: str = None) -> str:
        """Generate HTML validation report"""
        if filepath is None:
            timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
            filepath = f"validation/report_{timestamp}.html"
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Validation Report - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            margin: 40px;
            background: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }}
        .metric-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        .metric-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .pass {{ color: #27ae60; }}
        .fail {{ color: #e74c3c; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        th {{
            background: #34495e;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .progress-bar {{
            background: #ecf0f1;
            height: 24px;
            border-radius: 12px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #3498db, #2ecc71);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
        }}
        .criteria-check {{
            display: flex;
            align-items: center;
            padding: 10px;
            margin: 5px 0;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .criteria-check.passed {{
            border-left: 4px solid #27ae60;
        }}
        .criteria-check.failed {{
            border-left: 4px solid #e74c3c;
        }}
        .test-result {{
            margin: 20px 0;
            padding: 15px;
            border: 1px solid #ecf0f1;
            border-radius: 4px;
        }}
        .test-result.success {{
            border-left: 4px solid #27ae60;
        }}
        .test-result.failed {{
            border-left: 4px solid #e74c3c;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge.success {{ background: #27ae60; color: white; }}
        .badge.failed {{ background: #e74c3c; color: white; }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Validation Report</h1>
        <p class="timestamp">Generated: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        {self._generate_summary_html()}
        {self._generate_acceptance_criteria_html()}
        {self._generate_detailed_results_html()}
    </div>
</body>
</html>"""
        
        with open(filepath, 'w') as f:
            f.write(html)
        
        print(f"📄 HTML report saved to {filepath}")
        return filepath
    
    def _generate_summary_html(self) -> str:
        """Generate summary section"""
        summary = self.summary
        
        success_rate = summary.get('success_rate', 0)
        avg_score = summary.get('avg_overall_score', 0)
        avg_time = summary.get('avg_execution_time', 0)
        avg_groundedness = summary.get('avg_groundedness', 0)
        
        return f"""
        <h2>📊 Summary Statistics</h2>
        
        <div class="summary-grid">
            <div class="metric-card">
                <h3>Success Rate</h3>
                <div class="value {'pass' if success_rate >= 0.9 else 'fail'}">{success_rate:.1%}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {success_rate*100}%">{summary.get('successful_tests', 0)}/{summary.get('total_tests', 0)}</div>
                </div>
            </div>
            
            <div class="metric-card">
                <h3>Avg Quality Score</h3>
                <div class="value {'pass' if avg_score >= 0.8 else 'fail'}">{avg_score:.1%}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {avg_score*100}%"></div>
                </div>
            </div>
            
            <div class="metric-card">
                <h3>Avg Execution Time</h3>
                <div class="value {'pass' if avg_time < 300 else 'fail'}">{avg_time:.1f}s</div>
                <small>Target: &lt;300s (5 min)</small>
            </div>
            
            <div class="metric-card">
                <h3>Avg Groundedness</h3>
                <div class="value {'pass' if avg_groundedness >= 0.95 else 'fail'}">{avg_groundedness:.1%}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {avg_groundedness*100}%"></div>
                </div>
            </div>
        </div>
        
        <h3>Metric Breakdown</h3>
        <table>
            <tr>
                <th>Metric</th>
                <th>Average</th>
                <th>Min</th>
                <th>Max</th>
                <th>Std Dev</th>
            </tr>
            <tr>
                <td>Overall Score</td>
                <td>{summary.get('avg_overall_score', 0):.2%}</td>
                <td>{summary.get('min_overall_score', 0):.2%}</td>
                <td>{summary.get('max_overall_score', 0):.2%}</td>
                <td>{summary.get('std_overall_score', 0):.2%}</td>
            </tr>
            <tr>
                <td>Execution Time</td>
                <td>{summary.get('avg_execution_time', 0):.2f}s</td>
                <td>{summary.get('min_execution_time', 0):.2f}s</td>
                <td>{summary.get('max_execution_time', 0):.2f}s</td>
                <td>{summary.get('std_execution_time', 0):.2f}s</td>
            </tr>
            <tr>
                <td>Groundedness</td>
                <td>{summary.get('avg_groundedness', 0):.2%}</td>
                <td>{summary.get('min_groundedness', 0):.2%}</td>
                <td colspan="2">-</td>
            </tr>
            <tr>
                <td>Citation F1</td>
                <td>{summary.get('avg_citation_f1', 0):.2%}</td>
                <td colspan="3">-</td>
            </tr>
            <tr>
                <td>Answer Relevancy</td>
                <td>{summary.get('avg_relevancy', 0):.2%}</td>
                <td colspan="3">-</td>
            </tr>
        </table>
        """
    
    def _generate_acceptance_criteria_html(self) -> str:
        """Generate acceptance criteria section"""
        criteria = self.acceptance['criteria']
        all_met = self.acceptance['all_criteria_met']
        
        criteria_html = ""
        for name, data in criteria.items():
            status = "passed" if data['passed'] else "failed"
            icon = "✅" if data['passed'] else "❌"
            
            criteria_html += f"""
            <div class="criteria-check {status}">
                <div style="flex: 1;">
                    <strong>{icon} {name.replace('_', ' ').title()}</strong><br>
                    <small>Threshold: {data['threshold']} | Actual: {data['actual']:.4f}</small>
                </div>
            </div>
            """
        
        return f"""
        <h2>🎯 Acceptance Criteria</h2>
        <div style="background: {'#d4edda' if all_met else '#f8d7da'}; padding: 15px; border-radius: 4px; margin: 20px 0;">
            <strong>{'✅ ALL CRITERIA MET' if all_met else '❌ SOME CRITERIA NOT MET'}</strong>
        </div>
        {criteria_html}
        """
    
    def _generate_detailed_results_html(self) -> str:
        """Generate detailed results section"""
        results_html = ""
        
        for i, result in enumerate(self.results, 1):
            status = result.get('status', 'unknown')
            status_class = 'success' if status == 'success' else 'failed'
            status_badge = f'<span class="badge {status_class}">{status.upper()}</span>'
            
            query_id = result.get('query_id', 'N/A')
            query = result.get('query', 'N/A')
            score = result.get('overall_score', 0)
            exec_time = result.get('execution_time', 0)
            
            # Detailed metrics
            metrics_html = ""
            if status == 'success':
                groundedness = result.get('groundedness', {})
                citation = result.get('citation', {})
                relevancy = result.get('answer_relevancy', {})
                
                metrics_html = f"""
                <table style="font-size: 14px; margin-top: 10px;">
                    <tr>
                        <th>Metric</th>
                        <th>Score</th>
                        <th>Details</th>
                    </tr>
                    <tr>
                        <td>Groundedness</td>
                        <td>{groundedness.get('score', 0):.2%}</td>
                        <td>{groundedness.get('supported_claims', 0)}/{groundedness.get('total_claims', 0)} claims supported</td>
                    </tr>
                    <tr>
                        <td>Citation F1</td>
                        <td>{citation.get('f1_score', 0):.2%}</td>
                        <td>P: {citation.get('precision', 0):.2%}, R: {citation.get('recall', 0):.2%}</td>
                    </tr>
                    <tr>
                        <td>Answer Relevancy</td>
                        <td>{relevancy.get('score', 0):.2%}</td>
                        <td>{relevancy.get('explanation', 'N/A')[:100]}</td>
                    </tr>
                </table>
                """
            else:
                metrics_html = f"<p style='color: #e74c3c;'>Error: {result.get('error', 'Unknown error')}</p>"
            
            results_html += f"""
            <div class="test-result {status_class}">
                <h4>Test #{i}: {query_id} {status_badge}</h4>
                <p><strong>Query:</strong> {query}</p>
                <p><strong>Overall Score:</strong> {score:.2%} | <strong>Time:</strong> {exec_time:.2f}s</p>
                {metrics_html}
            </div>
            """
        
        return f"""
        <h2>📋 Detailed Results</h2>
        <p>Showing results for {len(self.results)} test case(s)</p>
        {results_html}
        """


def generate_quick_summary(results_file: str):
    """Generate a quick text summary from JSON results"""
    import json
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    summary = data['summary']
    acceptance = data['acceptance_criteria']
    
    print("\n" + "="*70)
    print("📊 QUICK VALIDATION SUMMARY")
    print("="*70)
    print(f"Timestamp: {data['timestamp']}")
    print(f"Success Rate: {summary['success_rate']:.1%}")
    print(f"Avg Quality Score: {summary.get('avg_overall_score', 0):.2%}")
    print(f"Avg Execution Time: {summary.get('avg_execution_time', 0):.2f}s")
    print(f"Acceptance Criteria Met: {'✅ YES' if acceptance['all_criteria_met'] else '❌ NO'}")
    print("="*70)