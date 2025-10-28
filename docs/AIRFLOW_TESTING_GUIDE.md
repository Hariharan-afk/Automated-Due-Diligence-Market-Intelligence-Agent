# Airflow DAG Testing Guide

**Complete step-by-step guide to test the `company_research_pipeline` DAG**

---

## Prerequisites

Before testing, ensure you have:
- Python 3.8+ installed
- Virtual environment activated
- `.env` file configured with API keys (NewsAPI, SEC API)
- SQLite database path configured

---

## Step 1: Install Airflow Dependencies

```bash
# Install Airflow and dependencies
pip install apache-airflow==2.8.0
pip install apache-airflow-providers-amazon==8.11.0

# Or install from requirements.txt
pip install -r requirements.txt
```

**Windows-specific note**: If you encounter issues, you may need:
```bash
# Set environment variable for Windows
set AIRFLOW_HOME=%CD%\airflow_home

# Or in PowerShell
$env:AIRFLOW_HOME = "$PWD\airflow_home"
```

---

## Step 2: Initialize Airflow

```bash
# Set Airflow home directory (IMPORTANT!)
export AIRFLOW_HOME=$(pwd)/airflow_home    # Linux/Mac
set AIRFLOW_HOME=%CD%\airflow_home         # Windows CMD
$env:AIRFLOW_HOME = "$PWD\airflow_home"    # Windows PowerShell

# Initialize the Airflow database
airflow db init

# Create an admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
```

**Note**: Remember your username (`admin`) and password (`admin`) for login.

---

## Step 3: Configure DAG Path

Airflow needs to know where your DAGs are located.

### Option A: Create Symbolic Link (Recommended)
```bash
# Create symbolic link from airflow_home/dags to your dags folder
cd airflow_home
mklink /D dags ..\dags                # Windows
ln -s ../dags dags                     # Linux/Mac
```

### Option B: Copy DAGs folder
```bash
# Copy your dags folder to airflow_home
cp -r dags airflow_home/dags          # Linux/Mac
xcopy dags airflow_home\dags /E /I    # Windows
```

### Option C: Modify airflow.cfg
Edit `airflow_home/airflow.cfg`:
```ini
[core]
dags_folder = C:\Users\suraj\Hariharan\Assignments\Term3\MLOps\Project\Automated-Due-Diligence-Market-Intelligence-Agent\data_pipeline_main\dags
```

---

## Step 4: Configure Airflow Settings (Optional but Recommended)

Edit `airflow_home/airflow.cfg`:

```ini
[core]
# Load examples (set to False to hide example DAGs)
load_examples = False

# Parallelism settings
parallelism = 4
dag_concurrency = 2
max_active_runs_per_dag = 1

[webserver]
# Web server port
web_server_port = 8080

[smtp]
# Email settings (if you want email alerts)
smtp_host = smtp.gmail.com
smtp_starttls = True
smtp_ssl = False
smtp_user = your-email@gmail.com
smtp_password = your-app-password
smtp_port = 587
smtp_mail_from = your-email@gmail.com
```

---

## Step 5: Set Airflow Variables

Your DAG uses an Airflow Variable called `target_company`. Set it:

```bash
# Set the company to research
airflow variables set target_company "Apple Inc."

# Or use ticker symbol
airflow variables set target_company "AAPL"

# Verify it's set
airflow variables get target_company
```

---

## Step 6: Start Airflow Services

You need to run TWO separate terminal windows:

### Terminal 1: Start Webserver
```bash
# Set AIRFLOW_HOME again
export AIRFLOW_HOME=$(pwd)/airflow_home    # Linux/Mac
set AIRFLOW_HOME=%CD%\airflow_home         # Windows CMD
$env:AIRFLOW_HOME = "$PWD\airflow_home"    # Windows PowerShell

# Start webserver
airflow webserver --port 8080
```

### Terminal 2: Start Scheduler
```bash
# Set AIRFLOW_HOME again (in new terminal)
export AIRFLOW_HOME=$(pwd)/airflow_home    # Linux/Mac
set AIRFLOW_HOME=%CD%\airflow_home         # Windows CMD
$env:AIRFLOW_HOME = "$PWD\airflow_home"    # Windows PowerShell

# Start scheduler
airflow scheduler
```

**Wait 30-60 seconds** for both services to fully start.

---

## Step 7: Access Airflow Web UI

1. Open your browser and go to: **http://localhost:8080**
2. Login with:
   - **Username**: `admin`
   - **Password**: `admin` (or whatever you set)

You should see the Airflow dashboard.

---

## Step 8: Verify DAG is Loaded

In the Airflow UI:

