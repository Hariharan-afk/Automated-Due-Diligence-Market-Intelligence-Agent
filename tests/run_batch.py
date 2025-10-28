"""
Batch processing script to run the pipeline for multiple companies
Usage: python run_batch.py
"""

import subprocess
import sys
from datetime import datetime
import yaml

# Load companies from params.yaml
try:
    with open('params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    companies = params.get('companies', [])
except Exception as e:
    print(f"Error loading params.yaml: {e}")
    companies = [
        "Apple Inc",
        "Microsoft Corporation",
        "Alphabet Inc",
        "Tesla Inc",
        "NVIDIA Corporation",
        "Amazon.com Inc",
        "Meta Platforms Inc"
    ]

print("=" * 60)
print("BATCH PROCESSING MULTIPLE COMPANIES")
print("=" * 60)
print(f"\nTotal companies to process: {len(companies)}")
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

results = []
success_count = 0
fail_count = 0

# Process each company
for i, company in enumerate(companies, 1):
    print("-" * 60)
    print(f"[{i}/{len(companies)}] Processing: {company}")
    print("-" * 60)

    try:
        # Run the pipeline
        result = subprocess.run(
            [sys.executable, "scripts/run_pipeline.py", "--company", company],
            capture_output=False,
            text=True,
            timeout=600  # 10 minute timeout per company
        )

        if result.returncode == 0:
            print(f"✅ SUCCESS: {company}\n")
            success_count += 1
            results.append({"company": company, "status": "Success"})
        else:
            print(f"❌ FAILED: {company}\n")
            fail_count += 1
            results.append({"company": company, "status": "Failed"})

    except subprocess.TimeoutExpired:
        print(f"⏱️ TIMEOUT: {company} (exceeded 10 minutes)\n")
        fail_count += 1
        results.append({"company": company, "status": "Timeout"})

    except Exception as e:
        print(f"❌ ERROR: {company} - {e}\n")
        fail_count += 1
        results.append({"company": company, "status": f"Error: {e}"})

# Print summary
print("=" * 60)
print("BATCH PROCESSING SUMMARY")
print("=" * 60)
print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\nTotal Companies: {len(companies)}")
print(f"✅ Successful: {success_count}")
print(f"❌ Failed: {fail_count}")
print(f"\nSuccess Rate: {(success_count/len(companies)*100):.1f}%")

print("\nDetailed Results:")
print("-" * 60)
for result in results:
    status_icon = "✅" if result["status"] == "Success" else "❌"
    print(f"{status_icon} {result['company']:<30} {result['status']}")

print("\n" + "=" * 60)
print("All data saved to: data/company_data.db")
print("Quality reports: data/quality_reports/")
print("Bias reports: data/bias_reports/")
print("=" * 60)
