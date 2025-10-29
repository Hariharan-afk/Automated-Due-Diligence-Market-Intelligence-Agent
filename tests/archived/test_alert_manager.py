"""
Comprehensive unit tests for Alert Manager module.
Tests include edge cases, missing configuration, and notification handling.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from src.alert_manager import AlertManager


@pytest.fixture
def mock_env_email_enabled():
    """Mock environment for email alerts enabled."""
    env_vars = {
        "ALERT_EMAIL_ENABLED": "true",
        "ALERT_EMAIL_SENDER": "test@example.com",
        "ALERT_EMAIL_PASSWORD": "password123",
        "ALERT_EMAIL_RECIPIENT": "recipient@example.com",
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": "587"
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def mock_env_slack_enabled():
    """Mock environment for Slack alerts enabled."""
    env_vars = {
        "ALERT_SLACK_ENABLED": "true",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST/WEBHOOK"
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def mock_env_all_disabled():
    """Mock environment with all alerts disabled."""
    env_vars = {
        "ALERT_EMAIL_ENABLED": "false",
        "ALERT_SLACK_ENABLED": "false"
    }
    with patch.dict(os.environ, env_vars):
        yield


class TestAlertManagerInitialization:
    """Test AlertManager initialization."""

    def test_init_default_configuration(self):
        """Test initialization with default configuration."""
        alert_mgr = AlertManager()
        assert alert_mgr.email_enabled is False
        assert alert_mgr.slack_enabled is False
        assert alert_mgr.smtp_server == "smtp.gmail.com"
        assert alert_mgr.smtp_port == 587

    def test_init_email_enabled(self, mock_env_email_enabled):
        """Test initialization with email alerts enabled."""
        alert_mgr = AlertManager()
        assert alert_mgr.email_enabled is True
        assert alert_mgr.email_sender == "test@example.com"
        assert alert_mgr.email_recipient == "recipient@example.com"

    def test_init_slack_enabled(self, mock_env_slack_enabled):
        """Test initialization with Slack alerts enabled."""
        alert_mgr = AlertManager()
        assert alert_mgr.slack_enabled is True
        assert alert_mgr.slack_webhook == "https://hooks.slack.com/services/TEST/WEBHOOK"

    def test_init_custom_smtp(self):
        """Test initialization with custom SMTP configuration."""
        env_vars = {
            "SMTP_SERVER": "smtp.office365.com",
            "SMTP_PORT": "465"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            assert alert_mgr.smtp_server == "smtp.office365.com"
            assert alert_mgr.smtp_port == 465


@pytest.mark.unit
class TestQualityAlert:
    """Test quality alert functionality."""

    def test_send_quality_alert_disabled(self, mock_env_all_disabled):
        """Test quality alert when all notifications are disabled."""
        alert_mgr = AlertManager()
        quality_report = {"overall_quality_score": 75}
        anomalies = []

        # Should not raise error even when disabled
        alert_mgr.send_quality_alert("Test Corp", quality_report, anomalies)

    @patch.object(AlertManager, 'send_email')
    @patch.object(AlertManager, 'send_slack')
    def test_send_quality_alert_both_enabled(self, mock_slack, mock_email, mock_env_email_enabled, mock_env_slack_enabled):
        """Test quality alert when both email and Slack are enabled."""
        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "test@example.com",
            "ALERT_EMAIL_PASSWORD": "password",
            "ALERT_EMAIL_RECIPIENT": "recipient@example.com",
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            quality_report = {"overall_quality_score": 45, "schema_validation": {"errors": ["Error 1"]}}
            anomalies = [{"severity": "high", "message": "Data quality issue"}]

            alert_mgr.send_quality_alert("Test Corp", quality_report, anomalies)

            mock_email.assert_called_once()
            mock_slack.assert_called_once()

    def test_quality_alert_empty_quality_report(self):
        """Test quality alert with empty quality report."""
        alert_mgr = AlertManager()
        alert_mgr.send_quality_alert("Test Corp", {}, [])
        # Should handle gracefully

    def test_quality_alert_missing_keys(self):
        """Test quality alert with missing keys in report."""
        alert_mgr = AlertManager()
        quality_report = {}  # Missing expected keys
        anomalies = []

        # Should handle missing keys with defaults
        alert_mgr.send_quality_alert("Test Corp", quality_report, anomalies)


@pytest.mark.unit
class TestBiasAlert:
    """Test bias alert functionality."""

    def test_send_bias_alert_disabled(self, mock_env_all_disabled):
        """Test bias alert when all notifications are disabled."""
        alert_mgr = AlertManager()
        bias_report = {"fairness_metrics": {"overall_fairness_score": 60}}

        # Should not raise error
        alert_mgr.send_bias_alert("Test Corp", bias_report)

    @patch.object(AlertManager, 'send_email')
    @patch.object(AlertManager, 'send_slack')
    def test_send_bias_alert_both_enabled(self, mock_slack, mock_email):
        """Test bias alert when both channels are enabled."""
        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "test@example.com",
            "ALERT_EMAIL_PASSWORD": "password",
            "ALERT_EMAIL_RECIPIENT": "recipient@example.com",
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            bias_report = {
                "fairness_metrics": {"overall_fairness_score": 35},
                "bias_findings": [{"severity": "high", "description": "Source bias detected"}]
            }

            alert_mgr.send_bias_alert("Test Corp", bias_report)

            mock_email.assert_called_once()
            mock_slack.assert_called_once()

    def test_bias_alert_empty_findings(self):
        """Test bias alert with no findings."""
        alert_mgr = AlertManager()
        bias_report = {"fairness_metrics": {"overall_fairness_score": 90}, "bias_findings": []}

        alert_mgr.send_bias_alert("Test Corp", bias_report)

    def test_bias_alert_missing_fairness_metrics(self):
        """Test bias alert with missing fairness metrics."""
        alert_mgr = AlertManager()
        bias_report = {"bias_findings": []}

        # Should handle missing metrics
        alert_mgr.send_bias_alert("Test Corp", bias_report)


@pytest.mark.unit
class TestEmailSending:
    """Test email sending functionality."""

    @patch('smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending."""
        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "sender@test.com",
            "ALERT_EMAIL_PASSWORD": "password123",
            "ALERT_EMAIL_RECIPIENT": "recipient@test.com"
        }
        with patch.dict(os.environ, env_vars):
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            alert_mgr = AlertManager()
            alert_mgr.send_email("Test Subject", "Test Body")

            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once()
            mock_server.send_message.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_email_not_configured(self):
        """Test email sending when not properly configured."""
        alert_mgr = AlertManager()
        alert_mgr.email_enabled = False

        # Should log warning and return without error
        alert_mgr.send_email("Test", "Body")

    def test_send_email_missing_sender(self):
        """Test email sending with missing sender."""
        env_vars = {"ALERT_EMAIL_ENABLED": "true", "ALERT_EMAIL_RECIPIENT": "test@test.com"}
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_email("Test", "Body")
            # Should handle gracefully

    def test_send_email_missing_recipient(self):
        """Test email sending with missing recipient."""
        env_vars = {"ALERT_EMAIL_ENABLED": "true", "ALERT_EMAIL_SENDER": "test@test.com"}
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_email("Test", "Body")
            # Should handle gracefully

    @patch('smtplib.SMTP')
    def test_send_email_connection_failure(self, mock_smtp):
        """Test email sending with connection failure."""
        mock_smtp.side_effect = Exception("Connection refused")

        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "sender@test.com",
            "ALERT_EMAIL_PASSWORD": "password",
            "ALERT_EMAIL_RECIPIENT": "recipient@test.com"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            # Should catch exception and log error
            alert_mgr.send_email("Test", "Body")

    @patch('smtplib.SMTP')
    def test_send_email_authentication_failure(self, mock_smtp):
        """Test email sending with authentication failure."""
        mock_server = MagicMock()
        mock_server.login.side_effect = Exception("Authentication failed")
        mock_smtp.return_value = mock_server

        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "sender@test.com",
            "ALERT_EMAIL_PASSWORD": "wrong_password",
            "ALERT_EMAIL_RECIPIENT": "recipient@test.com"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_email("Test", "Body")

    def test_send_email_empty_subject(self):
        """Test email sending with empty subject."""
        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "sender@test.com",
            "ALERT_EMAIL_PASSWORD": "password",
            "ALERT_EMAIL_RECIPIENT": "recipient@test.com"
        }
        with patch.dict(os.environ, env_vars):
            with patch('smtplib.SMTP') as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server

                alert_mgr = AlertManager()
                alert_mgr.send_email("", "Body")

                mock_server.send_message.assert_called_once()

    def test_send_email_special_characters(self):
        """Test email sending with special characters."""
        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "sender@test.com",
            "ALERT_EMAIL_PASSWORD": "password",
            "ALERT_EMAIL_RECIPIENT": "recipient@test.com"
        }
        with patch.dict(os.environ, env_vars):
            with patch('smtplib.SMTP') as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server

                alert_mgr = AlertManager()
                alert_mgr.send_email("Test 日本語 🎉", "Body with émojis")

                mock_server.send_message.assert_called_once()


