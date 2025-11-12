"""
Alert Manager Module
Handles email and Slack notifications for data quality issues
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertManager:
    """Manage alerts for data quality issues"""

    def __init__(self):
        # Email configuration
        self.email_enabled = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true"
        self.email_sender = os.getenv("ALERT_EMAIL_SENDER", "")
        self.email_password = os.getenv("ALERT_EMAIL_PASSWORD", "")
        self.email_recipient = os.getenv("ALERT_EMAIL_RECIPIENT", "")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))

        # Slack configuration
        self.slack_enabled = os.getenv("ALERT_SLACK_ENABLED", "false").lower() == "true"
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
        
        # Log configuration status
        if self.email_enabled:
            logger.info(f"📧 Email alerts enabled - sending to {self.email_recipient}")
        else:
            logger.info("📧 Email alerts disabled")

    def send_quality_alert(self, company_name: str, quality_report: Dict, anomalies: List[Dict]):
        """Send alert for quality issues"""
        logger.info(f"🔔 Sending quality alert for {company_name}")

        quality_score = quality_report.get('overall_quality_score', 0)
        error_count = len(quality_report.get('schema_validation', {}).get('errors', []))
        anomaly_count = len(anomalies)

        subject = f"🚨 Data Quality Alert: {company_name} - Score: {quality_score:.1f}/100"
        
        # Send HTML email
        html_message = self._format_quality_html(company_name, quality_score, error_count, anomaly_count, anomalies)
        text_message = self._format_quality_message(company_name, quality_score, error_count, anomaly_count, anomalies)

        if self.email_enabled:
            self.send_email(subject, text_message, html_message)

        if self.slack_enabled:
            self.send_slack(subject, text_message)

    def send_bias_alert(self, company_name: str, bias_report: Dict):
        """Send alert for bias issues"""
        logger.info(f"🔔 Sending bias alert for {company_name}")

        fairness_score = bias_report.get('fairness_metrics', {}).get('overall_fairness_score', 0)
        findings = bias_report.get('bias_findings', [])

        subject = f"⚖️ Bias Detection Alert: {company_name} - Fairness: {fairness_score:.1f}/100"
        
        # Send HTML email
        html_message = self._format_bias_html(company_name, fairness_score, findings)
        text_message = self._format_bias_message(company_name, fairness_score, findings)

        if self.email_enabled:
            self.send_email(subject, text_message, html_message)

        if self.slack_enabled:
            self.send_slack(subject, text_message)

    def send_combined_alert(
        self, 
        company_name: str, 
        quality_score: float,
        anomaly_count: int,
        alerts: List[str],
        additional_info: Optional[Dict] = None
    ):
        """
        Send a combined quality alert with all metrics
        This is the main method for DAG integration
        """
        logger.info(f"🔔 Sending combined alert for {company_name}")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Build HTML email
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #d32f2f; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f5f5f5; padding: 20px; border-radius: 0 0 5px 5px; }}
                .alert-item {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }}
                .metric {{ background-color: white; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .metric-label {{ font-weight: bold; color: #555; }}
                .metric-value {{ font-size: 24px; color: #d32f2f; }}
                .footer {{ text-align: center; color: #777; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 Data Quality Alert</h1>
                    <p><strong>Company:</strong> {company_name}</p>
                    <p><strong>Time:</strong> {timestamp}</p>
                </div>
                
                <div class="content">
                    <h2>Alerts Triggered:</h2>
                    {''.join(f'<div class="alert-item">{alert}</div>' for alert in alerts)}
                    
                    <h2>Quality Metrics:</h2>
                    <div class="metric">
                        <div class="metric-label">Quality Score</div>
                        <div class="metric-value">{quality_score:.1f}/100</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">Anomalies Detected</div>
                        <div class="metric-value">{anomaly_count}</div>
                    </div>
        """
        
        # Add additional info if provided
        if additional_info:
            html_message += "<h2>Additional Information:</h2>"
            for key, value in additional_info.items():
                html_message += f"""
                <div class="metric">
                    <div class="metric-label">{key.replace('_', ' ').title()}</div>
                    <div class="metric-value">{value}</div>
                </div>
                """
        
        html_message += """
                </div>
                
                <div class="footer">
                    <p>This is an automated alert from the Company Research Pipeline</p>
                    <p>Please review the Airflow logs for more details</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Build text version
        text_message = f"""Data Quality Alert

Company: {company_name}
Timestamp: {timestamp}

Alerts Triggered:
{''.join(f'  - {alert}' + chr(10) for alert in alerts)}

