"""
Alert Manager Module
Handles email and Slack notifications for data quality issues
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List
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

    def send_quality_alert(self, company_name: str, quality_report: Dict, anomalies: List[Dict]):
        """Send alert for quality issues"""
        logger.info(f"Sending quality alert for {company_name}")

        quality_score = quality_report.get('overall_quality_score', 0)
        error_count = len(quality_report.get('schema_validation', {}).get('errors', []))
        anomaly_count = len(anomalies)

        subject = f"Data Quality Alert: {company_name}"
        message = self._format_quality_message(company_name, quality_score, error_count, anomaly_count, anomalies)

        if self.email_enabled:
            self.send_email(subject, message)

        if self.slack_enabled:
            self.send_slack(subject, message)

    def send_bias_alert(self, company_name: str, bias_report: Dict):
        """Send alert for bias issues"""
        logger.info(f"Sending bias alert for {company_name}")

        fairness_score = bias_report.get('fairness_metrics', {}).get('overall_fairness_score', 0)
        findings = bias_report.get('bias_findings', [])

        subject = f"Bias Detection Alert: {company_name}"
        message = self._format_bias_message(company_name, fairness_score, findings)

        if self.email_enabled:
            self.send_email(subject, message)

        if self.slack_enabled:
            self.send_slack(subject, message)

    def send_email(self, subject: str, body: str):
        """Send email alert"""
        if not self.email_enabled or not self.email_sender or not self.email_recipient:
            logger.warning("Email alerts not properly configured")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_sender
            msg['To'] = self.email_recipient
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_sender, self.email_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"Email alert sent to {self.email_recipient}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

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
                logger.info("Slack alert sent successfully")
            else:
                logger.error(f"Slack alert failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

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

    # Test quality alert
    test_quality_report = {
        'overall_quality_score': 45,
        'schema_validation': {'errors': ['Missing field: ticker']},
    }

    test_anomalies = [
        {'severity': 'error', 'message': 'Insufficient news articles: 0'},
        {'severity': 'warning', 'message': 'Wikipedia content unusually short: 50 words'}
    ]

    print("Testing quality alert...")
    alert_mgr.send_quality_alert("Test Company", test_quality_report, test_anomalies)

    # Test bias alert
    test_bias_report = {
        'fairness_metrics': {'overall_fairness_score': 35},
        'bias_findings': [
            {'severity': 'high', 'description': 'Single source dominates with 80.0% of articles'},
            {'severity': 'medium', 'description': 'Only 2 unique sources found'}
        ]
    }

    print("Testing bias alert...")
    alert_mgr.send_bias_alert("Test Company", test_bias_report)

    print("\nAlert tests complete!")