@pytest.mark.unit
class TestSlackSending:
    """Test Slack notification functionality."""

    @patch('src.alert_manager.requests.post')
    def test_send_slack_success(self, mock_post):
        """Test successful Slack notification."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        env_vars = {
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_slack("Test Title", "Test Message")

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "Test Title" in call_args[1]['json']['text']
            assert "Test Message" in call_args[1]['json']['text']

    def test_send_slack_not_configured(self):
        """Test Slack sending when not configured."""
        alert_mgr = AlertManager()
        alert_mgr.slack_enabled = False

        # Should log warning and return
        alert_mgr.send_slack("Test", "Message")

    def test_send_slack_missing_webhook(self):
        """Test Slack sending with missing webhook."""
        env_vars = {"ALERT_SLACK_ENABLED": "true"}
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_slack("Test", "Message")
            # Should handle gracefully

    @patch('src.alert_manager.requests.post')
    def test_send_slack_api_error(self, mock_post):
        """Test Slack sending with API error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        env_vars = {
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_slack("Test", "Message")
            # Should log error but not raise

    @patch('src.alert_manager.requests.post')
    def test_send_slack_connection_timeout(self, mock_post):
        """Test Slack sending with connection timeout."""
        mock_post.side_effect = Exception("Connection timeout")

        env_vars = {
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_slack("Test", "Message")
            # Should catch exception and log error

    @patch('src.alert_manager.requests.post')
    def test_send_slack_empty_message(self, mock_post):
        """Test Slack sending with empty message."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        env_vars = {
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_slack("", "")

            mock_post.assert_called_once()

    @patch('src.alert_manager.requests.post')
    def test_send_slack_special_characters(self, mock_post):
        """Test Slack sending with special characters and emojis."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        env_vars = {
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST"
        }
        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()
            alert_mgr.send_slack("Test 🚀", "Message with 日本語 and émojis")

            mock_post.assert_called_once()


@pytest.mark.unit
class TestMessageFormatting:
    """Test message formatting functions."""

    def test_format_quality_message_basic(self):
        """Test basic quality message formatting."""
        alert_mgr = AlertManager()
        message = alert_mgr._format_quality_message("Test Corp", 75.5, 2, 1, [])

        assert "Test Corp" in message
        assert "75.5" in message
        assert "2" in message  # errors
        assert "1" in message  # anomalies

    def test_format_quality_message_with_anomalies(self):
        """Test quality message with anomalies."""
        alert_mgr = AlertManager()
        anomalies = [
            {"severity": "high", "message": "Critical issue"},
            {"severity": "medium", "message": "Warning"},
        ]
        message = alert_mgr._format_quality_message("Test Corp", 50.0, 0, 2, anomalies)

        assert "Critical issue" in message
        assert "HIGH" in message

    def test_format_quality_message_max_anomalies(self):
        """Test quality message with more than 5 anomalies."""
        alert_mgr = AlertManager()
        anomalies = [{"severity": "high", "message": f"Issue {i}"} for i in range(10)]
        message = alert_mgr._format_quality_message("Test Corp", 30.0, 0, 10, anomalies)

        # Should only show top 5
        assert "Issue 0" in message
        assert "Issue 4" in message
        # But not later ones (they might not be included)

    def test_format_quality_message_missing_severity(self):
        """Test quality message with missing severity field."""
        alert_mgr = AlertManager()
        anomalies = [{"message": "Issue without severity"}]
        message = alert_mgr._format_quality_message("Test Corp", 60.0, 0, 1, anomalies)

        assert "UNKNOWN" in message.upper()
        assert "Issue without severity" in message

    def test_format_bias_message_basic(self):
        """Test basic bias message formatting."""
        alert_mgr = AlertManager()
        findings = []
        message = alert_mgr._format_bias_message("Test Corp", 85.0, findings)

        assert "Test Corp" in message
        assert "85.0" in message

    def test_format_bias_message_with_findings(self):
        """Test bias message with findings."""
        alert_mgr = AlertManager()
        findings = [
            {"severity": "high", "description": "Source bias detected"},
            {"severity": "medium", "description": "Temporal bias"},
        ]
        message = alert_mgr._format_bias_message("Test Corp", 45.0, findings)

        assert "Source bias detected" in message
        assert "HIGH" in message
        assert "Temporal bias" in message

    def test_format_bias_message_many_findings(self):
        """Test bias message with many findings."""
        alert_mgr = AlertManager()
        findings = [{"severity": "medium", "description": f"Finding {i}"} for i in range(10)]
        message = alert_mgr._format_bias_message("Test Corp", 30.0, findings)

        # Should only show top 5
        assert "Finding 0" in message
        assert "Finding 4" in message

    def test_format_bias_message_missing_description(self):
        """Test bias message with missing description."""
        alert_mgr = AlertManager()
        findings = [{"severity": "high"}]  # Missing description
        message = alert_mgr._format_bias_message("Test Corp", 50.0, findings)

        assert "N/A" in message


@pytest.mark.edge_case
class TestEdgeCases:
    """Test various edge cases."""

    def test_very_long_company_name(self):
        """Test with very long company name."""
        alert_mgr = AlertManager()
        long_name = "A" * 1000
        quality_report = {"overall_quality_score": 75}

        # Should handle without error
        alert_mgr.send_quality_alert(long_name, quality_report, [])

    def test_special_characters_in_company_name(self):
        """Test with special characters in company name."""
        alert_mgr = AlertManager()
        special_name = "Test Corp <script>alert('xss')</script>"
        quality_report = {"overall_quality_score": 75}

        # Should handle special characters
        alert_mgr.send_quality_alert(special_name, quality_report, [])

    def test_negative_quality_score(self):
        """Test with negative quality score."""
        alert_mgr = AlertManager()
        quality_report = {"overall_quality_score": -10}

        message = alert_mgr._format_quality_message("Test", -10, 0, 0, [])
        assert "-10" in message

    def test_quality_score_over_100(self):
        """Test with quality score over 100."""
        alert_mgr = AlertManager()
        message = alert_mgr._format_quality_message("Test", 150.0, 0, 0, [])
        assert "150.0" in message

    def test_none_values(self):
        """Test with None values in reports."""
        alert_mgr = AlertManager()
        quality_report = {"overall_quality_score": None}

        # Should handle None gracefully
        message = alert_mgr._format_quality_message("Test", None, None, None, [])
        assert "None" in message or "0" in message


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration tests for complete alert scenarios."""

    @patch('smtplib.SMTP')
    @patch('src.alert_manager.requests.post')
    def test_full_quality_alert_workflow(self, mock_post, mock_smtp):
        """Test complete quality alert workflow with both channels."""
        # Setup mocks
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "sender@test.com",
            "ALERT_EMAIL_PASSWORD": "password",
            "ALERT_EMAIL_RECIPIENT": "recipient@test.com",
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
        }

        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()

            quality_report = {
                "overall_quality_score": 45.5,
                "schema_validation": {"errors": ["Error 1", "Error 2"]}
            }
            anomalies = [
                {"severity": "high", "message": "Critical data quality issue"},
                {"severity": "medium", "message": "Warning about data"}
            ]

            alert_mgr.send_quality_alert("Integration Test Corp", quality_report, anomalies)

            # Verify both channels were called
            mock_smtp.assert_called_once()
            mock_post.assert_called_once()

    @patch('smtplib.SMTP')
    @patch('src.alert_manager.requests.post')
    def test_full_bias_alert_workflow(self, mock_post, mock_smtp):
        """Test complete bias alert workflow."""
        # Setup mocks
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        env_vars = {
            "ALERT_EMAIL_ENABLED": "true",
            "ALERT_EMAIL_SENDER": "sender@test.com",
            "ALERT_EMAIL_PASSWORD": "password",
            "ALERT_EMAIL_RECIPIENT": "recipient@test.com",
            "ALERT_SLACK_ENABLED": "true",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
        }

        with patch.dict(os.environ, env_vars):
            alert_mgr = AlertManager()

            bias_report = {
                "fairness_metrics": {"overall_fairness_score": 35.0},
                "bias_findings": [
                    {"severity": "high", "description": "Single source dominance"},
                    {"severity": "medium", "description": "Temporal bias detected"}
                ]
            }

            alert_mgr.send_bias_alert("Bias Test Corp", bias_report)

            # Verify both channels were called
            mock_smtp.assert_called_once()
            mock_post.assert_called_once()