Quality Metrics:
- Quality Score: {quality_score:.1f}/100
- Anomalies Detected: {anomaly_count}
"""
        
        if additional_info:
            text_message += "\nAdditional Information:\n"
            for key, value in additional_info.items():
                text_message += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        text_message += "\nAction Required: Review and address data quality issues before proceeding.\n"
        
        subject = f"🚨 Data Quality Alert: {company_name} - Score: {quality_score:.1f}/100"
        
        if self.email_enabled:
            success = self.send_email(subject, text_message, html_message)
            return success
        
        if self.slack_enabled:
            self.send_slack(subject, text_message)
            return True
        
        logger.warning("⚠️ No alert channels enabled")
        return False

    def send_success_notification(
        self,
        company_name: str,
        quality_score: float,
        article_count: int,
        sec_count: int
    ):
        """Send success notification when pipeline completes successfully"""
        logger.info(f"✅ Sending success notification for {company_name}")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4caf50; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f5f5f5; padding: 20px; border-radius: 0 0 5px 5px; }}
                .metric {{ background-color: white; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .metric-label {{ font-weight: bold; color: #555; }}
                .metric-value {{ font-size: 24px; color: #4caf50; }}
                .footer {{ text-align: center; color: #777; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Pipeline Success</h1>
                    <p><strong>Company:</strong> {company_name}</p>
                    <p><strong>Time:</strong> {timestamp}</p>
                </div>
                
                <div class="content">
                    <h2>Pipeline Summary:</h2>
                    
                    <div class="metric">
                        <div class="metric-label">Quality Score</div>
                        <div class="metric-value">{quality_score:.1f}/100</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">Articles Processed</div>
                        <div class="metric-value">{article_count}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">SEC Filings Processed</div>
                        <div class="metric-value">{sec_count}</div>
                    </div>
                </div>
                
                <div class="footer">
                    <p>This is an automated notification from the Company Research Pipeline</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_message = f"""Pipeline Success

Company: {company_name}
Timestamp: {timestamp}

Pipeline Summary:
- Quality Score: {quality_score:.1f}/100
- Articles Processed: {article_count}
- SEC Filings Processed: {sec_count}

