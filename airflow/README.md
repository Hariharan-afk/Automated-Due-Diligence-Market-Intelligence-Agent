# Airflow Setup & Usage Guide

## 🚀 Quick Start

### 1. Install Airflow

```bash
# Create separate venv for Airflow
python -m venv .venv_airflow

# Activate
.venv_airflow\Scripts\activate  # Windows
# source .venv_airflow/bin/activate  # Linux/Mac

# Install Airflow 2.8.1
pip install "apache-airflow==2.8.1" --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.8.1/constraints-3.11.txt"

# Install providers
pip install apache-airflow-providers-google apache-airflow-providers-postgres
```

### 2. Initialize Airflow

```bash
# Set Airflow home (important!)
set AIRFLOW_HOME=C:\Users\suraj\Hariharan\Assignments\Term3\MLOps\MLOps-Project\Automated_Due_Dillegence_Market_Intelligence_Agent_v2\Data_Pipeline\airflow

# Initialize DB
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
```

### 3. Configure Airflow

Edit `airflow/airflow.cfg`:

```ini
[core]
dags_folder = C:\Users\suraj\Hariharan\Assignments\Term3\MLOps\MLOps-Project\Automated_Due_Dillegence_Market_Intelligence_Agent_v2\Data_Pipeline\airflow\dags
load_examples = False

[webserver]
base_url = http://localhost:8080
```

### 4. Start Airflow

```bash
# Terminal 1: Start webserver
airflow webserver --port 8080

# Terminal 2: Start scheduler
airflow scheduler
```

### 5. Access UI

- URL: http://localhost:8080
- Username: `admin`
- Password: `admin`

---

## 📋 Available DAGs

### 1. **Initial Load DAG** (`initial_load`)
- **Purpose:** One-time historical data load
- **Schedule:** Manual trigger only
- **What it does:**
  - Fetches SEC filings (2023+)
  - Fetches Wikipedia pages
  - Fetches news articles
  - Processes, embeds, uploads to cloud

**To Run:**
1. Go to Airflow UI
2. Find `initial_load` DAG
3. Toggle it ON (switch on right)
4. Click ▶️ (Trigger DAG) button

### 2. **SEC Monitoring DAG** (`sec_monitoring`) - Coming Soon
- **Schedule:** Daily at 6 PM (weekdays)
- Monitors for new SEC filings

### 3. **Wikipedia Update DAG** (`wikipedia_update`) - Coming Soon
- **Schedule:** Weekly on Sundays
- Updates changed Wikipedia pages

### 4. **News Fetch DAG** (`news_fetch`) - Coming Soon
- **Schedule:** 2x daily (9 AM, 5 PM)
- Fetches latest news

---

## 🔧 Configuration

### Environment Variables

Make sure `.env` is in the project root with:

```env
# GCS
GCP_BUCKET_NAME=your-bucket
GCP_PROJECT_ID=your-project
GCP_CREDENTIALS_PATH=path/to/credentials.json

# Qdrant
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION=company_data

# PostgreSQL (optional for state tracking)
POSTGRES_HOST=your-host.supabase.co
POSTGRES_PORT=6543
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# APIs
GROQ_API_KEY=your-groq-key
SEC_API_KEY=your.email@example.com
```

---

## 🧪 Testing DAGs

### Test DAG Syntax
```bash
# Check for errors
python airflow/dags/initial_load_dag.py
```

### Test Individual Task
```bash
# Test a specific task
airflow tasks test initial_load process_AAPL 2024-12-10
```

### Test Entire DAG
```bash
# Run full DAG (won't write to DB)
airflow dags test initial_load 2024-12-10
```

---

## 📊 Monitoring

### View Logs
- **UI:** Click on task → View Log
- **File:** `airflow/logs/dag_id/task_id/execution_date/`

### Check DAG Status
```bash
# List all DAGs
airflow dags list

# Show DAG details
airflow dags show initial_load
```

### Troubleshooting

#### DAG Not Showing Up
1. Check `AIRFLOW_HOME` is set correctly
2. Restart scheduler: `Ctrl+C` then `airflow scheduler`
3. Check logs: `airflow/logs/scheduler/`

#### Import Errors
1. Make sure project root is in Python path
2. Check `.env` file exists
3. Verify all dependencies installed

#### Task Failing
1. View logs in UI
2. Check cloud connection
3. Verify credentials in `.env`

---

## 🎯 Next Steps

1. **Test Initial Load:**
   - Trigger `initial_load` DAG in UI
   - Monitor progress (should take 30-60 min for AAPL)
   - Verify data in Qdrant/GCS

2. **Implement Monitoring DAGs:**
   - SEC monitoring (daily)
   - Wikipedia updates (weekly)
   - News fetching (2x daily)

3. **Production Deployment:**
   - Consider Astron omer.io or AWS MWAA
   - Set up alerts (email/Slack)
   - Configure proper scaling

---

## 📚 Resources

- [Airflow Docs](https://airflow.apache.org/docs/)
- [Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Troubleshooting](https://airflow.apache.org/docs/apache-airflow/stable/troubleshooting.html)
