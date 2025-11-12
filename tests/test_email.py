"""
Test email configuration before running the full pipeline
Run this from your project root: python test_email.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env from: {env_path}\n")
else:
    print(f"⚠️  No .env file found at: {env_path}")
    print("Looking for environment variables in system...\n")

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

try:
    from alert_manager import AlertManager
except ImportError as e:
    print(f"❌ Failed to import AlertManager: {e}")
    print(f"Make sure alert_manager.py is in: {PROJECT_ROOT / 'src'}")
    sys.exit(1)


def print_config():
    """Print current configuration"""
    print("="*60)
    print("  Email Configuration")
    print("="*60)
    print(f"Enabled: {os.getenv('ALERT_EMAIL_ENABLED', 'NOT SET')}")
    print(f"Sender: {os.getenv('ALERT_EMAIL_SENDER', 'NOT SET')}")
    print(f"Recipient: {os.getenv('ALERT_EMAIL_RECIPIENT', 'NOT SET')}")
    print(f"SMTP Server: {os.getenv('SMTP_SERVER', 'NOT SET')}")
    print(f"SMTP Port: {os.getenv('SMTP_PORT', 'NOT SET')}")
    
    password = os.getenv('ALERT_EMAIL_PASSWORD')
    if password:
        # Show only first and last 2 chars of password
        masked = password[:2] + '*' * (len(password) - 4) + password[-2:] if len(password) > 4 else '****'
        print(f"Password: {masked} (set)")
    else:
        print("Password: NOT SET")
    print("="*60 + "\n")


def test_basic_email():
    """Test basic email sending"""
    print("🧪 Test 1: Basic Email")
    print("-" * 60)
    
    manager = AlertManager()
    
    if not manager.email_enabled:
        print("❌ Email alerts are DISABLED")
        print("   Set ALERT_EMAIL_ENABLED=true in your .env file\n")
        return False
    
    print("📧 Sending basic test email...")
    success = manager.send_email(
        subject="🧪 Test Email from Airflow Pipeline",
        body="If you're reading this, your email configuration is working correctly!",
        html_body=f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #4caf50;">✅ Test Email Success!</h2>
            <p>If you're reading this, your email configuration is working correctly!</p>
            <hr>
            <p><strong>Configuration Details:</strong></p>
            <ul>
                <li>SMTP Server: {os.getenv('SMTP_SERVER')}</li>
                <li>SMTP Port: {os.getenv('SMTP_PORT')}</li>
                <li>Sender: {os.getenv('ALERT_EMAIL_SENDER')}</li>
                <li>Recipient: {os.getenv('ALERT_EMAIL_RECIPIENT')}</li>
            </ul>
            <hr>
            <p style="color: #777; font-size: 12px;">
                This is a test email from the Company Research Data Pipeline
            </p>
        </body>
        </html>
        """
    )
    
    if success:
        print(f"✅ Test email sent successfully to: {os.getenv('ALERT_EMAIL_RECIPIENT')}")
        print("   Check your inbox!\n")
        return True
    else:
        print("❌ Failed to send test email")
        print("   Check the error messages above\n")
        return False


def test_quality_alert():
    """Test quality alert email"""
    print("🧪 Test 2: Quality Alert Email")
    print("-" * 60)
    
    manager = AlertManager()
    
    if not manager.email_enabled:
        print("❌ Email alerts are DISABLED - skipping test\n")
        return False
    
    print("📧 Sending test quality alert...")
    success = manager.send_combined_alert(
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
            'fairness_score': '72.3/100'
        }
    )
    
    if success:
        print(f"✅ Quality alert sent successfully to: {os.getenv('ALERT_EMAIL_RECIPIENT')}")
        print("   This email shows what alerts look like\n")
        return True
    else:
        print("❌ Failed to send quality alert\n")
        return False


def test_success_notification():
    """Test success notification email"""
    print("🧪 Test 3: Success Notification Email")
    print("-" * 60)
    
    manager = AlertManager()
    
    if not manager.email_enabled:
        print("❌ Email alerts are DISABLED - skipping test\n")
        return False
    
    print("📧 Sending test success notification...")
    success = manager.send_success_notification(
        company_name="Apple Inc. (TEST)",
        quality_score=95.2,
        article_count=50,
        sec_count=5
    )
    
    if success:
        print(f"✅ Success notification sent to: {os.getenv('ALERT_EMAIL_RECIPIENT')}")
        print("   This email shows what success looks like\n")
        return True
    else:
        print("❌ Failed to send success notification\n")
        return False


def test_old_format():
    """Test the old quality/bias alert format"""
    print("🧪 Test 4: Legacy Alert Format")
    print("-" * 60)
    
    manager = AlertManager()
    
    if not manager.email_enabled:
        print("❌ Email alerts are DISABLED - skipping test\n")
        return False
    
    print("📧 Sending legacy quality alert...")
    
    test_quality_report = {
        'overall_quality_score': 45,
        'schema_validation': {'errors': ['Missing field: ticker']},
    }

    test_anomalies = [
        {'severity': 'error', 'message': 'Insufficient news articles: 0'},
        {'severity': 'warning', 'message': 'Wikipedia content unusually short: 50 words'}
    ]
    
    manager.send_quality_alert("Test Company", test_quality_report, test_anomalies)
    
    print("📧 Sending legacy bias alert...")
    
    test_bias_report = {
        'fairness_metrics': {'overall_fairness_score': 35},
        'bias_findings': [
            {'severity': 'high', 'description': 'Single source dominates with 80.0% of articles'},
            {'severity': 'medium', 'description': 'Only 2 unique sources found'}
        ]
    }
    
    manager.send_bias_alert("Test Company", test_bias_report)
    
    print("✅ Legacy format alerts sent\n")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  Email Configuration Test Suite")
    print("  Company Research Data Pipeline")
    print("="*60 + "\n")
    
    # Show configuration
    print_config()
    
    # Check if email is enabled
    if os.getenv('ALERT_EMAIL_ENABLED', '').lower() != 'true':
        print("⚠️  WARNING: ALERT_EMAIL_ENABLED is not set to 'true'")
        print("   Emails will not be sent even if configuration is correct\n")
        
        response = input("Would you like to continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...\n")
            return
    
    # Run tests
    results = []
    
    # Test 1: Basic email
    results.append(("Basic Email", test_basic_email()))
    
    if results[0][1]:  # If basic test passed, run others
        input("\nPress Enter to test quality alert email...")
        results.append(("Quality Alert", test_quality_alert()))
        
        input("\nPress Enter to test success notification email...")
        results.append(("Success Notification", test_success_notification()))
        
        input("\nPress Enter to test legacy alert formats...")
        results.append(("Legacy Formats", test_old_format()))
    
    # Summary
    print("\n" + "="*60)
    print("  Test Summary")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
    
    print("="*60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    if passed_count == total_count:
        print(f"\n🎉 All tests passed! ({passed_count}/{total_count})")
        print("Your email configuration is working correctly!")
    else:
        print(f"\n⚠️  Some tests failed ({passed_count}/{total_count} passed)")
        print("Please check your .env configuration and Gmail App Password")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user\n")
    except Exception as e:
        print(f"\n❌ Test suite error: {e}\n")
        import traceback
        traceback.print_exc()