1. Look for DAG named: **`company_research_pipeline`**
2. It should have tags: `research`, `data-pipeline`, `mlops`
3. Check the status:
   - ✅ Green = DAG loaded successfully
   - ❌ Red = Import error (check logs)

If you see red/errors:
```bash
# Check DAG for syntax errors
python dags/company_research_dag.py

# Check Airflow import errors
airflow dags list-import-errors
```

---

## Step 9: Test the DAG

### Method 1: Manual Trigger (Recommended for Testing)

1. In Airflow UI, find `company_research_pipeline`
2. Click the **Play button** (▶) on the right to trigger manually
3. Confirm the trigger
4. Click on the DAG name to see the run

### Method 2: Command Line Trigger

```bash
# Trigger the DAG manually
airflow dags trigger company_research_pipeline

# Trigger with specific execution date
airflow dags trigger company_research_pipeline --exec-date 2025-10-27
```

### Method 3: Test Individual Tasks

```bash
# Test a specific task without dependencies
airflow tasks test company_research_pipeline initialize_database 2025-10-27

# Test data acquisition task
airflow tasks test company_research_pipeline acquire_company_data 2025-10-27

# Test preprocessing task
airflow tasks test company_research_pipeline preprocess_data 2025-10-27
```

---

## Step 10: Monitor Execution

### View in Airflow UI

1. Click on the DAG name: **`company_research_pipeline`**
2. You'll see different views:

#### **Graph View** (Shows task dependencies)
- Click "Graph" tab
- See task relationships visually
- Green = Success, Red = Failed, Light Blue = Running

#### **Gantt View** (Shows timeline - THIS IS WHAT YOU NEED!)
- Click "Gantt" tab
- See execution timeline
- Identify bottlenecks visually
- Longer bars = slower tasks

#### **Tree View** (Shows multiple runs)
- Click "Tree" tab
- See historical runs
- Compare performance across runs

### View Task Logs

To debug failures:
1. Click on a task box (any colored square)
2. Click "Log" button
3. View detailed execution logs

---

## Step 11: Capture Gantt Chart for Documentation

Once the DAG runs successfully:

1. Go to **Graph View** in Airflow UI
2. Click on **"Gantt"** tab
3. Wait for the entire DAG to complete
4. Take a screenshot of the Gantt chart showing:
   - Task names
   - Duration bars
   - Total execution time
   - Color coding (green/red)

5. Add screenshot to your documentation:
   - Save as `docs/gantt_chart_screenshot.png`
   - Reference in AIRFLOW_GANTT_SUMMARY.md

---

## Step 12: Verify Results

After successful run, check:

### 1. Database
```bash
# Open SQLite database
sqlite3 data/pipeline.db

# Check inserted data
SELECT COUNT(*) FROM companies;
SELECT COUNT(*) FROM articles;
SELECT COUNT(*) FROM sec_filings;

# Exit
.exit
```

### 2. Processed Data
```bash
# Check processed files
ls -l data/processed/

# View sample processed data
cat data/processed/Apple_processed_*.json | head -50
```

### 3. Metrics and Reports
```bash
# Check quality reports
ls -l data/quality_reports/

# Check bias reports
ls -l data/bias_reports/

# View DVC metrics
dvc metrics show
```

---

## Step 13: Performance Analysis

### Extract Timing Data from Gantt Chart

In the Gantt view, note down:
- **initialize_database**: ~1s
- **acquire_company_data**: ~60s (BOTTLENECK!)
- **preprocess_data**: ~10s
- **validate_schema**: ~5s
- **detect_anomalies**: ~3s
- **detect_bias**: ~5s
- **store_to_database**: ~5s
- **generate_statistics**: ~2s
- **check_and_alert**: ~1s

**Total**: ~90-120 seconds

This confirms the analysis in AIRFLOW_GANTT_SUMMARY.md!

---

## Troubleshooting Common Issues

### Issue 1: DAG Not Appearing

**Problem**: DAG doesn't show up in UI

**Solution**:
```bash
# Check if DAG folder is correct
airflow dags list

# Check for import errors
airflow dags list-import-errors

# Manually parse DAG file
python dags/company_research_dag.py
```

### Issue 2: Import Errors

**Problem**: "Module not found" errors

**Solution**:
```bash
# Ensure all dependencies installed
pip install -r requirements.txt

# Check if src modules are accessible
python -c "import sys; sys.path.append('src'); from data_acquisition import DataAcquisitionPipeline"
```

### Issue 3: Database Locked

**Problem**: "database is locked" error

**Solution**:
```bash
# Close any open connections
# Use this in DAG instead of global connection
# (Already implemented in the DAG)
```

### Issue 4: API Key Errors

