# ⚡ Quick Reference - Combined Data Pipeline

## 🚀 Setup Commands (Windows)

```bash
# 1. Navigate to project
cd combined_data_pipeline

# 2. Create environment file
copy .env.example .env
# Edit .env and add API keys

# 3. Start Docker services
cd docker
docker-compose up -d
cd ..

# 4. Initialize databases
python scripts\setup\init_databases.py
python scripts\setup\create_vector_collections.py

# 5. Access Airflow
# Open browser: http://localhost:8080
# Username: admin, Password: (from .env)
```

**OR use automated script:**
```bash
quick_start.bat
```

---

## 🔑 Required API Keys

| Service | URL | Free Tier | Purpose |
|---------|-----|-----------|---------|
| **Groq** | https://console.groq.com | 14,400 req/day | Table summarization |
| **NewsAPI** | https://newsapi.org | 1000 req/day | Financial news |
| SEC API | https://sec-api.io | Limited | Enhanced SEC features |

**In `.env`:**
```bash
GROQ_API_KEY=gsk_your_key_here
NEWSAPI_KEY=your_key_here
SEC_API_KEY=your_key_here  # Optional
```

---

## 📊 Airflow DAGs Overview

| DAG | Schedule | Purpose | Duration |
|-----|----------|---------|----------|
| **sec_filings_pipeline** | Daily 12am | New 10-K/10-Q | 5-15 min* |
| **wikipedia_refresh_pipeline** | Sun 3am | Weekly update | 2-5 min |
| **news_ingestion_pipeline** | Every 6hr | Recent news | 1-2 min |
| **data_cleanup_pipeline** | Daily 1am | Delete old news | <30 sec |

*First run: 1-3 hours (historical data)

---

## 🐳 Docker Commands

```bash
# Start services
docker-compose -f docker\docker-compose.yml up -d

# Stop services
docker-compose -f docker\docker-compose.yml down

# View logs
docker-compose -f docker\docker-compose.yml logs -f

# Check status
docker-compose -f docker\docker-compose.yml ps

# Restart service
docker-compose -f docker\docker-compose.yml restart airflow-scheduler
```

---

## ✈️ Trigger DAGs

**Via Airflow UI:**
1. Go to http://localhost:8080
2. Click ▶️ next to DAG name
3. Click "Trigger DAG"

**Via Command Line:**
```bash
docker exec -it docker_airflow-scheduler_1 airflow dags trigger sec_filings_pipeline
docker exec -it docker_airflow-scheduler_1 airflow dags trigger wikipedia_refresh_pipeline
docker exec -it docker_airflow-scheduler_1 airflow dags trigger news_ingestion_pipeline
docker exec -it docker_airflow-scheduler_1 airflow dags trigger data_cleanup_pipeline
```

---

## 📈 Check Pipeline Status

**In Airflow UI:**
- Click DAG name → **Graph** view → See task colors
- 🟢 Green = Success, 🔴 Red = Failed, 🟡 Yellow = Running

**Via Python:**
```bash
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); from src.storage.metadata_store_manager import MetadataStoreManager; db = MetadataStoreManager(); stats = db.get_pipeline_stats(); print(f'Companies: {stats.get(\"company_count\", 0)}'); print(f'Filings: {stats.get(\"total_filings\", 0)}'); print(f'Chunks: {stats.get(\"total_chunks\", 0)}')"
```

---

## 🗄️ Database Access

**PostgreSQL:**
```bash
# Connect
docker exec -it docker_postgres_1 psql -U pipeline_user -d due_diligence_dev

# View companies
SELECT * FROM companies;

# View filings
SELECT ticker, filing_type, fiscal_year, status, total_chunks
FROM sec_filings
ORDER BY filing_date DESC;

# Exit
\q
```

**Qdrant:**
```bash
# Open browser
http://localhost:6333/dashboard

# Or check programmatically
python -c "from src.storage.vector_store_manager import VectorStoreManager; vs = VectorStoreManager(); print(f'Chunks: {vs.count_chunks()}')"
```

---

## 🔧 Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker ps

# Check port conflicts
netstat -ano | findstr :5432
netstat -ano | findstr :8080

# Restart Docker Desktop
```

### DAGs not showing
```bash
# Check DAG files exist
dir airflow\dags

# Restart scheduler
docker-compose -f docker\docker-compose.yml restart airflow-scheduler

# Wait 30 seconds and refresh browser
```

### Database connection failed
```bash
# Verify PostgreSQL is up
docker-compose -f docker\docker-compose.yml ps postgres

# Check password in .env matches
type .env | findstr POSTGRES_PASSWORD

# Restart PostgreSQL
docker-compose -f docker\docker-compose.yml restart postgres
```

### Import errors
```bash
# Install dependencies
pip install -r requirements.txt

# Set Python path
set PYTHONPATH=%PYTHONPATH%;%CD%
```

### Out of memory
```bash
# Increase Docker memory
# Docker Desktop → Settings → Resources → Memory → 8GB+

# Or reduce batch size in configs\development.yaml
# Change: batch_size: 32 → batch_size: 16
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `.env` | **API keys and passwords** (DO NOT COMMIT) |
| `configs/development.yaml` | Pipeline configuration |
| `configs/companies.yaml` | Tracked companies list |
| `docker/docker-compose.yml` | Docker services definition |
| `airflow/dags/sec_filings_pipeline.py` | SEC DAG |
| `scripts/setup/init_databases.py` | DB schema creator |

---

## 🎯 Success Checklist

- [ ] Docker services running (4 containers)
- [ ] `.env` file created with API keys
- [ ] Database initialized (5 companies)
- [ ] Qdrant collection created
- [ ] Airflow accessible at http://localhost:8080
- [ ] All 4 DAGs visible and enabled
- [ ] At least one DAG triggered successfully
- [ ] Pipeline stats show data (chunks > 0)

---

## 📊 Expected Data Volumes (After Full Run)

| Source | Filings/Articles | Chunks | Vectors |
|--------|-----------------|--------|---------|
| SEC | ~25 filings | ~3,000 | ~3,000 |
| Wikipedia | 5 pages | ~75 | ~75 |
| News (3 days) | ~40 articles | ~120 | ~120 |
| **Total** | **~70 docs** | **~3,195** | **~3,195** |

---

## 🆘 Quick Help

**Documentation:**
- Full Setup Guide: `docs/SETUP_GUIDE.md`
- DAG Visualization: `docs/AIRFLOW_DAG_GUIDE.md`
- Main README: `README.md`

**Logs:**
```bash
# Airflow logs
docker-compose -f docker\docker-compose.yml logs airflow-scheduler

# PostgreSQL logs
docker-compose -f docker\docker-compose.yml logs postgres

# All logs
docker-compose -f docker\docker-compose.yml logs
```

**Useful Links:**
- Airflow UI: http://localhost:8080
- Qdrant Dashboard: http://localhost:6333/dashboard
- Groq Console: https://console.groq.com
- NewsAPI Dashboard: https://newsapi.org/account

---

**Last Updated**: 2025-01-18