All quality checks passed successfully!
"""
        
        subject = f"✅ Pipeline Success: {company_name} - Quality: {quality_score:.1f}/100"
        
        if self.email_enabled:
            return self.send_email(subject, text_message, html_message)
        
        return False

    def send_email(self, subject: str, body: str, html_body: Optional[str] = None):
        """Send email alert with optional HTML body"""
        if not self.email_enabled or not self.email_sender or not self.email_recipient:
            logger.warning("📧 Email alerts not properly configured")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_sender
            msg['To'] = self.email_recipient
            msg['Subject'] = subject

            # Attach plain text version
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach HTML version if provided
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_sender, self.email_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"✅ Email alert sent to {self.email_recipient}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email alert: {e}", exc_info=True)
            return False

    def send_slack(self, title: str, message: str):
        """Send Slack alert"""
        if not self.slack_enabled or not self.slack_webhook:
            logger.warning("Slack alerts not properly configured")
            return

        try:
            import requests

            payload = {
                "text": f"*{title}*\n{message}",
                "username": "Data Pipeline Bot",
                "icon_emoji": ":robot_face:"
            }

            response = requests.post(
                self.slack_webhook,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                logger.info("✅ Slack alert sent successfully")
            else:
                logger.error(f"❌ Slack alert failed: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Failed to send Slack alert: {e}")

    def _format_quality_html(self, company: str, score: float, errors: int, anomalies: int, anomaly_list: List[Dict]) -> str:
        """Format quality alert as HTML"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #d32f2f; color: white; padding: 15px; }}
                .metric {{ background-color: #f5f5f5; padding: 10px; margin: 10px 0; }}
                .anomaly {{ background-color: #fff3cd; padding: 8px; margin: 5px 0; border-left: 4px solid #ffc107; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🚨 Data Quality Alert</h2>
                    <p>Company: {company}</p>
                    <p>Time: {timestamp}</p>
                </div>
                
                <div class="metric">
                    <strong>Quality Score:</strong> {score:.1f}/100
                </div>
                <div class="metric">
                    <strong>Validation Errors:</strong> {errors}
                </div>
                <div class="metric">
                    <strong>Anomalies Detected:</strong> {anomalies}
                </div>
                
                <h3>Top Anomalies:</h3>
        """
        
        for anomaly in anomaly_list[:5]:
            severity = anomaly.get('severity', 'unknown').upper()
            message = anomaly.get('message', 'N/A')
            html += f'<div class="anomaly">[{severity}] {message}</div>\n'
        
        html += """
            </div>
        </body>
        </html>
        """
        
        return html

    def _format_quality_message(self, company: str, score: float, errors: int, anomalies: int, anomaly_list: List[Dict]) -> str:
        """Format quality alert message"""
        message = f"""Data Quality Alert

Company: {company}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Quality Metrics:
- Quality Score: {score:.1f}/100
- Validation Errors: {errors}
- Anomalies Detected: {anomalies}

"""
        if anomaly_list:
            message += "Anomaly Details:\n"
            for anomaly in anomaly_list[:5]:  # Top 5
                message += f"  - [{anomaly.get('severity', 'unknown').upper()}] {anomaly.get('message', 'N/A')}\n"

        message += "\nAction Required: Review and address data quality issues before proceeding.\n"

        return message

    def _format_bias_html(self, company: str, fairness_score: float, findings: List[Dict]) -> str:
        """Format bias alert as HTML"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #ff9800; color: white; padding: 15px; }}
                .metric {{ background-color: #f5f5f5; padding: 10px; margin: 10px 0; }}
                .finding {{ background-color: #ffe0b2; padding: 8px; margin: 5px 0; border-left: 4px solid #ff9800; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>⚖️ Bias Detection Alert</h2>
                    <p>Company: {company}</p>
                    <p>Time: {timestamp}</p>
                </div>
                
                <div class="metric">
                    <strong>Fairness Score:</strong> {fairness_score:.1f}/100
                </div>
                <div class="metric">
                    <strong>Issues Found:</strong> {len(findings)}
                </div>
                
                <h3>Top Findings:</h3>
        """
        
        for finding in findings[:5]:
            severity = finding.get('severity', 'unknown').upper()
            description = finding.get('description', 'N/A')
            html += f'<div class="finding">[{severity}] {description}</div>\n'
        
        html += """
            </div>
        </body>
        </html>
        """
        
        return html

    def _format_bias_message(self, company: str, fairness_score: float, findings: List[Dict]) -> str:
        """Format bias alert message"""
        message = f"""Bias Detection Alert

Company: {company}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Bias Metrics:
- Fairness Score: {fairness_score:.1f}/100
- Issues Found: {len(findings)}

"""
        if findings:
            message += "Bias Findings:\n"
            for finding in findings[:5]:  # Top 5
                message += f"  - [{finding.get('severity', 'unknown').upper()}] {finding.get('description', 'N/A')}\n"

        message += "\nAction Required: Review and mitigate bias issues in data collection.\n"

        return message


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Initialize alert manager
    alert_mgr = AlertManager()

    # Test combined alert (new method for DAG integration)
    print("Testing combined alert...")
    alert_mgr.send_combined_alert(
        company_name="Apple Inc. (TEST)",
        quality_score=65.5,
        anomaly_count=8,
        alerts=[
            "⚠️ Low quality score: 65.5/100 (threshold: 70)",
            "⚠️ High anomaly count: 8 (threshold: 5)",
            "⚠️ Bias detected - Fairness score: 72.3/100"
        ],
        additional_info={
            'articles_processed': 42,
            'sec_filings_processed': 3,
            'bias_detected': True,
            'fairness_score': 72.3
        }
    )

    # Test quality alert
    test_quality_report = {
        'overall_quality_score': 45,
        'schema_validation': {'errors': ['Missing field: ticker']},
    }

    test_anomalies = [
        {'severity': 'error', 'message': 'Insufficient news articles: 0'},
        {'severity': 'warning', 'message': 'Wikipedia content unusually short: 50 words'}
    ]

    print("\nTesting quality alert...")
    alert_mgr.send_quality_alert("Test Company", test_quality_report, test_anomalies)

    # Test bias alert
    test_bias_report = {
        'fairness_metrics': {'overall_fairness_score': 35},
        'bias_findings': [
            {'severity': 'high', 'description': 'Single source dominates with 80.0% of articles'},
            {'severity': 'medium', 'description': 'Only 2 unique sources found'}
        ]
    }

    print("\nTesting bias alert...")
    alert_mgr.send_bias_alert("Test Company", test_bias_report)

    # Test success notification
    print("\nTesting success notification...")
    alert_mgr.send_success_notification(
        company_name="Apple Inc. (TEST)",
        quality_score=95.2,
        article_count=50,
        sec_count=5
    )

    print("\n✅ Alert tests complete!")