**Problem**: "401 Unauthorized" or missing API keys

**Solution**:
```bash
# Verify .env file exists
cat .env | grep API_KEY

# Test API keys manually
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('NEWSAPI_KEY'))"
```

### Issue 5: Scheduler Not Picking Up DAG

**Problem**: DAG schedule doesn't trigger automatically

**Solution**:
```bash
# Unpause the DAG
airflow dags unpause company_research_pipeline

# Check scheduler logs
tail -f airflow_home/logs/scheduler/latest/*.log
```

### Issue 6: Tasks Stuck in "Running"

**Problem**: Tasks never complete

**Solution**:
```bash
# Check task logs in UI
# Or via command line:
airflow tasks state company_research_pipeline acquire_company_data 2025-10-27

# Clear stuck task
airflow tasks clear company_research_pipeline --yes
```

---

## Quick Test Command Summary

For quick testing without UI:

```bash
# 1. Set environment
export AIRFLOW_HOME=$(pwd)/airflow_home

# 2. List DAGs
airflow dags list

# 3. Test DAG validation
python dags/company_research_dag.py

# 4. Test specific task
airflow tasks test company_research_pipeline initialize_database 2025-10-27

# 5. Trigger full DAG run
airflow dags trigger company_research_pipeline

# 6. Check run status
airflow dags list-runs -d company_research_pipeline
```

---

## Expected Output (Successful Run)

When everything works, you should see:

### In Airflow UI:
- ✅ All 9 tasks green in Graph View
- ✅ Gantt chart showing ~90-120s total execution
- ✅ No red tasks or errors
- ✅ XCom data passed between tasks

### In Database:
```sql
SELECT * FROM companies LIMIT 1;
-- Should show Apple Inc. with metadata

SELECT COUNT(*) FROM articles;
-- Should show ~20 news articles

SELECT COUNT(*) FROM sec_filings;
-- Should show 2 filings (10-K and 10-Q)
```

### In Files:
```
data/processed/Apple_processed_*.json  (exists)
data/quality_reports/Apple_quality_*.json  (exists)
data/bias_reports/Apple_bias_*.json  (exists)
data/metrics/*.json  (updated with new metrics)
```

---

## Next Steps After Successful Test

1. **Capture Gantt Chart Screenshot**
   - Save as documentation evidence
   - Add to AIRFLOW_GANTT_SUMMARY.md

2. **Compare Results with DVC Pipeline**
   ```bash
   # Run DVC pipeline for comparison
   dvc repro

   # Compare metrics
   dvc metrics show
   dvc plots show
   ```

3. **Test with Different Company**
   ```bash
   # Change target company
   airflow variables set target_company "Microsoft"

   # Trigger new run
   airflow dags trigger company_research_pipeline
   ```

4. **Test Error Handling**
   - Try with invalid company name
   - Test with missing API keys
   - Verify retry logic works

5. **Test Alerting**
   - Configure SMTP settings
   - Trigger a failing task
   - Verify email alert received

---

## Stopping Airflow

When you're done testing:

1. Stop the scheduler: Press `Ctrl+C` in Terminal 2
2. Stop the webserver: Press `Ctrl+C` in Terminal 1

Or force kill:
```bash
# Find Airflow processes
ps aux | grep airflow         # Linux/Mac
tasklist | findstr airflow    # Windows

# Kill processes
pkill -f "airflow webserver"  # Linux/Mac
pkill -f "airflow scheduler"  # Linux/Mac
```

---

## Checklist for Successful DAG Test

- [ ] Airflow installed and initialized
- [ ] Admin user created
- [ ] DAG folder configured correctly
- [ ] `target_company` variable set
- [ ] Webserver running on port 8080
- [ ] Scheduler running in background
- [ ] DAG appears in UI (green status)
- [ ] Manual trigger works
- [ ] All 9 tasks execute successfully
- [ ] Gantt chart shows execution timeline
- [ ] Database populated with data
- [ ] Processed files created
- [ ] Metrics and reports generated
- [ ] Screenshot of Gantt chart captured
- [ ] Timing matches AIRFLOW_GANTT_SUMMARY.md analysis

---

## Additional Resources

- [AIRFLOW_SETUP.md](AIRFLOW_SETUP.md) - Complete Airflow setup guide
- [AIRFLOW_GANTT_SUMMARY.md](AIRFLOW_GANTT_SUMMARY.md) - Performance analysis
- [Airflow Documentation](https://airflow.apache.org/docs/apache-airflow/stable/)
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)

---

**Last Updated**: October 27, 2025
**DAG Version**: company_research_pipeline v1.0
**Airflow Version**: 2.8.0
